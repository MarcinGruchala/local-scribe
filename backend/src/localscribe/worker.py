"""A single supervised child process with durable attempt ownership and recovery."""

import argparse
import fcntl
import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

from .jobs import JobError


def stop_group(process: psutil.Process, grace: float = 1.0):
    """The caller must verify identity before passing a recovered process here."""
    try:
        if os.getpgid(process.pid) != process.pid:
            return
        os.killpg(process.pid, signal.SIGTERM)
        # Keep the leader unreaped until after the group-wide forced stop. Process
        # enumeration is unavailable in some macOS sandboxes and is not required.
        time.sleep(grace)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except PermissionError:
            # macOS sandbox reports EPERM for a group containing only a zombie.
            if process.status() != psutil.STATUS_ZOMBIE:
                raise
        except ProcessLookupError:
            pass
    except (ProcessLookupError, psutil.NoSuchProcess):
        pass


def command_matches(actual, expected):
    """macOS Python.app rewrites argv[0] after the interpreter launcher execs."""
    if not expected or not actual:
        return False
    if actual == expected:
        return True
    return (
        expected[0] == sys.executable
        and actual[0] == psutil.Process().exe()
        and actual[1:] == expected[1:]
    )


class Worker:
    def __init__(
        self, jobs, model_root: Path, *, command_factory=None, poll_interval=0.1, stop_grace=1.0
    ):
        self.jobs = jobs
        self.model_root = Path(model_root)
        self.command_factory = command_factory or (
            lambda request, result: [
                sys.executable,
                "-m",
                "localscribe.pipeline",
                "--request",
                str(request),
                "--output",
                str(result),
            ]
        )
        self.poll_interval, self.stop_grace = poll_interval, stop_grace
        self._stop = threading.Event()
        self._thread = None
        self._lock_handle = None
        self._process = None

    @property
    def alive(self):
        return self._thread is not None and self._thread.is_alive()

    def _fail(self, job_id, attempt, code, message):
        for _ in range(3):
            try:
                self.jobs.fail(job_id, attempt, code, message)
                return True
            except sqlite3.Error:
                time.sleep(min(self.poll_interval, 0.1))
        # Preserve the active row for startup recovery and stop taking new work.
        self._stop.set()
        return False

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        handle = (self.jobs.storage.root / "worker.lock").open("a+")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise RuntimeError("Another worker owns this local data store.") from None
        self._lock_handle = handle
        try:
            self._recover_children()
            self.jobs.recover()
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run, name="localscribe-worker", daemon=True
            )
            self._thread.start()
        except BaseException:
            self._release_lock()
            raise

    def _release_lock(self):
        if self._lock_handle:
            fcntl.flock(self._lock_handle, fcntl.LOCK_UN)
            self._lock_handle.close()
            self._lock_handle = None

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self.stop_grace + 10)
            if self._thread.is_alive():
                raise RuntimeError("The worker has not stopped; its ownership lock is retained.")
        self._release_lock()

    def _recover_children(self):
        for attempt in self.jobs.active_processes():
            if (
                attempt["pid"] is None
                or attempt["process_started"] is None
                or not attempt["command"]
            ):
                continue
            try:
                process = psutil.Process(attempt["pid"])
                expected = json.loads(attempt["command"])
                request_path = (
                    self.jobs.directory(attempt["job_id"])
                    / "attempts"
                    / str(attempt["number"])
                    / "request.json"
                )
                gate_command = None
                try:
                    request = json.loads(request_path.read_text())
                    gate_command = [
                        sys.executable,
                        "-m",
                        "localscribe.worker",
                        "--child-gate",
                        str(request_path),
                        "--command",
                        json.dumps(expected),
                        "--parent-pid",
                        str(request["launcherPid"]),
                        "--parent-started",
                        str(request["launcherStarted"]),
                    ]
                except (OSError, ValueError, KeyError):
                    pass
                if (
                    abs(process.create_time() - attempt["process_started"]) < 0.01
                    and any(
                        command_matches(process.cmdline(), candidate)
                        for candidate in (expected, gate_command)
                    )
                    and str(request_path) in expected
                ):
                    stop_group(process, self.stop_grace)
            except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
                continue

    def _run(self):
        try:
            while not self._stop.is_set():
                try:
                    job = self.jobs.claim()
                except sqlite3.Error:
                    self._stop.wait(min(max(self.poll_interval, 0.05), 0.5))
                    continue
                if job is None:
                    self._stop.wait(self.poll_interval)
                    continue
                try:
                    self._execute(job)
                except (
                    OSError,
                    ValueError,
                    JobError,
                    subprocess.SubprocessError,
                    psutil.Error,
                    sqlite3.Error,
                ):
                    self._fail(
                        job["id"],
                        job["attempt"],
                        "pipeline_failed",
                        "The worker could not start processing. Retry this job.",
                    )
        finally:
            self._process = None

    def _execute(self, job):
        job_id, attempt = job["id"], job["attempt"]
        directory = self.jobs.directory(job_id)
        attempt_dir = directory / "attempts" / str(attempt)
        attempt_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        request_path, result_path = attempt_dir / "request.json", attempt_dir / "result.json"
        request = {
            "jobId": job_id,
            "job": job,
            "options": job["options"],
            "source": str(directory / "source"),
            "normalized": str(directory / "normalized.wav"),
            "attempt_dir": str(attempt_dir),
            "model_root": str(self.model_root),
            "launcherPid": os.getpid(),
            "launcherStarted": psutil.Process().create_time(),
        }
        request_path.write_text(json.dumps(request))
        request_path.chmod(0o600)
        command = self.command_factory(request_path, result_path)
        process = None
        try:
            environment = dict(os.environ)
            # Local credentials must not enter the model worker process.
            for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_TOKEN"):
                environment.pop(key, None)
            environment.update(
                HF_HUB_OFFLINE="1",
                HF_HUB_DISABLE_TELEMETRY="1",
                TRANSFORMERS_OFFLINE="1",
                PYANNOTE_METRICS_ENABLED="0",
            )
            # The child cannot exec inference until PID identity is durably registered.
            gate_command = [
                sys.executable,
                "-m",
                "localscribe.worker",
                "--child-gate",
                str(request_path),
                "--command",
                json.dumps(command),
                "--parent-pid",
                str(request["launcherPid"]),
                "--parent-started",
                str(request["launcherStarted"]),
            ]
            process = subprocess.Popen(
                gate_command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=environment,
            )
            self._process = process
            identity = psutil.Process(process.pid)
            self.jobs.record_process(job_id, attempt, process.pid, identity.create_time(), command)
            (attempt_dir / "launch-permitted").touch()
            previous_stage = None
            while process.poll() is None:
                current = self.jobs.get(job_id)
                if self._stop.is_set() or current["status"] == "cancelling":
                    stop_group(identity, self.stop_grace)
                    process.wait(timeout=self.stop_grace + 2)
                    if current["status"] == "cancelling":
                        self.jobs.finish_cancel(job_id, attempt)
                    else:
                        self._fail(
                            job_id,
                            attempt,
                            "interrupted",
                            "Processing stopped with the application. Retry this job.",
                        )
                    return
                try:
                    stage = json.loads((attempt_dir / "stage.json").read_text())["stage"]
                    if stage != previous_stage:
                        self.jobs.stage(job_id, attempt, stage)
                        previous_stage = stage
                except (OSError, ValueError, KeyError):
                    pass
                self._stop.wait(self.poll_interval)
            if self.jobs.get(job_id)["status"] == "cancelling":
                self.jobs.finish_cancel(job_id, attempt)
                result_path.unlink(missing_ok=True)
                return
            if process.returncode != 0:
                try:
                    error = json.loads((attempt_dir / "error.json").read_text())
                    code = error["code"]
                    message = error["message"]
                except (OSError, ValueError, KeyError):
                    code, message = (
                        "pipeline_failed",
                        "The processing child failed. Retry this job.",
                    )
                self._fail(job_id, attempt, code, message)
            elif not self.jobs.publish(job_id, attempt, result_path):
                self.jobs.finish_cancel(job_id, attempt)
        except (
            OSError,
            ValueError,
            JobError,
            subprocess.SubprocessError,
            psutil.Error,
            sqlite3.Error,
        ):
            if process is not None and process.poll() is None:
                stop_group(psutil.Process(process.pid), self.stop_grace)
                process.wait(timeout=self.stop_grace + 2)
            self._fail(
                job_id,
                attempt,
                "pipeline_failed",
                "Processing or result validation failed. Retry this job.",
            )
        finally:
            # Persistence errors never leave a live inference process behind.
            if process is not None and process.poll() is None:
                stop_group(psutil.Process(process.pid), self.stop_grace)
                process.wait(timeout=self.stop_grace + 2)
            self._process = None


def child_gate(request: Path, command: list[str], parent_pid: int, parent_started: float):
    """Wait for durable parent registration, and exit if the parent dies first."""
    if os.getppid() != parent_pid:
        return 1
    try:
        parent = psutil.Process(parent_pid)
        if parent.create_time() != parent_started:
            return 1
    except psutil.NoSuchProcess:
        return 1
    deadline = time.monotonic() + 15
    permit = request.parent / "launch-permitted"
    while time.monotonic() < deadline:
        try:
            if (
                os.getppid() != parent.pid
                or not parent.is_running()
                or parent.create_time() != parent_started
            ):
                return 1
        except psutil.NoSuchProcess:
            return 1
        if permit.exists():
            os.execvpe(command[0], command, os.environ)
        time.sleep(0.02)
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--child-gate", type=Path, required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--parent-started", type=float, required=True)
    args = parser.parse_args()
    raise SystemExit(
        child_gate(args.child_gate, json.loads(args.command), args.parent_pid, args.parent_started)
    )

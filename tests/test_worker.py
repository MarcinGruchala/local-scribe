"""Fresh-process lifecycle checks with explicit pause/release synchronization."""

import os
import subprocess
import sys
import time

import psutil
import pytest
from localscribe.jobs import Jobs
from localscribe.storage import Storage
from localscribe.worker import Worker

CHILD = """
import json, os, pathlib, signal, sys, time
request_path, result_path = map(pathlib.Path, sys.argv[1:])
request = json.loads(request_path.read_text())
directory = request_path.parent
(directory / "entered").touch()
(directory / "stage.json").write_text(json.dumps({"stage":"transcribing"}))
while not (directory / "release").exists():
    time.sleep(.01)
job = request["job"]
result = {"jobId":job["id"],"duration":1,"language":"en","requestedLanguage":"auto",
"detectedLanguage":"en","options":job["options"],"originalText":"Hello",
"segments":[{"id":"s1","start":0,"end":1,"speakerId":None,"text":"Hello"}],
"speakers":[],"modelSegments":[],"words":[],"regularTurns":[],"exclusiveTurns":[],
"warnings":[],"provenance":{"fixture":True}}
result_path.write_text(json.dumps(result))
"""


@pytest.fixture
def jobs(tmp_path):
    service = Jobs(Storage(tmp_path / "store"))
    service.initialize()
    return service


def enqueue(jobs, tmp_path, name):
    source = tmp_path / name
    source.write_bytes(b"fixture original")
    return jobs.create_import(source, name, {"duration": 1, "sizeBytes": 16}, {})


def wait_for(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for a deterministic fixture synchronization point.")


def attempt_dir(jobs, job):
    return jobs.directory(job["id"]) / "attempts" / "1"


def make_worker(jobs, tmp_path, **kwargs):
    script = tmp_path / "fixture_child.py"
    script.write_text(CHILD)
    return Worker(
        jobs,
        tmp_path / "models",
        command_factory=lambda request, result: [
            sys.executable,
            str(script),
            str(request),
            str(result),
        ],
        poll_interval=0.01,
        stop_grace=0.1,
        **kwargs,
    )


def test_queue_runs_sequentially_and_leaves_database_responsive(jobs, tmp_path):
    first = enqueue(jobs, tmp_path, "one.wav")
    second = enqueue(jobs, tmp_path, "two.wav")
    worker = make_worker(jobs, tmp_path)
    worker.start()
    try:
        wait_for(lambda: (attempt_dir(jobs, first) / "entered").exists())
        assert jobs.get(second["id"])["status"] == "queued"
        assert not (attempt_dir(jobs, second) / "entered").exists()
        # This write would block if inference held a SQLite transaction.
        third = enqueue(jobs, tmp_path, "three.wav")
        assert jobs.get(third["id"])["status"] == "queued"
        wait_for(lambda: jobs.get(first["id"])["status"] == "transcribing")
        (attempt_dir(jobs, first) / "release").touch()
        wait_for(lambda: jobs.get(first["id"])["status"] == "completed")
        wait_for(lambda: (attempt_dir(jobs, second) / "entered").exists())
        jobs.cancel(third["id"])
        (attempt_dir(jobs, second) / "release").touch()
        wait_for(lambda: jobs.get(second["id"])["status"] == "completed")
        assert jobs.transcript(first["id"])["originalText"] == "Hello"
        assert (jobs.directory(first["id"]) / "source").read_bytes() == b"fixture original"
    finally:
        worker.stop()


def test_active_cancel_terminates_child_and_prevents_publication(jobs, tmp_path):
    job = enqueue(jobs, tmp_path, "cancel.wav")
    worker = make_worker(jobs, tmp_path)
    worker.start()
    try:
        wait_for(lambda: (attempt_dir(jobs, job) / "entered").exists())
        process = jobs.active_processes()[0]
        assert jobs.cancel(job["id"])["status"] == "cancelling"
        wait_for(lambda: jobs.get(job["id"])["status"] == "cancelled")
        assert not psutil.pid_exists(process["pid"])
        assert not list(jobs.directory(job["id"]).glob("attempts/*/published.json"))
        assert jobs.cancel(job["id"])["status"] == "cancelled"
    finally:
        worker.stop()


def test_shutdown_interrupts_active_preserves_queue_and_single_worker(jobs, tmp_path):
    first = enqueue(jobs, tmp_path, "first.wav")
    second = enqueue(jobs, tmp_path, "second.wav")
    worker = make_worker(jobs, tmp_path)
    worker.start()
    wait_for(lambda: (attempt_dir(jobs, first) / "entered").exists())
    duplicate = make_worker(jobs, tmp_path)
    with pytest.raises(RuntimeError, match="Another worker"):
        duplicate.start()
    worker.stop()
    assert jobs.get(first["id"])["failure"]["code"] == "interrupted"
    assert jobs.get(second["id"])["status"] == "queued"
    assert jobs.directory(first["id"]).joinpath("source").exists()


def test_recovery_checks_pid_create_time_and_exact_command(jobs, tmp_path):
    job = enqueue(jobs, tmp_path, "recovery.wav")
    active = jobs.claim()
    directory = attempt_dir(jobs, active)
    directory.mkdir(parents=True)
    request = directory / "request.json"
    request.write_text("{}")
    command = [sys.executable, "-c", "import time; time.sleep(60)", str(request)]
    process = subprocess.Popen(command, start_new_session=True)
    worker = make_worker(jobs, tmp_path)
    try:
        identity = psutil.Process(process.pid)
        jobs.record_process(job["id"], 1, process.pid, identity.create_time() - 100, command)
        worker.recover_children()
        assert process.poll() is None  # A reused PID cannot be killed.
        jobs.record_process(
            job["id"], 1, process.pid, identity.create_time(), command[:-1] + ["different-request"]
        )
        worker.recover_children()
        assert process.poll() is None
        jobs.record_process(job["id"], 1, process.pid, identity.create_time(), command)
        worker.recover_children()
        process.wait(timeout=3)
        jobs.recover()
        assert jobs.get(job["id"])["failure"]["code"] == "interrupted"
    finally:
        if process.poll() is None:
            os.killpg(process.pid, 9)
            process.wait()


def test_cancellation_forces_uncooperative_process_group(jobs, tmp_path):
    script = tmp_path / "uncooperative.py"
    script.write_text("""import pathlib, signal, subprocess, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
request = pathlib.Path(sys.argv[1])
child = subprocess.Popen([sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)"])
(request.parent / "grandchild.pid").write_text(str(child.pid))
(request.parent / "entered").touch()
while True: time.sleep(.01)
""")
    job = enqueue(jobs, tmp_path, "stubborn.wav")
    worker = Worker(
        jobs,
        tmp_path / "models",
        command_factory=lambda request, result: [sys.executable, str(script), str(request)],
        poll_interval=0.01,
        stop_grace=0.1,
    )
    worker.start()
    try:
        wait_for(lambda: (attempt_dir(jobs, job) / "entered").exists())
        grandchild = int((attempt_dir(jobs, job) / "grandchild.pid").read_text())
        jobs.cancel(job["id"])
        wait_for(lambda: jobs.get(job["id"])["status"] == "cancelled")

        def stopped():
            try:
                return psutil.Process(grandchild).status() == psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:
                return True

        wait_for(stopped)
    finally:
        worker.stop()


def test_child_gate_rejects_adopted_parent_even_with_existing_permit(tmp_path, monkeypatch):
    from localscribe.worker import child_gate

    request = tmp_path / "request.json"
    request.write_text("{}")
    request.with_name("launch-permitted").touch()
    monkeypatch.setattr("localscribe.worker.os.getppid", lambda: 1)

    def forbidden_exec(*args):
        raise AssertionError("Orphaned child must not start inference.")

    monkeypatch.setattr("localscribe.worker.os.execvpe", forbidden_exec)
    assert child_gate(request, ["inference"], 999999, 100.0) == 1


def test_transient_sqlite_claim_error_does_not_kill_worker(jobs, tmp_path, monkeypatch):
    import sqlite3

    job = enqueue(jobs, tmp_path, "sqlite.wav")
    real_claim = jobs.claim
    failed_once = False

    def temporarily_busy():
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise sqlite3.OperationalError("injected database busy")
        return real_claim()

    monkeypatch.setattr(jobs, "claim", temporarily_busy)
    worker = make_worker(jobs, tmp_path)
    worker.start()
    try:
        wait_for(lambda: (attempt_dir(jobs, job) / "entered").exists())
        assert failed_once and worker.alive
        jobs.cancel(job["id"])
        wait_for(lambda: jobs.get(job["id"])["status"] == "cancelled")
    finally:
        worker.stop()
    assert not worker.alive


def test_persistent_sqlite_failure_stops_child_before_worker_exits(jobs, tmp_path, monkeypatch):
    import sqlite3

    job = enqueue(jobs, tmp_path, "sqlite-failure.wav")
    worker = make_worker(jobs, tmp_path)
    worker.start()
    try:
        wait_for(lambda: (attempt_dir(jobs, job) / "entered").exists())
        identity = jobs.active_processes()[0]

        def unavailable(*args, **kwargs):
            raise sqlite3.OperationalError("injected persistent database failure")

        monkeypatch.setattr(jobs, "get", unavailable)
        monkeypatch.setattr(jobs, "fail", unavailable)
        wait_for(lambda: not worker.alive)
        assert not psutil.pid_exists(identity["pid"])
    finally:
        worker.stop()

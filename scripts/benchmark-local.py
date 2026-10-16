"""Run one explicit local spike while sampling read-only macOS memory pressure.

The child inherits the caller's OS network policy; this wrapper does not establish
network isolation or assess the 30/60-minute release gates. Run sequentially only
when the coordinator grants the inference slot. Private spike output stays outside Git.

Apple XNU's sysctl handler exports dispatch/knote flags, not its internal enum:
https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_memorystatus_notify.c
https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/event_private.h
Normal=1, warning=2, critical=4. Unknown raw values remain unknown in every report.
"""

import argparse
import ctypes
import fcntl
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
from collections import Counter
from itertools import pairwise
from pathlib import Path

from localscribe.models import default_root

PRESSURE_NAMES = {1: "normal", 2: "warning", 4: "critical"}
PRESSURE_SOURCES = [
    "https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_memorystatus_notify.c",
    "https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/event_private.h",
]
PROVENANCE_FIELDS = {"repo", "revision", "engine", "version", "device", "status", "task", "ready"}
MAX_RESULT_BYTES = 64 * 1024**2


class BenchmarkInterrupted(Exception):
    pass


def read_pressure():
    """Read the same unsigned value as sysctl -n kern.memorystatus_vm_pressure_level."""
    if sys.platform != "darwin":
        return {"rawLevel": None, "level": "unavailable", "error": "unsupported_platform"}
    try:
        query = ctypes.CDLL(None, use_errno=True).sysctlbyname
        query.argtypes = [
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        query.restype = ctypes.c_int
        value = ctypes.c_uint32()
        size = ctypes.c_size_t(ctypes.sizeof(value))
        code = query(
            b"kern.memorystatus_vm_pressure_level", ctypes.byref(value), ctypes.byref(size), None, 0
        )
        if code != 0 or size.value != ctypes.sizeof(value):
            return {"rawLevel": None, "level": "unavailable", "error": "sysctl_unavailable"}
        return {"rawLevel": value.value, "level": PRESSURE_NAMES.get(value.value, "unknown")}
    except (OSError, AttributeError, ValueError):
        return {"rawLevel": None, "level": "unavailable", "error": "sysctl_unavailable"}


def parse_free_percentage(text):
    match = re.search(
        r"System-wide memory free percentage:\s*(\d+(?:\.\d+)?)%", text, re.IGNORECASE
    )
    if match:
        value = float(match.group(1))
        if 0 <= value <= 100:
            return value
    return None


def read_baseline():
    baseline = {"pressure": read_pressure(), "freePercent": None}
    try:
        # -Q queries availability; never request an allocation or pressure trigger.
        result = subprocess.run(
            ["/usr/bin/memory_pressure", "-Q"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
        if result.returncode == 0:
            baseline["freePercent"] = parse_free_percentage(result.stdout)
        if baseline["freePercent"] is None:
            baseline["freePercentError"] = "memory_pressure_query_unavailable"
    except (OSError, subprocess.SubprocessError):
        baseline["freePercentError"] = "memory_pressure_query_unavailable"
    return baseline


def pressure_summary(samples, end_seconds):
    counts = Counter(
        str(sample["rawLevel"]) for sample in samples if sample["rawLevel"] is not None
    )
    start = None
    longest = 0.0
    for sample in samples:
        if sample["rawLevel"] in {2, 4}:
            if start is None:
                start = sample["elapsedSeconds"]
        elif start is not None:
            longest = max(longest, sample["elapsedSeconds"] - start)
            start = None
    if start is not None:
        longest = max(longest, end_seconds - start)
    gaps = [right["elapsedSeconds"] - left["elapsedSeconds"] for left, right in pairwise(samples)]
    return {
        "rawLevelCounts": dict(counts),
        "namedLevelCounts": dict(Counter(sample["level"] for sample in samples)),
        "unavailableSamples": sum(sample["rawLevel"] is None for sample in samples),
        "unknownSamples": sum(
            sample["rawLevel"] is not None and sample["rawLevel"] not in PRESSURE_NAMES
            for sample in samples
        ),
        "longestConsecutiveNonNormalSeconds": longest,
        "maximumObservedGapSeconds": max(gaps, default=0),
        "durationMethod": "Sample-and-hold estimate; unknown/unavailable observations break continuity. Short spikes between polls may be missed.",
    }


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def sanitized_result(result):
    required = ("duration", "totalSeconds", "realTimeFactor", "peakRssBytes")
    if any(not finite_number(result.get(key)) or result[key] < 0 for key in required):
        raise ValueError("Invalid aggregate spike metrics.")
    return {
        **{key: result[key] for key in required},
        "language": result.get("language"),
        "segmentCount": len(result.get("segments", [])),
        "speakerCount": len(result.get("speakers", [])),
        "warningCodes": [warning["code"] for warning in result.get("warnings", [])],
        "stageTimings": {
            key: value
            for key, value in result.get("stageTimings", {}).items()
            if finite_number(value) and value >= 0
        },
        "provenance": {
            engine: {key: value for key, value in details.items() if key in PROVENANCE_FIELDS}
            for engine, details in result.get("provenance", {}).items()
            if isinstance(details, dict)
        },
        "architecture": result.get("architecture"),
        "versions": result.get("versions", {}),
    }


def terminate_group(process, grace=1.0):
    """Only called with this invocation's own fresh-session Popen child."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
        # Keep the group leader unreaped until after escalation; its PID stays reserved.
        time.sleep(grace)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except PermissionError:
            # macOS sandbox can return EPERM for a group containing only a zombie.
            if process.poll() is None:
                raise
        except ProcessLookupError:
            pass
    except ProcessLookupError:
        pass
    process.wait(timeout=grace + 3)


def spike_command(args, child_output):
    command = [
        sys.executable,
        "-m",
        "localscribe.spike",
        str(args.sample),
        "--output",
        str(child_output),
        "--profile",
        args.profile,
        "--language",
        args.language,
        "--model-root",
        str(args.model_root),
    ]
    if args.diarization:
        command.append("--diarization")
    if args.speaker_count is not None:
        command += ["--speaker-count", str(args.speaker_count)]
    return command


def run_benchmark(
    args,
    *,
    pressure_reader=read_pressure,
    baseline_reader=read_baseline,
    command_factory=spike_command,
):
    wrapper_start = time.monotonic()
    baseline = baseline_reader()
    child_output = args.output.with_suffix(".spike.json")
    report = {
        "status": "failed",
        "baseline": baseline,
        "options": {
            "profile": args.profile,
            "language": args.language,
            "diarization": args.diarization,
            "speakerCount": args.speaker_count,
        },
        "pressureMapping": {str(key): value for key, value in PRESSURE_NAMES.items()},
        "pressureSources": PRESSURE_SOURCES,
        "pollIntervalSeconds": args.poll_interval,
        "osNetworkPolicy": "Inherited from caller; not established or verified by this wrapper.",
        "releaseGateAssessment": "Not assessed. Representative inputs and independent quality/reference, 30-minute and 60-minute gate review are required.",
    }
    environment = dict(os.environ)
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_TOKEN"):
        environment.pop(key, None)
    environment.update(
        HF_HUB_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
        TRANSFORMERS_OFFLINE="1",
        PYANNOTE_METRICS_ENABLED="0",
    )
    samples, process = [], None
    child_elapsed = None
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            command_factory(args, child_output),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=environment,
        )
        next_sample = started
        deadline = started + args.timeout
        while process.poll() is None:
            now = time.monotonic()
            if now >= deadline:
                report["status"] = "timed_out"
                terminate_group(process, args.stop_grace)
                break
            if now >= next_sample:
                samples.append({"elapsedSeconds": now - started, **pressure_reader()})
                next_sample = now + args.poll_interval
            time.sleep(
                min(
                    0.1, max(0, next_sample - time.monotonic()), max(0, deadline - time.monotonic())
                )
            )
        child_elapsed = time.monotonic() - started
        samples.append({"elapsedSeconds": child_elapsed, **pressure_reader()})
        report["childExitCode"] = process.returncode
        if process.returncode == 0 and report["status"] != "timed_out":
            if child_output.stat().st_size > MAX_RESULT_BYTES:
                raise ValueError("Private spike result exceeds the bounded parse limit.")
            report["result"] = sanitized_result(json.loads(child_output.read_text()))
            report["status"] = "completed"
        elif report["status"] != "timed_out":
            report["failureType"] = "child_failed"
    except (KeyboardInterrupt, BenchmarkInterrupted):
        report["status"] = "interrupted"
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        report["failureType"] = type(error).__name__
    finally:
        if process is not None and process.poll() is None:
            terminate_group(process, args.stop_grace)
        if child_elapsed is None:
            child_elapsed = time.monotonic() - started
        if process is not None:
            report["childExitCode"] = process.returncode
        report["childObservedWallSeconds"] = child_elapsed
        report["totalWallSeconds"] = time.monotonic() - wrapper_start
        report["memoryPressure"] = {**pressure_summary(samples, child_elapsed), "samples": samples}
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Sanitized report; private spike JSON/WAV use the same stem with .spike suffixes.",
    )
    parser.add_argument("--model-root", type=Path, default=default_root())
    parser.add_argument("--profile", choices=("fast", "quality"), default="fast")
    parser.add_argument("--language", choices=("auto", "en", "pl"), default="auto")
    parser.add_argument("--diarization", action="store_true")
    parser.add_argument("--speaker-count", type=int, choices=range(1, 11))
    parser.add_argument("--timeout", type=float, default=7200)
    parser.add_argument("--poll-interval", type=float, default=2)
    parser.add_argument("--stop-grace", type=float, default=1)
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[1]
    args.sample, args.output, args.model_root = (
        path.expanduser().resolve() for path in (args.sample, args.output, args.model_root)
    )
    if args.output.is_relative_to(repository) or args.model_root.is_relative_to(repository):
        parser.error(
            "Benchmark outputs and the writable model cache must remain outside the repository."
        )
    if not args.sample.is_file():
        parser.error("The selected local sample does not exist.")
    outputs = [
        args.output,
        args.output.with_suffix(".spike.json"),
        args.output.with_suffix(".spike.wav"),
    ]
    if args.sample in outputs or any(path.exists() for path in outputs):
        parser.error(
            "Choose unused output paths that cannot overwrite the input or previous evidence."
        )
    if args.speaker_count is not None and not args.diarization:
        parser.error("Speaker count requires --diarization.")
    for value, minimum, maximum in (
        (args.timeout, 0.01, 86400),
        (args.poll_interval, 0.05, 60),
        (args.stop_grace, 0, 10),
    ):
        if not math.isfinite(value) or not minimum <= value <= maximum:
            parser.error(
                "Timeout, polling interval, or stop grace is outside its finite supported bounds."
            )
    return args


def console_summary(report):
    # Full timestamped observations stay in the external JSON, never long console logs.
    return {
        **report,
        "memoryPressure": {
            key: value for key, value in report["memoryPressure"].items() if key != "samples"
        },
    }


def handle_termination(signum, frame):
    raise BenchmarkInterrupted()


def main():
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    signal.signal(signal.SIGTERM, handle_termination)
    lock_path = Path("/private/tmp") / f"localscribe-benchmark-{os.getuid()}.lock"
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SystemExit("Another benchmark owns the local inference slot.") from None
        report = run_benchmark(args)
    temporary = args.output.with_name(args.output.name + ".partial")
    try:
        with temporary.open("w") as handle:
            os.chmod(temporary, 0o600)
            json.dump(report, handle, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, args.output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps(console_summary(report), allow_nan=False))
    raise SystemExit(0 if report["status"] == "completed" else 1)


if __name__ == "__main__":
    main()

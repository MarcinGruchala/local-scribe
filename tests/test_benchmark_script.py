"""Memory reporting and real process cleanup checks without loading any model."""

import ctypes
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark-local.py"
spec = importlib.util.spec_from_file_location("local_benchmark", SCRIPT)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def args(tmp_path, **overrides):
    sample = tmp_path / "sample.wav"
    sample.write_bytes(b"fixture")
    return SimpleNamespace(
        sample=sample,
        output=tmp_path / "report.json",
        model_root=tmp_path / "models",
        profile="fast",
        language="auto",
        diarization=True,
        speaker_count=2,
        timeout=overrides.get("timeout", 3),
        poll_interval=0.05,
        stop_grace=0.05,
    )


def test_memory_pressure_flags_use_exported_values_and_keep_unknown(monkeypatch):
    monkeypatch.setattr(benchmark.sys, "platform", "darwin")

    class Query:
        value = 1

        def __call__(self, name, output, size, new_value, new_size):
            assert name == b"kern.memorystatus_vm_pressure_level"
            assert new_value is None and new_size == 0  # Read only.
            ctypes.cast(output, ctypes.POINTER(ctypes.c_uint32)).contents.value = self.value
            return 0

    query = Query()
    monkeypatch.setattr(
        benchmark.ctypes, "CDLL", lambda *a, **k: SimpleNamespace(sysctlbyname=query)
    )
    for raw, level in [
        (1, "normal"),
        (2, "warning"),
        (4, "critical"),
        (0, "unknown"),
        (99, "unknown"),
    ]:
        query.value = raw
        assert benchmark.read_pressure() == {"rawLevel": raw, "level": level}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("System-wide memory free percentage: 68%\n", 68),
        ("prefix\nSystem-wide memory free percentage: 12.5%\n", 12.5),
        ("System-wide memory free percentage: 101%", None),
        ("unavailable", None),
    ],
)
def test_baseline_free_percentage_parsing(text, expected):
    assert benchmark.parse_free_percentage(text) == expected


def test_read_only_baseline_query_never_triggers_pressure(monkeypatch):
    monkeypatch.setattr(benchmark, "read_pressure", lambda: {"rawLevel": 1, "level": "normal"})

    def run(command, **kwargs):
        assert command == ["/usr/bin/memory_pressure", "-Q"]
        assert kwargs["timeout"] == 5
        return SimpleNamespace(returncode=0, stdout="System-wide memory free percentage: 68%")

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    assert benchmark.read_baseline() == {
        "pressure": {"rawLevel": 1, "level": "normal"},
        "freePercent": 68,
    }


def test_unknown_and_unavailable_samples_break_non_normal_continuity():
    readings = [(0, 1), (2, 2), (4, 4), (6, None), (8, 2), (10, 99), (12, 4)]
    samples = [
        {
            "elapsedSeconds": t,
            "rawLevel": raw,
            "level": benchmark.PRESSURE_NAMES.get(raw, "unavailable" if raw is None else "unknown"),
        }
        for t, raw in readings
    ]
    summary = benchmark.pressure_summary(samples, 15)
    assert summary["rawLevelCounts"] == {"1": 1, "2": 2, "4": 2, "99": 1}
    assert summary["unavailableSamples"] == 1 and summary["unknownSamples"] == 1
    assert summary["longestConsecutiveNonNormalSeconds"] == 4
    assert summary["maximumObservedGapSeconds"] == 2


def fixture_child(tmp_path, source):
    script = tmp_path / "child.py"
    script.write_text(source)
    return lambda settings, output: [sys.executable, str(script), str(output)]


def test_one_fresh_child_reports_aggregates_without_text_tokens_or_paths(tmp_path, monkeypatch):
    settings = args(tmp_path)
    monkeypatch.setenv("HF_TOKEN", "secret-download-token")
    command = fixture_child(
        tmp_path,
        """import json, os, pathlib, sys, time
assert "HF_TOKEN" not in os.environ
assert os.environ["HF_HUB_OFFLINE"] == "1"
print("private transcript and credentials must not be forwarded")
time.sleep(.1)
pathlib.Path(sys.argv[1]).write_text(json.dumps({"duration":10,"totalSeconds":.1,"realTimeFactor":.01,
"peakRssBytes":1234,"language":"pl","segments":[{"text":"private text"}],"speakers":[],
"originalText":"private text","stageTimings":{"asr":.05,"diarization":.05},"warnings":[],
"provenance":{"asr":{"repo":"fixture/model","revision":"a"*40,"token":"private credential"}},
"privatePath":"/private/home/recording","versions":{}}))
""",
    )
    report = benchmark.run_benchmark(
        settings,
        pressure_reader=lambda: {"rawLevel": 1, "level": "normal"},
        baseline_reader=lambda: {"freePercent": 68},
        command_factory=command,
    )
    assert report["status"] == "completed" and report["childExitCode"] == 0
    assert report["result"]["segmentCount"] == 1 and report["result"]["peakRssBytes"] == 1234
    assert report["memoryPressure"]["rawLevelCounts"]["1"] >= 2
    assert report["memoryPressure"]["longestConsecutiveNonNormalSeconds"] == 0
    assert "passed" not in report and "Not assessed" in report["releaseGateAssessment"]
    serialized = json.dumps(report)
    for private in [
        "private text",
        "private credential",
        "secret-download-token",
        "/private/home/recording",
        str(settings.sample),
    ]:
        assert private not in serialized


def test_timeout_stops_uncooperative_child_and_process_group(tmp_path):
    settings = args(tmp_path, timeout=0.5)
    command = fixture_child(
        tmp_path,
        """import pathlib, signal, subprocess, sys, time
signal.signal(signal.SIGTERM,signal.SIG_IGN)
child=subprocess.Popen([sys.executable,"-c","import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)"])
pathlib.Path(sys.argv[1]+".pids").write_text(str(__import__("os").getpid())+" "+str(child.pid))
while True: time.sleep(.01)
""",
    )
    report = benchmark.run_benchmark(
        settings,
        pressure_reader=lambda: {"rawLevel": None, "level": "unavailable"},
        baseline_reader=dict,
        command_factory=command,
    )
    assert report["status"] == "timed_out" and report["childExitCode"] != 0
    assert report["memoryPressure"]["unavailableSamples"] > 0
    for pid in map(int, settings.output.with_suffix(".spike.json.pids").read_text().split()):
        try:
            assert psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            pass


def test_interruption_stops_own_child_and_preserves_sanitized_failure(tmp_path):
    settings = args(tmp_path)
    command = fixture_child(
        tmp_path,
        """import pathlib, os, sys, time
pathlib.Path(sys.argv[1]+".pid").write_text(str(os.getpid()))
time.sleep(60)
""",
    )
    count = 0

    def interrupted_read():
        nonlocal count
        count += 1
        if count > 1:
            raise benchmark.BenchmarkInterrupted()
        return {"rawLevel": 1, "level": "normal"}

    report = benchmark.run_benchmark(
        settings, pressure_reader=interrupted_read, baseline_reader=dict, command_factory=command
    )
    assert report["status"] == "interrupted"
    pid = int(settings.output.with_suffix(".spike.json.pid").read_text())
    assert not psutil.pid_exists(pid)


def test_cli_builds_fixed_spike_and_rejects_unsafe_outputs(tmp_path):
    source = tmp_path / "recording.wav"
    source.write_bytes(b"fixture")
    settings = benchmark.parse_args(
        [
            str(source),
            "--output",
            str(tmp_path / "benchmark.json"),
            "--diarization",
            "--speaker-count",
            "2",
            "--language",
            "pl",
        ]
    )
    command = benchmark.spike_command(settings, settings.output.with_suffix(".spike.json"))
    assert command[:3] == [sys.executable, "-m", "localscribe.spike"]
    assert command.count("--diarization") == 1 and command[-2:] == ["--speaker-count", "2"]
    for extra in [
        ["--output", str(SCRIPT.parent / "private.json")],
        ["--timeout", "nan"],
        ["--speaker-count", "2"],
        ["--output", str(source)],
    ]:
        with pytest.raises(SystemExit) as error:
            benchmark.parse_args([str(source), "--output", str(tmp_path / "report.json"), *extra])
        assert error.value.code == 2


def test_timeout_never_becomes_completed_when_child_handles_term_successfully(tmp_path):
    settings = args(tmp_path, timeout=0.3)
    command = fixture_child(
        tmp_path,
        """import json, pathlib, signal, sys, time
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
pathlib.Path(sys.argv[1]).write_text(json.dumps({"duration":10,"totalSeconds":.1,
"realTimeFactor":.01,"peakRssBytes":1234,"stageTimings":{},"segments":[]}))
while True: time.sleep(.01)
""",
    )
    report = benchmark.run_benchmark(
        settings,
        pressure_reader=lambda: {"rawLevel": 1, "level": "normal"},
        baseline_reader=dict,
        command_factory=command,
    )
    assert report["childExitCode"] == 0 and report["status"] == "timed_out"
    assert "result" not in report


def test_console_summary_keeps_aggregate_evidence_without_raw_sample_logs():
    report = {
        "status": "completed",
        "baseline": {"freePercent": 68},
        "pressureSources": benchmark.PRESSURE_SOURCES,
        "memoryPressure": {
            "rawLevelCounts": {"1": 1800},
            "unavailableSamples": 0,
            "samples": [{"rawLevel": 1, "elapsedSeconds": index * 2} for index in range(1800)],
        },
    }
    summary = benchmark.console_summary(report)
    assert "samples" not in summary["memoryPressure"]
    assert summary["memoryPressure"]["rawLevelCounts"] == {"1": 1800}
    assert summary["pressureSources"] == benchmark.PRESSURE_SOURCES
    assert len(report["memoryPressure"]["samples"]) == 1800
    assert len(json.dumps(summary)) < 1000

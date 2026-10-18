"""Model-free checks for the explicit live validation script's lifecycle assertions."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-live-cancellation.py"
spec = importlib.util.spec_from_file_location("live_cancellation_check", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def arguments(tmp_path, *, diarization=True):
    source = tmp_path / "sample.wav"
    source.write_bytes(b"fixture")
    cli = [
        "--sample",
        str(source),
        "--output",
        str(tmp_path / "report.json"),
        "--cancel-delay",
        "0",
        "--late-wait",
        "0",
    ]
    if diarization:
        cli += ["--diarization", "--stage", "diarizing"]
    return check.parse_args(cli)


def server(args, *, late_result=False, changed_retry=False, ended_stage=False):
    options = {
        "language": "en",
        "profile": "fast",
        "diarization": args.diarization,
        "speakerCount": None,
    }
    models = {"fast": {"repo": "fixture/asr", "revision": "a" * 40}}
    job = {
        "id": "fixture-job",
        "options": options,
        "modelSettings": models,
        "duration": 20,
        "status": "queued",
        "attempt": 0,
    }
    phase = "new"
    calls = []
    reads = 0
    transcript_reads = 0

    def handler(request):
        nonlocal phase, reads, transcript_reads
        route = request.url.path
        calls.append((request.method, route))
        if route == "/api/session":
            return httpx.Response(200, json={"token": "session-secret"})
        if request.method == "POST" and route == "/api/jobs":
            assert request.headers["X-LocalScribe-Token"] == "session-secret"
            phase = "active"
            return httpx.Response(201, json=job)
        if request.method == "POST" and route.endswith("/cancel"):
            phase = "cancelled"
            return httpx.Response(200, json={**job, "status": "cancelled", "attempt": 1})
        if request.method == "POST" and route.endswith("/retry"):
            phase = "retried"
            return httpx.Response(
                200,
                json={
                    **job,
                    "status": "queued",
                    "attempt": 1,
                    "modelSettings": {} if changed_retry else models,
                },
            )
        if request.method == "DELETE":
            phase = "deleted"
            return httpx.Response(204)
        if route.endswith("/transcript"):
            if phase == "cancelled":
                transcript_reads += 1
                return httpx.Response(200 if late_result and transcript_reads > 1 else 409, json={})
            return httpx.Response(
                200,
                json={
                    "options": options,
                    "originalText": "private transcript content",
                    "provenance": {
                        "asr": {
                            "repo": "fixture/asr",
                            "revision": "a" * 40,
                            "token": "private credential",
                        },
                        "diarization": {"repo": "fixture/diarization", "revision": "b" * 40},
                    },
                    "stageTimings": {"asr": 1, "diarization": 2},
                },
            )
        if phase == "deleted":
            return httpx.Response(404)
        if phase == "active":
            reads += 1
            stage = "assembling" if ended_stage and reads > 1 else args.stage
            return httpx.Response(200, json={**job, "status": stage, "attempt": 1})
        if phase == "cancelled":
            return httpx.Response(200, json={**job, "status": "cancelled", "attempt": 1})
        return httpx.Response(200, json={**job, "status": "completed", "attempt": 2})

    return httpx.Client(
        base_url="http://127.0.0.1:8767", transport=httpx.MockTransport(handler)
    ), calls


@pytest.mark.parametrize("diarization", [True, False])
def test_requested_stage_cancel_retry_same_settings_delete_and_redaction(tmp_path, diarization):
    args = arguments(tmp_path, diarization=diarization)
    client, calls = server(args)
    with client:
        report = check.run_check(client, args)
    assert report["passed"] and report["deleted"] and report["immutableRetrySettings"]
    assert report["cancelStage"] == ("diarizing" if diarization else "transcribing")
    assert report["retryAttempt"] == 2 and report["latePublicationPrevented"]
    assert ("DELETE", "/api/jobs/fixture-job") in calls
    serialized = json.dumps(report)
    for secret in (
        "private transcript content",
        "private credential",
        "session-secret",
        str(args.sample),
    ):
        assert secret not in serialized


@pytest.mark.parametrize(
    "failure,code",
    [
        ("late_result", "late_transcript_publication"),
        ("changed_retry", "retry_model_settings_changed"),
        ("ended_stage", "requested_stage_ended_before_cancel"),
    ],
)
def test_failed_checks_are_reported_and_owned_job_cleaned(tmp_path, failure, code):
    args = arguments(tmp_path)
    client, calls = server(args, **{failure: True})
    with client:
        report = check.run_check(client, args)
    assert not report["passed"] and report["failedCheck"] == code and report["deleted"]
    assert ("DELETE", "/api/jobs/fixture-job") in calls


def test_cli_preserves_defaults_and_rejects_unsafe_or_inconsistent_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(check, "ROOT", tmp_path)
    (tmp_path / "cancellation.wav").write_bytes(b"fixture")
    args = check.parse_args([])
    assert args.base_url == "http://127.0.0.1:8767" and args.stage == "transcribing"
    assert not args.diarization and args.cancel_delay == 0.9 and args.late_wait == 2
    assert args.sample == tmp_path / "cancellation.wav"
    assert args.output == tmp_path / "live-cancellation.json"
    for cli in [
        ["--stage", "diarizing"],
        ["--base-url", "https://example.com"],
        ["--base-url", "http://user:password@127.0.0.1"],
        ["--timeout", "nan"],
        ["--output", str(SCRIPT.parent / "report.json")],
    ]:
        with pytest.raises(SystemExit) as error:
            check.parse_args(cli)
        assert error.value.code == 2

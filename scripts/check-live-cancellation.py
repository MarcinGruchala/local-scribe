"""Explicit real-model cancellation/retry check against an isolated validation server.

Run only when the coordinator grants the single local inference slot. Reports never
contain transcript text, session tokens, response bodies, or local recording paths.
"""

import argparse
import json
import math
import os
import time
import urllib.parse
from pathlib import Path

import httpx

ROOT = Path("/private/tmp/localscribe-validation")
TERMINAL = {"completed", "failed", "cancelled"}
PROVENANCE_FIELDS = {"repo", "revision", "engine", "version", "device", "status", "task", "ready"}


class CheckFailure(Exception):
    """A stable, sanitized check identifier; never an HTTP response or transcript."""


def require(condition, code):
    if not condition:
        raise CheckFailure(code)


def read_state(client, path, timeout=10):
    response = client.get(path, timeout=timeout)
    require(response.status_code == 200, "job_status_unavailable")
    return response.json()


def wait_status(client, path, target, timeout):
    deadline = time.monotonic() + timeout
    while (remaining := deadline - time.monotonic()) > 0:
        state = read_state(client, path, timeout=min(10, remaining))
        if state["status"] == target:
            return state
        require(state["status"] not in TERMINAL, "unexpected_terminal_state_before_" + target)
        time.sleep(min(0.05, remaining))
    raise CheckFailure("timed_out_waiting_for_" + target)


def sanitized_provenance(provenance):
    return {
        engine: {key: value for key, value in details.items() if key in PROVENANCE_FIELDS}
        for engine, details in provenance.items()
        if isinstance(details, dict)
    }


def cleanup(client, path, headers, timeout):
    """Only touch the job created by this invocation, including on check failure."""
    try:
        state = read_state(client, path)
        if state["status"] not in TERMINAL:
            response = client.post(path + "/cancel", headers=headers, timeout=10)
            require(response.status_code == 200, "cleanup_cancel_failed")
            state = wait_status(client, path, "cancelled", min(timeout, 30))
        if state["status"] in TERMINAL:
            response = client.delete(path, headers=headers, timeout=10)
            return response.status_code == 204 and client.get(path, timeout=10).status_code == 404
    except (CheckFailure, httpx.HTTPError, ValueError, KeyError):
        return False
    return False


def run_check(client, args):
    response = client.get("/api/session", timeout=10)
    require(response.status_code == 200, "session_unavailable")
    headers = {"X-LocalScribe-Token": response.json()["token"]}
    options = {"language": "en", "profile": "fast", "diarization": args.diarization}
    with args.sample.open("rb") as stream:
        response = client.post(
            "/api/jobs",
            headers=headers,
            files={"file": (args.sample.name, stream, "audio/wav")},
            data={"options": json.dumps(options)},
            timeout=args.timeout,
        )
    require(response.status_code == 201, "import_failed")
    job = response.json()
    path = "/api/jobs/" + job["id"]
    report = {"passed": False, "cancelStage": args.stage, "diarization": args.diarization}
    try:
        state = wait_status(client, path, args.stage, args.timeout)
        require(state["attempt"] == 1, "unexpected_initial_attempt")
        time.sleep(args.cancel_delay)
        state = read_state(client, path)
        require(state["status"] == args.stage, "requested_stage_ended_before_cancel")
        require(
            client.post(path + "/cancel", headers=headers, timeout=10).status_code == 200,
            "cancel_request_failed",
        )
        state = wait_status(client, path, "cancelled", args.timeout)
        require(
            client.get(path + "/transcript", timeout=10).status_code == 409,
            "cancelled_attempt_published_transcript",
        )
        require(
            client.post(path + "/cancel", headers=headers, timeout=10).status_code == 200,
            "repeated_cancel_failed",
        )
        time.sleep(args.late_wait)
        require(read_state(client, path)["status"] == "cancelled", "late_status_publication")
        require(
            client.get(path + "/transcript", timeout=10).status_code == 409,
            "late_transcript_publication",
        )
        response = client.post(path + "/retry", headers=headers, timeout=10)
        require(response.status_code == 200, "retry_request_failed")
        retry = response.json()
        require(retry["options"] == job["options"], "retry_options_changed")
        require(
            retry.get("modelSettings") == job.get("modelSettings"), "retry_model_settings_changed"
        )
        state = wait_status(client, path, "completed", args.timeout)
        require(state["attempt"] == 2, "unexpected_retry_attempt")
        require(state["options"] == job["options"], "completed_options_changed")
        require(
            state.get("modelSettings") == job.get("modelSettings"),
            "completed_model_settings_changed",
        )
        response = client.get(path + "/transcript", timeout=10)
        require(response.status_code == 200, "retry_transcript_unavailable")
        result = response.json()
        require(result["options"] == job["options"], "transcript_options_changed")
        if args.diarization:
            provenance = result["provenance"].get("diarization", {})
            require(
                provenance.get("status") not in {"failed", "disabled"}
                and bool(provenance.get("repo"))
                and bool(provenance.get("revision")),
                "retry_diarization_not_successful",
            )
        report.update(
            {
                "duration": state["duration"],
                "cancelledAttempt": 1,
                "retryAttempt": 2,
                "retryStatus": state["status"],
                "latePublicationPrevented": True,
                "immutableRetrySettings": True,
                "source": "Public human-speech validation fixture; cancellation check only",
                "provenance": sanitized_provenance(result["provenance"]),
                "stageTimings": result["stageTimings"],
            }
        )
        require(
            client.delete(path, headers=headers, timeout=10).status_code == 204, "delete_failed"
        )
        report["deleted"] = client.get(path, timeout=10).status_code == 404
        require(report["deleted"], "deleted_job_still_visible")
        report["passed"] = True
    except (CheckFailure, httpx.HTTPError, ValueError, KeyError) as error:
        report["failedCheck"] = (
            str(error) if isinstance(error, CheckFailure) else type(error).__name__
        )
        report["deleted"] = cleanup(client, path, headers, args.timeout)
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8767")
    parser.add_argument("--sample", type=Path, default=ROOT / "cancellation.wav")
    parser.add_argument("--output", type=Path, default=ROOT / "live-cancellation.json")
    parser.add_argument("--diarization", action="store_true")
    parser.add_argument("--stage", choices=("transcribing", "diarizing"), default="transcribing")
    parser.add_argument(
        "--timeout", type=float, default=120, help="Maximum seconds per lifecycle phase."
    )
    parser.add_argument(
        "--cancel-delay",
        type=float,
        default=0.9,
        help="Seconds within the selected stage before cancellation.",
    )
    parser.add_argument(
        "--late-wait",
        type=float,
        default=2,
        help="Seconds to watch for forbidden late publication.",
    )
    args = parser.parse_args(argv)
    base = urllib.parse.urlparse(args.base_url)
    if (
        base.scheme != "http"
        or base.hostname not in {"127.0.0.1", "localhost", "::1"}
        or base.username
        or base.password
        or base.path not in {"", "/"}
        or base.query
        or base.fragment
    ):
        parser.error(
            "The validation server must be an HTTP loopback URL without credentials or a path."
        )
    if args.stage == "diarizing" and not args.diarization:
        parser.error("The diarizing stage requires --diarization.")
    if not math.isfinite(args.timeout) or not 0 < args.timeout <= 3600:
        parser.error("Timeout must be finite, greater than zero, and at most 3600 seconds.")
    if any(
        not math.isfinite(value) or not 0 <= value <= 30
        for value in (args.cancel_delay, args.late_wait)
    ):
        parser.error("Cancel delay and late wait must be finite and between zero and 30 seconds.")
    args.sample = args.sample.expanduser().resolve()
    args.output = args.output.expanduser().resolve()
    repository = Path(__file__).resolve().parents[1]
    if args.output.is_relative_to(repository):
        parser.error("Write validation reports outside the repository.")
    if not args.sample.is_file():
        parser.error("The selected local sample does not exist.")
    return args


def main():
    args = parse_args()
    try:
        with httpx.Client(base_url=args.base_url, timeout=120) as client:
            report = run_check(client, args)
    except (CheckFailure, httpx.HTTPError, ValueError, KeyError, OSError) as error:
        report = {
            "passed": False,
            "failedCheck": str(error) if isinstance(error, CheckFailure) else type(error).__name__,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = args.output.with_name(args.output.name + ".partial")
    try:
        with temporary.open("w") as handle:
            os.chmod(temporary, 0o600)
            json.dump(report, handle, indent=2)
            handle.write("\n")
        os.replace(temporary, args.output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps(report))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()

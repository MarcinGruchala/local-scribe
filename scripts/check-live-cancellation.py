"""Explicit real-model cancellation/retry check against the isolated validation server."""

import json
import time
from pathlib import Path

import httpx

ROOT = Path("/private/tmp/localscribe-validation")
source = ROOT / "cancellation.wav"
base = "http://127.0.0.1:8767"
with httpx.Client(base_url=base, timeout=120) as client:
    token = client.get("/api/session").json()["token"]
    headers = {"X-LocalScribe-Token": token}
    with source.open("rb") as stream:
        response = client.post(
            "/api/jobs",
            headers=headers,
            files={"file": ("cancellation.wav", stream, "audio/wav")},
            data={
                "options": json.dumps({"language": "en", "profile": "fast", "diarization": False})
            },
        )
    response.raise_for_status()
    job = response.json()
    path = "/api/jobs/" + job["id"]
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        state = client.get(path).json()
        if state["status"] == "transcribing":
            break
        if state["status"] in ("failed", "completed"):
            raise RuntimeError("Expected an active transcription before cancellation.")
        time.sleep(0.05)
    else:
        raise RuntimeError("Transcription stage did not start.")
    time.sleep(0.9)
    assert client.post(path + "/cancel", headers=headers).status_code == 200
    while time.monotonic() < deadline:
        state = client.get(path).json()
        if state["status"] == "cancelled":
            break
        time.sleep(0.1)
    assert state["status"] == "cancelled"
    assert client.get(path + "/transcript").status_code == 409
    time.sleep(2)
    assert client.get(path).json()["status"] == "cancelled"
    assert client.post(path + "/retry", headers=headers).status_code == 200
    while time.monotonic() < deadline:
        state = client.get(path).json()
        if state["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.1)
    assert state["status"] == "completed", state.get("error")
    assert state["attempt"] == 2
    result = client.get(path + "/transcript").json()
    report = {
        "duration": state["duration"],
        "cancelledAttempt": 1,
        "retryAttempt": 2,
        "retryStatus": state["status"],
        "latePublicationPrevented": True,
        "source": "Repeated public English FLEURS snippet; cancellation fixture only",
        "provenance": result["provenance"],
        "stageTimings": result["stageTimings"],
    }
    assert client.delete(path, headers=headers).status_code == 204
    report["deleted"] = client.get(path).status_code == 404
    (ROOT / "live-cancellation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))

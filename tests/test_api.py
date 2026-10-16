"""HTTP import/edit/export/playback contracts with deterministic persisted results."""

import io
import json
import wave

import pytest
from fastapi.testclient import TestClient
from localscribe.alignment import assemble
from localscribe.api import create_app
from localscribe.config import Settings


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(tmp_path / "store", tmp_path / "models", tmp_path / "ui"))
    app.state.readiness = lambda: {k: {"ready": True} for k in ("fast", "quality", "diarization")}
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        client.headers["X-LocalScribe-Token"] = client.get("/api/session").json()["token"]
        yield client


def wav_bytes():
    data = io.BytesIO()
    with wave.open(data, "wb") as handle:
        handle.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        handle.writeframes(b"\0\0" * 32000)
    return data.getvalue()


def create(client):
    response = client.post(
        "/api/jobs",
        files={"file": ("../Zażółć.wav", wav_bytes(), "audio/wav")},
        data={"options": json.dumps({"diarization": True})},
    )
    assert response.status_code == 201, response.text
    return response.json()


def complete(client, job):
    jobs = client.app.state.jobs
    claimed = jobs.claim()
    directory = jobs.directory(job["id"])
    (directory / "normalized.wav").write_bytes(wav_bytes())
    result = assemble(
        {
            "text": "Hello world",
            "language": "en",
            "segments": [{"start": 0, "end": 1, "text": "Hello world"}],
        },
        [{"start": 0, "end": 1, "speakerId": "x"}],
        [{"start": 0, "end": 1, "speakerId": "x"}],
        2,
        job["id"],
        claimed["options"],
    )
    output = directory / "result.json"
    output.write_text(json.dumps(result))
    assert jobs.publish(job["id"], claimed["attempt"], output)
    return result


def test_import_play_edit_export_delete(client):
    job = create(client)
    assert client.delete("/api/jobs/" + job["id"]).status_code == 409
    assert client.get("/api/jobs").json()["total"] == 1
    original = complete(client, job)
    path = "/api/jobs/" + job["id"]
    full = client.get(path + "/media")
    ranged = client.get(path + "/media", headers={"Range": "bytes=0-9"})
    assert ranged.status_code == 206
    assert ranged.content == full.content[:10]
    assert ranged.headers["content-range"].startswith("bytes 0-9/")
    assert client.get(path + "/media", headers={"Range": "bytes=99999999-"}).status_code == 416
    assert client.get(path + "/media", headers={"Range": "garbage"}).status_code == 400
    edit = client.patch(
        path + "/transcript",
        json={
            "revision": 0,
            "texts": {"segment_1": "Zażółć gęślą"},
            "names": {"speaker_1": "Marcin"},
        },
    )
    assert edit.status_code == 200, edit.text
    assert (
        client.patch(
            path + "/transcript", json={"revision": 0, "texts": {"segment_1": "stale"}}
        ).status_code
        == 409
    )
    assert (
        client.patch(
            path + "/transcript", json={"revision": 1, "texts": {"unknown": "bad"}}
        ).status_code
        == 422
    )
    saved = client.get(path + "/transcript").json()
    assert saved["segments"][0]["text"] == original["segments"][0]["text"]
    assert saved["segments"][0]["editedText"] == "Zażółć gęślą"
    assert saved["speakers"][0]["displayName"] == "Marcin"
    for fmt in ("txt", "srt", "vtt", "json"):
        export = client.get(path + "/export", params={"format": fmt})
        assert export.status_code == 200
        assert "Zażółć gęślą" in export.text
        assert "Marcin" in export.text
    assert client.get(path + "/export", params={"format": "exe"}).status_code == 422
    directory = client.app.state.jobs.directory(job["id"])
    assert (directory / "source").read_bytes() == wav_bytes()
    assert client.delete(path).status_code == 204
    assert not directory.exists()
    assert client.get(path).status_code == 404


def test_bad_options_and_missing_models_do_not_queue(client):
    assert (
        client.post(
            "/api/jobs", files={"file": ("a.wav", wav_bytes())}, data={"options": "{"}
        ).status_code
        == 422
    )
    client.app.state.readiness = lambda: {
        k: {"ready": False} for k in ("fast", "quality", "diarization")
    }
    response = client.post("/api/jobs", files={"file": ("a.wav", wav_bytes())})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "model_not_ready"
    assert client.app.state.jobs.list()["total"] == 0
    assert not list(client.app.state.storage.imports_root.iterdir())


def test_stopped_supervised_worker_reports_actionable_readiness(client):
    from types import SimpleNamespace

    client.app.state.worker = SimpleNamespace(alive=False)
    result = client.get("/api/health").json()
    assert result["ready"] is False
    assert result["worker"]["running"] is False
    assert "Restart the application" in result["worker"]["message"]


def test_retry_cannot_silently_change_the_imported_model_revision(client):
    references = {
        "fast": {
            "ready": True,
            "repo": "mlx-community/whisper-large-v3-turbo",
            "revision": "a" * 40,
        },
        "diarization": {
            "ready": True,
            "repo": "pyannote/speaker-diarization-community-1",
            "revision": "b" * 40,
        },
        "quality": {"ready": False},
    }
    client.app.state.readiness = lambda: references
    job = create(client)
    assert job["modelSettings"]["fast"]["revision"] == "a" * 40
    path = "/api/jobs/" + job["id"]
    assert client.post(path + "/cancel").json()["status"] == "cancelled"
    references["fast"]["revision"] = "c" * 40
    response = client.post(path + "/retry")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "model_revision_changed"
    assert client.get(path).json()["status"] == "cancelled"
    references["fast"]["revision"] = "a" * 40
    assert client.post(path + "/retry").json()["status"] == "queued"
    assert client.get(path).json()["modelSettings"]["fast"]["revision"] == "a" * 40

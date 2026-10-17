"""Existing inference results become editable history entries without inference."""

import json
import wave

import pytest
from fastapi.testclient import TestClient
from localscribe.api import create_app
from localscribe.config import Settings
from localscribe.jobs import Jobs
from localscribe.restore import restore_transcript
from localscribe.storage import Storage
from test_jobs import completed


def artifacts(tmp_path):
    previous = Jobs(Storage(tmp_path / "previous"))
    previous.initialize()
    job = completed(previous, tmp_path)
    previous.patch(job["id"], 0, {"s1": "Saved correction"}, {"speaker1": "Saved name"})
    transcript = tmp_path / "transcript.json"
    transcript.write_text(json.dumps(previous.transcript(job["id"])))
    normalized = tmp_path / "normalized.wav"
    with wave.open(str(normalized), "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0\0" * 16000)
    return transcript, previous.directory(job["id"]) / "source", normalized


def test_restore_appears_in_history_with_playback_edits_exports_and_no_queued_inference(tmp_path):
    transcript, source, normalized = artifacts(tmp_path)
    settings = Settings(tmp_path / "active", tmp_path / "models", tmp_path / "ui")
    app = create_app(settings)
    jobs = app.state.jobs
    assert jobs.list()["total"] == 0
    restored = restore_transcript(jobs, transcript, source, normalized)
    assert jobs.claim() is None
    assert source.is_file() and normalized.is_file() and transcript.is_file()
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        assert client.get("/api/jobs").json()["jobs"][0]["id"] == restored["id"]
        route = "/api/jobs/" + restored["id"]
        value = client.get(route + "/transcript").json()
        assert value["revision"] == 1
        assert value["segments"][0]["text"] == "Hello"
        assert value["segments"][0]["editedText"] == "Saved correction"
        assert value["speakers"][0]["displayName"] == "Saved name"
        assert value["provenance"]["restoration"]["inferenceRerun"] is False
        assert client.get(route + "/media", headers={"Range": "bytes=0-43"}).status_code == 206
        assert "Saved correction" in client.get(route + "/export?format=txt").text
        client.headers["X-LocalScribe-Token"] = client.get("/api/session").json()["token"]
        saved = client.patch(
            route + "/transcript", json={"revision": 1, "texts": {"s1": "New edit"}}
        )
        assert saved.status_code == 200
        # Repeating restoration must neither duplicate the entry nor erase later edits.
        assert restore_transcript(jobs, transcript, source, normalized)["id"] == restored["id"]
        assert jobs.list()["total"] == 1
        assert jobs.transcript(restored["id"])["segments"][0]["editedText"] == "New edit"
        assert client.delete(route).status_code == 204
    assert source.is_file() and normalized.is_file() and transcript.is_file()


def test_mismatching_audio_does_not_create_history_or_files(tmp_path):
    transcript, source, normalized = artifacts(tmp_path)
    value = json.loads(transcript.read_text())
    value["duration"] = 100
    transcript.write_text(json.dumps(value))
    jobs = Jobs(Storage(tmp_path / "active"))
    jobs.initialize()
    with pytest.raises(ValueError, match="must match"):
        restore_transcript(jobs, transcript, source, normalized)
    assert jobs.list()["total"] == 0 and not list(jobs.storage.jobs_root.iterdir())


def test_failed_copy_keeps_history_unpublished_and_sources_intact(tmp_path, monkeypatch):
    transcript, source, normalized = artifacts(tmp_path)
    jobs = Jobs(Storage(tmp_path / "active"))
    jobs.initialize()

    def fail_copy(*args):
        raise OSError("Simulated disk full")

    monkeypatch.setattr("localscribe.restore.shutil.copyfile", fail_copy)
    with pytest.raises(OSError, match="disk full"):
        restore_transcript(jobs, transcript, source, normalized)
    assert jobs.list()["total"] == 0 and not list(jobs.storage.jobs_root.iterdir())
    assert source.is_file() and normalized.is_file() and transcript.is_file()

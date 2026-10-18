"""Local-file repair uses authenticated job ownership, never caller-provided paths."""

from pathlib import Path

from test_api import client as client  # noqa: PLC0414 - expose the shared pytest fixture
from test_api import complete, create


def test_health_exposes_actual_configured_storage_location(client):
    storage = client.get("/api/health").json()["storage"]
    assert storage["dataRoot"] == str(client.app.state.settings.data_root)
    assert Path(storage["dataRoot"]).is_absolute()
    assert storage["availableBytes"] > 0


def test_local_file_repair_requires_session_and_known_job(client):
    token = client.headers.pop("X-LocalScribe-Token")
    response = client.post("/api/jobs/" + "a" * 32 + "/local-files")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "invalid_session"
    client.headers["X-LocalScribe-Token"] = token
    response = client.post("/api/jobs/" + "a" * 32 + "/local-files")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"


def test_local_file_repair_restores_known_job_files_and_cannot_redirect_output(client, tmp_path):
    job = create(client)
    complete(client, job)
    path = f"/api/jobs/{job['id']}"
    before = client.get(path).json()["localFiles"]
    assert before["status"] == "ready"
    Path(before["files"][0]).unlink()
    arbitrary_target = tmp_path / "caller-selected-folder"
    response = client.post(path + "/local-files", json={"directory": str(arbitrary_target)})
    assert response.status_code == 200
    repaired = response.json()["localFiles"]
    assert repaired["status"] == "ready"
    assert repaired["directory"] == str(client.app.state.jobs.directory(job["id"]))
    assert len(repaired["files"]) == 4
    assert all(Path(file).is_file() for file in repaired["files"])
    assert not arbitrary_target.exists()
    assert client.get(path + "/transcript").json()["revision"] == 0

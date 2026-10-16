"""Fast startup, security, and durable-store checks without model assets."""

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from localscribe.api import create_app
from localscribe.config import Settings
from localscribe.launcher import AlreadyRunningError, instance_lock
from localscribe.storage import Storage


@pytest.fixture
def settings(tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("<!doctype html><title>LocalScribe</title>")
    return Settings(tmp_path / "private", tmp_path / "models", frontend, 8765)


@pytest.fixture
def client(settings):
    app = create_app(settings)

    @app.post("/api/protected-test")
    def protected_test():
        return {"ok": True}

    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        yield client


def test_same_origin_root_and_health_without_models(client):
    assert client.get("/").status_code == 200
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["ready"] is False
    assert "token" not in health.text
    assert health.headers["cache-control"] == "no-store"


def test_security_rejects_unexpected_hosts_and_origins(client):
    for host in ("example.com:8765", "127.0.0.1.evil.example:8765", "127.0.0.1:9999", "[::1]:8765"):
        response = client.get("/api/session", headers={"host": host})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "invalid_host"
    for origin in (
        "https://example.com",
        "null",
        "http://[",
        "http://127.0.0.1:9999",
        "http://localhost:8765",
        "http://127.0.0.1:8765/path",
    ):
        response = client.get("/api/session", headers={"origin": origin})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "invalid_origin"
    assert (
        client.get("/api/session", headers={"origin": "http://127.0.0.1:8765"}).status_code == 200
    )


def test_mutations_require_session_token(client):
    assert client.post("/api/protected-test").status_code == 403
    assert (
        client.post("/api/protected-test", headers={"X-LocalScribe-Token": "wrong"}).status_code
        == 403
    )
    token = client.get("/api/session").json()["token"]
    assert (
        client.post("/api/protected-test", headers={"X-LocalScribe-Token": token}).status_code
        == 200
    )


def test_migrations_and_connection_pragmas_are_repeatable(settings):
    storage = Storage(settings.data_root)
    storage.initialize()
    storage.initialize()
    with storage.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert (
            connection.execute("SELECT count(*) FROM schema_migrations WHERE version=1").fetchone()[
                0
            ]
            == 1
        )
    assert storage.jobs_root.is_dir()


def test_single_instance_lock_has_process_lifetime(tmp_path):
    with instance_lock(tmp_path), pytest.raises(AlreadyRunningError), instance_lock(tmp_path):
        pytest.fail("A second launcher acquired the lock.")
    with instance_lock(tmp_path):
        pass


def test_missing_frontend_is_actionable(settings):
    app = create_app(replace(settings, frontend_dist=Path("/nonexistent/frontend")))
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        response = client.get("/")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "frontend_not_built"


def test_private_roots_cannot_enter_checkout(monkeypatch):
    repository = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("LOCALSCRIBE_DATA_ROOT", str(repository / "private-recordings"))
    with pytest.raises(ValueError, match="outside the repository"):
        Settings.from_env()

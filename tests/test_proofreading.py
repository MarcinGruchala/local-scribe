"""Conservative correction contracts use synthetic text and isolated stores."""

import pytest
from localscribe.proofreading import validate_response


def test_validated_suggestion_preserves_source_values():
    targets = [{"id": "a", "text": "hello world"}]
    changes = validate_response(
        {
            "changes": [
                {"id": "a", "old": "hello world", "new": "Hello, world.", "uncertain": False}
            ]
        },
        targets,
    )
    assert changes[0]["old"] == "hello world"
    assert changes[0]["new"] == "Hello, world."


@pytest.mark.parametrize(
    "change",
    [
        {
            "id": "missing",
            "old": "I paid 12 and did not leave",
            "new": "I paid 12 and did not leave.",
        },
        {"id": "a", "old": "wrong", "new": "I paid 12 and did not leave."},
        {"id": "a", "old": "I paid 12 and did not leave", "new": "I paid 13 and did not leave."},
        {"id": "a", "old": "I paid 12 and did not leave", "new": "I paid 12 and did leave."},
        {"id": "a", "old": "I paid 12 and did not leave", "new": "Zapłaciłem 12 i nie wyszedłem."},
    ],
)
def test_unsafe_output_is_rejected(change):
    with pytest.raises(ValueError):
        validate_response(
            {"changes": [{**change, "uncertain": False}]},
            [{"id": "a", "text": "I paid 12 and did not leave"}],
        )


# Shared fixtures intentionally shadow imported fixture names.
from localscribe.jobs import JobError
from localscribe.proofreading import LocalModel, Proofreading
from test_api import client  # noqa: F401
from test_transcript_history import recording


class ModelFixture:
    def __init__(self, callback=None):
        self.callback = callback
        self.calls = []

    def readiness(self):
        return {"ready": True, "model": "synthetic", "prompt": "test"}

    def generate(self, targets, context, glossary):
        self.calls.append((targets, context, glossary))
        if self.callback:
            return self.callback(targets)
        return {
            "changes": [
                {
                    "id": s["id"],
                    "old": s["text"],
                    "new": s["text"].strip().capitalize() + ".",
                    "uncertain": False,
                }
                for s in targets
            ]
        }


def setup_service(client, tmp_path):  # noqa: F811
    jobs = client.app.state.jobs
    job_id = recording(
        jobs,
        tmp_path,
        segments=[
            {
                "id": f"s{i}",
                "start": i * 2,
                "end": i * 2 + 1,
                "speakerId": "speaker1",
                "text": "hello world",
            }
            for i in range(20)
        ],
    )
    service = client.app.state.proofreading
    service.model = ModelFixture()
    return jobs, job_id, service


def test_pending_apply_restart_undo_redo_export_and_owned_deletion(client, tmp_path):  # noqa: F811
    from localscribe.exports import render

    jobs, job_id, service = setup_service(client, tmp_path)
    jobs.grouping_apply(job_id, 0)
    jobs.grouping_split(job_id, 1, "s1")
    original = jobs.transcript(job_id)
    immutable = next(jobs.directory(job_id).glob("attempts/*/published.json")).read_bytes()
    copies = (jobs.directory(job_id) / "transcript.txt").read_bytes()
    task = service.create(job_id, 2, glossary=["LocalScribe"])
    assert service.run_next()
    ready = service.get(job_id, task["id"])
    assert ready["status"] == "ready" and len(ready["suggestions"]) == 20
    assert jobs.transcript(job_id) == original
    assert (jobs.directory(job_id) / "transcript.txt").read_bytes() == copies
    saved = service.apply(job_id, task["id"], 2, ["s0", "s1"])
    assert saved["revision"] == 3 and saved["segments"][0]["editedText"] == "Hello world."
    assert saved["grouping"]["manualSplits"] == ["s1"]
    assert jobs.history(job_id)["operations"][-1]["type"] == "proofreading"
    service = Proofreading(jobs, ModelFixture())
    assert service.get(job_id)["status"] == "applied"
    undone = jobs.undo(job_id, 3)
    assert undone["segments"] == original["segments"]
    assert jobs.redo(job_id, 4)["segments"] == saved["segments"]
    assert next(jobs.directory(job_id).glob("attempts/*/published.json")).read_bytes() == immutable
    assert (jobs.directory(job_id) / "transcript.txt").read_text() == render(
        jobs.transcript(job_id), "txt"
    )[0]
    for before, after in zip(original["segments"], saved["segments"], strict=True):
        assert all(before[k] == after[k] for k in ("id", "speakerId", "start", "end", "text"))
    jobs.delete(job_id)
    with jobs.storage.connect() as db:
        assert db.execute("SELECT count(*) FROM proofreading_tasks").fetchone()[0] == 0


def test_cancel_drains_model_before_no_late_publication(client, tmp_path):  # noqa: F811
    jobs, job_id, service = setup_service(client, tmp_path)
    task = service.create(job_id, 0)

    def cancel(targets):
        service.cancel(job_id, task["id"])
        return {
            "changes": [
                {
                    "id": targets[0]["id"],
                    "old": targets[0]["text"],
                    "new": "Hello world.",
                    "uncertain": False,
                }
            ]
        }

    service.model = ModelFixture(cancel)
    assert service.run_next()
    assert service.get(job_id)["status"] == "cancelled"
    assert not service.get(job_id)["suggestions"]
    assert len(service.model.calls) == 1
    assert jobs.transcript(job_id)["revision"] == 0
    queued = service.create(job_id, 0)
    assert service.cancel(job_id, queued["id"])["status"] == "cancelled"
    assert not service.run_next()


@pytest.mark.parametrize(
    "mode",
    [
        "stale_during",
        "stale_after",
        "malformed",
        "duplicate",
        "context_id",
        "interrupted",
        "timeout",
    ],
)
def test_failures_cannot_apply_or_change_exports(client, tmp_path, mode):  # noqa: F811
    jobs, job_id, service = setup_service(client, tmp_path)
    task = service.create(job_id, 0, ["s1"])

    def response(targets):
        change = {
            "id": targets[0]["id"],
            "old": targets[0]["text"],
            "new": "Hello world.",
            "uncertain": False,
        }
        if mode == "stale_during":
            jobs.patch(job_id, 0, {"s0": "Manual draft saved"})
        if mode == "malformed":
            return {"changes": "bad"}
        if mode == "duplicate":
            return {"changes": [change, change]}
        if mode == "context_id":
            change["id"] = "s0"
        if mode == "timeout":
            raise TimeoutError()
        return {"changes": [change]}

    service.model = ModelFixture(response)
    if mode == "interrupted":
        with jobs.storage.connect() as db:
            db.execute("UPDATE proofreading_tasks SET status='running' WHERE id=?", (task["id"],))
        service.recover()
    else:
        service.run_next()
    if mode == "stale_after":
        jobs.patch(job_id, 0, {"s0": "Manual draft saved"})
    with pytest.raises(JobError):
        service.apply(job_id, task["id"], jobs.transcript(job_id)["revision"], ["s1"])
    assert jobs.transcript(job_id)["segments"][1]["editedText"] is None
    assert not any(op["type"] == "proofreading" for op in jobs.history(job_id)["operations"])


def test_http_selection_glossary_reject_and_guarded_accept(client, tmp_path):  # noqa: F811
    jobs, job_id, service = setup_service(client, tmp_path)
    path = f"/api/jobs/{job_id}/proofreading"
    assert client.get("/api/proofreading/readiness").json()["ready"]
    assert (
        client.post(path, json={"expectedRevision": 0, "segmentIds": ["s1", "s3"]}).status_code
        == 422
    )
    assert (
        client.post(path, json={"expectedRevision": 0, "glossary": ["a" * 81]}).status_code == 422
    )
    response = client.post(
        path, json={"expectedRevision": 0, "segmentIds": ["s1", "s2"], "glossary": ["LocalScribe"]}
    )
    assert response.status_code == 202
    assert client.post(path, json={"expectedRevision": 0}).status_code == 409
    service.run_next()
    assert service.model.calls[0][2] == ["LocalScribe"]
    assert all(t["id"] in ["s1", "s2"] for t in service.model.calls[0][0])
    task = response.json()["id"]
    assert (
        client.post(
            path + f"/{task}/reject", json={"expectedRevision": 0, "segmentIds": ["s1"]}
        ).status_code
        == 200
    )
    assert (
        client.post(
            path + f"/{task}/apply", json={"expectedRevision": 0, "segmentIds": ["s1"]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            path + f"/{task}/apply",
            json={"expectedRevision": 0, "segmentIds": ["s2"]},
            headers={"X-LocalScribe-Token": "wrong"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            path + f"/{task}/apply", json={"expectedRevision": 0, "segmentIds": ["s2"]}
        ).status_code
        == 200
    )
    assert (
        client.post(
            path + f"/{task}/apply", json={"expectedRevision": 1, "segmentIds": ["s2"]}
        ).status_code
        == 409
    )
    assert jobs.transcript(job_id)["segments"][1]["editedText"] is None


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:1234",
        "http://localhost:1234",
        "http://example.com",
        "http://127.0.0.1.evil.test",
        "http://user:pass@127.0.0.1:1234",
        "http://127.0.0.1:1234/redirect",
        "http://127.0.0.1:1234?target=x",
    ],
)
def test_model_rejects_nonliteral_or_ambiguous_targets(monkeypatch, url):
    monkeypatch.setenv("LOCALSCRIBE_LM_URL", url)
    with pytest.raises(ValueError):
        LocalModel()


def test_missing_model_does_not_disable_manual_work(client, tmp_path, monkeypatch):  # noqa: F811
    jobs, job_id, service = setup_service(client, tmp_path)
    service.model = None
    monkeypatch.delenv("LOCALSCRIBE_LM_MODEL", raising=False)
    assert not service.readiness()["ready"]
    with pytest.raises(JobError):
        service.create(job_id, 0)
    assert jobs.patch(job_id, 0, {"s0": "Manual correction"})["revision"] == 1


def test_uncertain_suggestion_requires_listening(client, tmp_path):  # noqa: F811
    jobs, job_id, service = setup_service(client, tmp_path)
    service.model = ModelFixture(
        lambda targets: {
            "changes": [
                {
                    "id": targets[0]["id"],
                    "old": targets[0]["text"],
                    "new": targets[0]["text"],
                    "uncertain": True,
                }
            ]
        }
    )
    task = service.create(job_id, 0, ["s0"])
    service.run_next()
    with pytest.raises(JobError):
        service.apply(job_id, task["id"], 0, ["s0"])
    assert jobs.transcript(job_id)["revision"] == 0


def test_grammar_and_whitespace_only_changes_are_not_corrections():
    targets = [{"id": "a", "text": " one day"}]
    with pytest.raises(ValueError):
        validate_response(
            {"changes": [{"id": "a", "old": " one day", "new": " one days", "uncertain": False}]},
            targets,
        )
    assert (
        validate_response(
            {"changes": [{"id": "a", "old": " one day", "new": "one day", "uncertain": False}]},
            targets,
        )
        == []
    )


def test_idle_store_does_not_starve_another_store_and_cancel_drains(tmp_path):
    import threading

    from localscribe.jobs import Jobs
    from localscribe.storage import Storage
    from localscribe.worker import Worker
    from test_worker import enqueue, wait_for

    first = Jobs(Storage(tmp_path / "idle"))
    first.initialize()
    second = Jobs(Storage(tmp_path / "busy"))
    second.initialize()
    idle = Worker(first, tmp_path / "models", poll_interval=0.02)
    job_id = recording(second, tmp_path)
    entered, release = threading.Event(), threading.Event()

    def blocked_response(targets):
        entered.set()
        assert release.wait(5)
        return {"changes": []}

    service = Proofreading(second, ModelFixture(blocked_response))
    task = service.create(job_id, 0, ["s0"])
    queued = enqueue(second, tmp_path, "queued.wav")
    busy = Worker(second, tmp_path / "models", proofreading=service, poll_interval=0.02)
    idle.start()
    busy.start()
    try:
        assert entered.wait(4), "The idle store retained the heavy lock."
        service.cancel(job_id, task["id"])
        assert second.get(queued["id"])["status"] == "queued"
        second.patch(job_id, 0, {"s1": "Manual save while inference is blocked"})
        assert service.get(job_id)["status"] == "cancelling"
        release.set()
        wait_for(lambda: service.get(job_id)["status"] == "cancelled")
        assert not service.get(job_id)["suggestions"]
    finally:
        release.set()
        busy.stop()
        idle.stop()


def test_uncertain_transport_completion_keeps_shared_barrier(tmp_path, monkeypatch):
    from localscribe import heavy

    monkeypatch.setattr(heavy, "MARKER", tmp_path / "marker.json")
    monkeypatch.setattr(heavy, "LOCK", tmp_path / "lock")

    class Adapter:
        endpoint = "http://127.0.0.1:1234"
        model = "owned-test"

        def request(self, *args):
            return {"models": [{"loaded_instances": [{"id": "owned-test"}]}]}

    adapter = Adapter()
    with pytest.raises(TimeoutError), heavy.uncertain_model(adapter):
        raise TimeoutError()
    assert heavy.MARKER.exists()
    monkeypatch.setattr("localscribe.proofreading.LocalModel", lambda: adapter)
    with heavy.heavy_slot() as acquired:
        assert not acquired
    adapter.request = lambda *args: {"models": []}
    with heavy.heavy_slot() as acquired:
        assert acquired
    assert not heavy.MARKER.exists()


@pytest.mark.parametrize(
    "status,raw", [(302, b"{}"), (401, b"{}"), (200, b"bad json"), (200, b"x" * 256001)]
)
def test_adapter_refuses_redirect_auth_malformed_and_oversized_without_proxy(
    monkeypatch, status, raw
):
    import http.client

    captured = []

    class Response:
        def read(self, size):
            assert size == 256001
            return raw

    class Connection:
        def __init__(self, host, port, timeout):
            captured.append((host, port, timeout))

        def request(self, *args, **kwargs):
            captured.append(args)

        def getresponse(self):
            response = Response()
            response.status = status
            return response

        def close(self):
            pass

    monkeypatch.setenv("HTTP_PROXY", "http://remote.invalid:9000")
    monkeypatch.setenv("LOCALSCRIBE_LM_URL", "http://127.0.0.1:1234")
    monkeypatch.setattr(http.client, "HTTPConnection", Connection)
    with pytest.raises(ValueError):
        LocalModel().request("GET", "/api/v1/models")
    assert captured[0][0] == "127.0.0.1" and len(captured) == 2


@pytest.mark.parametrize(
    "old,new",
    [
        ("We can’t leave", "We can leave"),
        ("I couldn’t go", "I could go"),
        ("Anna went home", "Ania went home"),
    ],
)
def test_typographic_negation_and_initial_names_are_protected(old, new):
    with pytest.raises(ValueError):
        validate_response(
            {"changes": [{"id": "a", "old": old, "new": new, "uncertain": False}]},
            [{"id": "a", "text": old}],
        )


@pytest.mark.parametrize(
    "response",
    [
        None,
        {},
        {"choices": [{"finish_reason": "stop", "message": None}]},
        {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}], "usage": None},
        {"choices": "invalid"},
    ],
)
def test_malformed_nested_completion_is_a_controlled_failure(monkeypatch, response):
    model = LocalModel()
    model.request = lambda *args: response
    with pytest.raises((ValueError, TypeError, KeyError)):
        model.generate([], [], [])


def test_transient_proofreading_database_error_does_not_stop_worker(tmp_path):
    import sqlite3
    import threading

    from localscribe.jobs import Jobs
    from localscribe.storage import Storage
    from localscribe.worker import Worker
    from test_worker import wait_for

    jobs = Jobs(Storage(tmp_path / "store"))
    jobs.initialize()
    service = Proofreading(jobs, ModelFixture())
    called = threading.Event()

    def run_next(*args):
        called.set()
        raise sqlite3.OperationalError("database is locked")

    service.run_next = run_next
    worker = Worker(jobs, tmp_path / "models", proofreading=service)
    worker.start()
    try:
        wait_for(called.is_set)
        assert worker.alive
    finally:
        worker.stop()


def test_pipeline_child_retains_shared_lock_after_launcher_crash(tmp_path):
    import os
    import subprocess
    import sys

    from localscribe import heavy
    from test_worker import wait_for

    marker = tmp_path / "entered"
    release = tmp_path / "release"
    child = """import pathlib,sys,time
pathlib.Path(sys.argv[1]).touch()
while not pathlib.Path(sys.argv[2]).exists(): time.sleep(.01)
"""
    # The parent exits without finally/unlock, exactly like a killed launcher.
    parent = """import os,subprocess,sys
from localscribe.heavy import heavy_slot
with heavy_slot() as descriptor:
    assert descriptor
    subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2],sys.argv[3]],pass_fds=(descriptor,))
    os._exit(0)
"""
    env = {
        **os.environ,
        "PYTHONPATH": str(
            __import__("pathlib").Path(__file__).resolve().parents[1] / "backend/src"
        ),
    }
    subprocess.run(
        [sys.executable, "-c", parent, child, str(marker), str(release)], env=env, check=True
    )
    try:
        wait_for(marker.exists)
        with heavy.heavy_slot() as acquired:
            assert not acquired
    finally:
        release.touch()

    def available():
        with heavy.heavy_slot() as acquired:
            return bool(acquired)

    wait_for(available)

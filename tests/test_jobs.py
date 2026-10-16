"""Deterministic persistence, publication races, edits, and deletion checks."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from localscribe.jobs import JobError, Jobs
from localscribe.storage import Storage


@pytest.fixture
def jobs(tmp_path):
    repository = Jobs(Storage(tmp_path / "store"))
    repository.initialize()
    return repository


def queued(jobs, tmp_path, name="recording.wav"):
    source = tmp_path / name
    source.write_bytes(b"original media bytes")
    return jobs.create_import(
        source, name, {"duration": 1.0, "sizeBytes": source.stat().st_size}, {}
    )


def result(jobs, job):
    payload = {
        "jobId": job["id"],
        "duration": 1,
        "language": "en",
        "requestedLanguage": "auto",
        "detectedLanguage": "en",
        "options": job["options"],
        "originalText": "Hello",
        "segments": [{"id": "s1", "start": 0, "end": 1, "speakerId": "speaker1", "text": "Hello"}],
        "speakers": [{"id": "speaker1", "displayName": "Speaker 1"}],
        "modelSegments": [],
        "words": [],
        "regularTurns": [],
        "exclusiveTurns": [],
        "warnings": [],
        "provenance": {"test": True},
    }
    path = jobs.directory(job["id"]) / "attempts" / str(job["attempt"]) / "result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return path


def completed(jobs, tmp_path, name="recording.wav"):
    job = queued(jobs, tmp_path, name)
    job = jobs.claim()
    assert jobs.publish(job["id"], job["attempt"], result(jobs, job))
    return jobs.get(job["id"])


def test_fifo_claim_is_transactional_and_attempt_options_immutable(jobs, tmp_path):
    first = queued(jobs, tmp_path, "a.wav")
    second = queued(jobs, tmp_path, "b.wav")
    with ThreadPoolExecutor(2) as executor:
        claims = list(executor.map(lambda _: jobs.claim(), range(2)))
    active = [claim for claim in claims if claim]
    assert len(active) == 1 and active[0]["id"] == first["id"]
    jobs.fail(first["id"], 1, "test_failure", "Test failure.")
    assert jobs.claim()["id"] == second["id"]
    with jobs.storage.connect() as db:
        assert (
            json.loads(
                db.execute(
                    "SELECT options FROM attempts WHERE job_id=?", (first["id"],)
                ).fetchone()[0]
            )
            == first["options"]
        )


def test_cancel_retry_and_late_publish(jobs, tmp_path):
    job = queued(jobs, tmp_path)
    assert jobs.cancel(job["id"])["status"] == "cancelled"
    assert jobs.cancel(job["id"])["status"] == "cancelled"
    jobs.retry(job["id"])
    with pytest.raises(JobError, match="Only failed"):
        jobs.retry(job["id"])
    active = jobs.claim()
    assert active["attempt"] == 1
    path = result(jobs, active)
    jobs.cancel(job["id"])
    assert not jobs.publish(job["id"], 1, path)
    assert not path.exists()
    jobs.finish_cancel(job["id"], 1)
    jobs.retry(job["id"])
    retry = jobs.claim()
    assert retry["attempt"] == 2
    assert not jobs.publish(job["id"], 1, result(jobs, active))
    assert jobs.get(job["id"])["status"] == "preparing"


def test_cancel_publish_race_has_one_transactional_winner(jobs, tmp_path):
    job = queued(jobs, tmp_path)
    job = jobs.claim()
    path = result(jobs, job)
    barrier = threading.Barrier(2)

    def publish():
        barrier.wait()
        return jobs.publish(job["id"], 1, path)

    def cancel():
        barrier.wait()
        return jobs.cancel(job["id"])

    with ThreadPoolExecutor(2) as executor:
        future_publish = executor.submit(publish)
        future_cancel = executor.submit(cancel)
        published, cancelled = future_publish.result(), future_cancel.result()
    assert jobs.get(job["id"])["status"] == ("completed" if published else "cancelling")
    assert cancelled["status"] == ("completed" if published else "cancelling")
    if published:
        assert jobs.transcript(job["id"])["originalText"] == "Hello"


def test_failed_publication_never_completes(jobs, tmp_path, monkeypatch):
    job = queued(jobs, tmp_path)
    job = jobs.claim()
    path = result(jobs, job)

    def fail_rename(*args):
        raise OSError("injected disk failure")

    monkeypatch.setattr("localscribe.jobs.os.replace", fail_rename)
    with pytest.raises(OSError):
        jobs.publish(job["id"], 1, path)
    assert jobs.get(job["id"])["status"] == "preparing"
    with pytest.raises(JobError):
        jobs.transcript(job["id"])


def test_recovery_preserves_queue_completed_and_exposes_interruption(jobs, tmp_path):
    done = completed(jobs, tmp_path, "done.wav")
    interrupted = queued(jobs, tmp_path, "interrupted.wav")
    active = jobs.claim()
    waiting = queued(jobs, tmp_path, "waiting.wav")
    orphan = result(jobs, active).with_name("published.json")
    orphan.write_text("uncommitted publication")
    (jobs.storage.imports_root / "abandoned.partial").write_text("unfinished upload")
    abandoned_job = jobs.storage.jobs_root / ("a" * 32)
    abandoned_job.mkdir()
    jobs.recover()
    assert jobs.get(done["id"])["status"] == "completed"
    assert jobs.transcript(done["id"])["originalText"] == "Hello"
    assert jobs.get(interrupted["id"])["failure"]["code"] == "interrupted"
    assert jobs.get(waiting["id"])["status"] == "queued"
    assert not orphan.exists() and not abandoned_job.exists()
    assert list(jobs.storage.imports_root.iterdir()) == []
    jobs.retry(interrupted["id"])


def test_missing_published_file_recovery_is_visible(jobs, tmp_path):
    done = completed(jobs, tmp_path)
    with jobs.storage.connect() as db:
        reference = db.execute("SELECT result FROM jobs WHERE id=?", (done["id"],)).fetchone()[0]
    (jobs.directory(done["id"]) / reference).unlink()
    jobs.recover()
    assert jobs.get(done["id"])["failure"]["code"] == "missing_result"


def test_edits_are_atomic_revisioned_and_separate_from_inference(jobs, tmp_path):
    done = completed(jobs, tmp_path)
    immutable = next(jobs.directory(done["id"]).glob("attempts/*/published.json"))
    before = immutable.read_bytes()
    edited = jobs.patch(done["id"], 0, {"s1": "Cześć"}, {"speaker1": "Marcin"})
    assert edited["revision"] == 1 and edited["segments"][0]["editedText"] == "Cześć"
    assert edited["segments"][0]["text"] == "Hello"
    assert edited["speakers"][0]["displayName"] == "Marcin"
    assert immutable.read_bytes() == before
    restarted = Jobs(Storage(jobs.storage.root))
    assert restarted.transcript(done["id"]) == edited
    for segments, speakers in [({"unknown": "text"}, {}), ({}, {"speaker1": " "}), ({"s1": 2}, {})]:
        with pytest.raises(JobError) as error:
            jobs.patch(done["id"], 1, segments, speakers)
        assert error.value.status == 422
        assert jobs.transcript(done["id"]) == edited
    with pytest.raises(JobError) as error:
        jobs.patch(done["id"], 0, {"s1": "stale"})
    assert error.value.code == "stale_revision"


def test_delete_owns_all_files_preserves_other_jobs_and_models(jobs, tmp_path):
    done = completed(jobs, tmp_path, "done.wav")
    other = queued(jobs, tmp_path, "other.wav")
    shared = jobs.storage.root / "models" / "weights"
    shared.parent.mkdir()
    shared.write_bytes(b"shared")
    (jobs.directory(done["id"]) / "normalized.wav").write_bytes(b"wav")
    jobs.patch(done["id"], 0, {"s1": "edited"})
    jobs.delete(done["id"])
    assert not jobs.directory(done["id"]).exists()
    assert shared.read_bytes() == b"shared"
    assert jobs.get(other["id"])["status"] == "queued"
    with pytest.raises(JobError) as error:
        jobs.delete(done["id"])
    assert error.value.status == 404
    with pytest.raises(JobError) as error:
        jobs.delete(other["id"])
    assert error.value.status == 409


def test_partial_delete_is_visible_and_recovered(jobs, tmp_path, monkeypatch):
    done = completed(jobs, tmp_path)
    real_remove = __import__("shutil").rmtree

    def fail_remove(path):
        raise PermissionError("injected permission failure")

    monkeypatch.setattr("localscribe.jobs.shutil.rmtree", fail_remove)
    with pytest.raises(JobError) as error:
        jobs.delete(done["id"])
    assert error.value.code == "deletion_failed"
    assert jobs.get(done["id"])["status"] == "deletion_failed"
    with pytest.raises(JobError):
        jobs.retry(done["id"])
    monkeypatch.setattr("localscribe.jobs.shutil.rmtree", real_remove)
    jobs.recover()
    with pytest.raises(JobError):
        jobs.get(done["id"])


def test_delete_retry_race_cannot_remove_an_enqueued_job(jobs, tmp_path):
    job = queued(jobs, tmp_path)
    jobs.cancel(job["id"])
    barrier = threading.Barrier(2)

    def operation(method):
        barrier.wait()
        try:
            method(job["id"])
            return True
        except JobError:
            return False

    with ThreadPoolExecutor(2) as executor:
        delete = executor.submit(operation, jobs.delete)
        retry = executor.submit(operation, jobs.retry)
        assert delete.result() != retry.result()
    if jobs.directory(job["id"]).exists():
        assert jobs.get(job["id"])["status"] == "queued"


def test_unknown_ids_cannot_escape_owned_storage(jobs):
    for job_id in ("../../etc", "z" * 32, "/etc/passwd", "a" * 32):
        with pytest.raises(JobError) as error:
            jobs.get(job_id)
        assert error.value.status == 404


def test_warnings_migrate_once_and_status_never_reads_transcript(jobs, tmp_path, monkeypatch):
    from pathlib import Path

    done = completed(jobs, tmp_path)
    immutable = next(jobs.directory(done["id"]).glob("attempts/*/published.json"))
    payload = json.loads(immutable.read_text())
    payload["warnings"] = [{"code": "legacy_warning", "message": "Legacy warning."}]
    immutable.write_text(json.dumps(payload))
    with jobs.storage.connect() as db:
        db.execute("ALTER TABLE jobs DROP COLUMN warnings")
        db.execute("DELETE FROM schema_migrations WHERE version=3")
    jobs.initialize()

    def forbidden_read(*args, **kwargs):
        raise AssertionError("Status/history must not load complete transcript files.")

    monkeypatch.setattr(Path, "read_text", forbidden_read)
    assert jobs.get(done["id"])["warnings"] == payload["warnings"]
    assert jobs.list()["jobs"][0]["warnings"] == payload["warnings"]
    # Reinitializing an already migrated database does not read result files.
    jobs.initialize()


def test_publish_persists_small_warning_metadata(jobs, tmp_path):
    queued(jobs, tmp_path)
    job = jobs.claim()
    output = result(jobs, job)
    payload = json.loads(output.read_text())
    payload["warnings"] = [
        {"code": "diarization_failed", "message": "Speaker labels are unavailable."}
    ]
    output.write_text(json.dumps(payload))
    jobs.publish(job["id"], job["attempt"], output)
    assert jobs.get(job["id"])["warnings"] == payload["warnings"]


PINNED_MODELS = {
    "fast": {"repo": "fixture/asr", "revision": "a" * 40},
    "diarization": {"repo": "fixture/diarization", "revision": "b" * 40},
}


def pinned_job(jobs, tmp_path):
    source = tmp_path / "pinned-source.wav"
    source.write_bytes(b"original media bytes")
    return jobs.create_import(
        source, "pinned-source.wav", {"duration": 1, "modelSettings": PINNED_MODELS}, {}
    )


def pinned_result(jobs, job):
    path = result(jobs, job)
    payload = json.loads(path.read_text())
    payload["provenance"] = {
        "asr": dict(PINNED_MODELS["fast"]),
        "diarization": dict(PINNED_MODELS["diarization"]),
    }
    path.write_text(json.dumps(payload))
    return path


def test_pinned_model_references_survive_retry_and_restart(jobs, tmp_path):
    original = pinned_job(jobs, tmp_path)
    claimed = jobs.claim()
    assert claimed["modelSettings"] == PINNED_MODELS
    jobs.fail(original["id"], 1, "interrupted", "Retry this job.")
    jobs.retry(original["id"])
    restarted = Jobs(Storage(jobs.storage.root))
    restarted.initialize()
    restarted.recover()
    retry = restarted.claim()
    assert retry["attempt"] == 2 and retry["modelSettings"] == original["modelSettings"]
    assert retry["options"] == original["options"]
    assert restarted.publish(retry["id"], 2, pinned_result(restarted, retry))


@pytest.mark.parametrize(
    "engine,field",
    [("asr", "revision"), ("asr", "repo"), ("diarization", "revision"), ("diarization", "repo")],
)
def test_mismatched_provenance_cannot_publish(jobs, tmp_path, engine, field):
    pinned_job(jobs, tmp_path)
    claimed = jobs.claim()
    path = pinned_result(jobs, claimed)
    payload = json.loads(path.read_text())
    payload["provenance"][engine][field] = "changed"
    path.write_text(json.dumps(payload))
    with pytest.raises(JobError) as error:
        jobs.publish(claimed["id"], claimed["attempt"], path)
    assert error.value.code == "model_revision_changed"
    assert jobs.get(claimed["id"])["status"] == "preparing"
    assert not path.with_name("published.json").exists()
    with pytest.raises(JobError):
        jobs.transcript(claimed["id"])


@pytest.mark.parametrize("status", ["failed", "disabled"])
def test_degraded_or_disabled_diarization_does_not_claim_model_success(jobs, tmp_path, status):
    pinned_job(jobs, tmp_path)
    claimed = jobs.claim()
    path = pinned_result(jobs, claimed)
    payload = json.loads(path.read_text())
    payload["provenance"]["diarization"] = {"status": status}
    path.write_text(json.dumps(payload))
    assert jobs.publish(claimed["id"], claimed["attempt"], path)


def test_incomplete_pinned_map_cannot_bypass_publication_checks(jobs, tmp_path):
    source = tmp_path / "source.wav"
    source.write_bytes(b"original")
    jobs.create_import(source, "source.wav", {"duration": 1, "modelSettings": {}}, {})
    claimed = jobs.claim()
    with pytest.raises(JobError) as error:
        jobs.publish(claimed["id"], claimed["attempt"], result(jobs, claimed))
    assert error.value.code == "model_revision_changed"

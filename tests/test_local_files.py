"""Saved-revision copies, isolated failure, startup repair, and deletion races."""

import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from localscribe import local_files
from localscribe.exports import render
from localscribe.jobs import JobError, Jobs
from localscribe.storage import Storage
from test_jobs import completed, queued, result


@pytest.fixture
def jobs(tmp_path):
    service = Jobs(Storage(tmp_path / "store"))
    service.initialize()
    return service


def assert_saved_files(jobs, job_id):
    job = jobs.get(job_id)
    saved = jobs.transcript(job_id)
    directory = jobs.directory(job_id)
    assert job["localFiles"]["status"] == "ready"
    assert job["localFiles"]["directory"] == str(directory)
    assert job["localFiles"]["revision"] == saved["revision"]
    assert job["localFiles"]["savedRevision"] == saved["revision"]
    assert local_files.matches_saved_revision(directory, job_id, job["attempt"], saved["revision"])
    for format in local_files.FORMATS:
        path = directory / f"transcript.{format}"
        assert path.read_text() == render(saved, format)[0]
        assert str(path) in job["localFiles"]["files"]
    assert not list(directory.glob(".*.pending"))


def test_publish_and_edit_export_only_saved_text_and_names(jobs, tmp_path):
    done = completed(jobs, tmp_path)
    job_id = done["id"]
    assert_saved_files(jobs, job_id)
    immutable = next(jobs.directory(job_id).glob("attempts/*/published.json"))
    before = immutable.read_bytes()
    saved = jobs.patch(job_id, 0, {"s1": "Cześć"}, {"speaker1": "Marcin"})
    assert saved["revision"] == 1
    assert_saved_files(jobs, job_id)
    assert immutable.read_bytes() == before
    assert "Marcin: Cześć" in (jobs.directory(job_id) / "transcript.txt").read_text()
    copy = json.loads((jobs.directory(job_id) / "transcript.json").read_text())
    assert copy["segments"][0]["text"] == "Hello"
    assert copy["segments"][0]["editedText"] == "Cześć"
    assert jobs.list()["jobs"][0]["localFiles"] == jobs.get(job_id)["localFiles"]


def test_publish_copy_failure_keeps_completed_canonical_result(jobs, tmp_path, monkeypatch):
    queued(jobs, tmp_path)
    active = jobs.claim()

    def broken_copy(*args):
        raise OSError("injected private detail")

    monkeypatch.setattr(local_files, "write_saved_revision", broken_copy)
    assert jobs.publish(active["id"], 1, result(jobs, active))
    job = jobs.get(active["id"])
    assert job["status"] == "completed" and job["failure"] is None
    assert jobs.transcript(active["id"])["originalText"] == "Hello"
    assert job["localFiles"]["status"] == "error"
    assert job["localFiles"]["error"]["code"] == "local_files_failed"
    assert "injected private detail" not in json.dumps(job)


def test_edit_copy_failure_never_reports_failed_save_and_can_retry(jobs, tmp_path, monkeypatch):
    done = completed(jobs, tmp_path)
    real_write = local_files.write_saved_revision

    def broken_copy(*args):
        raise RuntimeError("private transcript content")

    monkeypatch.setattr(local_files, "write_saved_revision", broken_copy)
    saved = jobs.patch(done["id"], 0, {"s1": "Saved despite copy failure"})
    assert saved["revision"] == 1
    assert jobs.transcript(done["id"])["segments"][0]["editedText"] == "Saved despite copy failure"
    job = jobs.get(done["id"])
    assert job["status"] == "completed" and job["error"] is None
    assert job["localFiles"]["status"] == "error"
    assert job["localFiles"]["revision"] == 0 and job["localFiles"]["savedRevision"] == 1
    assert "private transcript content" not in json.dumps(job)
    monkeypatch.setattr(local_files, "write_saved_revision", real_write)
    assert jobs.sync_local_files(done["id"])["localFiles"]["status"] == "ready"
    assert_saved_files(jobs, done["id"])


def test_partial_copy_failure_invalidates_manifest_and_startup_repairs(jobs, tmp_path, monkeypatch):
    done = completed(jobs, tmp_path)
    directory = jobs.directory(done["id"])
    real_replace = local_files.os.replace

    def fail_second_file(source, target):
        if Path(target) == directory / "transcript.srt":
            raise OSError("injected filesystem failure")
        return real_replace(source, target)

    monkeypatch.setattr(local_files.os, "replace", fail_second_file)
    saved = jobs.patch(done["id"], 0, {"s1": "New saved text"})
    assert saved["revision"] == 1 and jobs.get(done["id"])["localFiles"]["status"] == "error"
    assert "New saved text" in (directory / "transcript.txt").read_text()
    assert "Hello" in (directory / "transcript.srt").read_text()
    assert not (directory / local_files.MANIFEST).exists()
    assert not list(directory.glob(".*.pending"))
    monkeypatch.setattr(local_files.os, "replace", real_replace)
    restarted = Jobs(Storage(jobs.storage.root))
    restarted.initialize()
    restarted.recover()
    assert_saved_files(restarted, done["id"])


@pytest.mark.parametrize(
    "damage",
    [
        "missing_txt",
        "corrupt_json",
        "modified_vtt",
        "invalid_manifest_json",
        "manifest_wrong_type",
        "manifest_wrong_revision",
        "manifest_wrong_hash",
    ],
)
def test_startup_repairs_missing_corrupt_or_manually_modified_copies(jobs, tmp_path, damage):
    done = completed(jobs, tmp_path)
    directory = jobs.directory(done["id"])
    manifest_path = directory / local_files.MANIFEST
    if damage == "missing_txt":
        (directory / "transcript.txt").unlink()
    elif damage == "corrupt_json":
        (directory / "transcript.json").write_text("{broken")
    elif damage == "modified_vtt":
        (directory / "transcript.vtt").write_text("manual filesystem edit")
    elif damage == "invalid_manifest_json":
        manifest_path.write_text("{broken")
    elif damage == "manifest_wrong_type":
        manifest_path.write_text("[]")
    else:
        manifest = json.loads(manifest_path.read_text())
        if damage == "manifest_wrong_revision":
            manifest["revision"] = 20
        else:
            manifest["files"]["transcript.txt"]["sha256"] = "a" * 64
        manifest_path.write_text(json.dumps(manifest))
    assert not local_files.matches_saved_revision(directory, done["id"], 1, 0)
    jobs.recover()
    assert_saved_files(jobs, done["id"])
    assert jobs.transcript(done["id"])["segments"][0]["editedText"] is None


def test_old_save_copy_request_cannot_overwrite_newer_saved_revision(jobs, tmp_path, monkeypatch):
    done = completed(jobs, tmp_path)
    older_committed, release_older = threading.Event(), threading.Event()
    real_sync = jobs._sync_local_files_after_commit

    def delayed_sync(job_id):
        if threading.current_thread().name.startswith("older-save"):
            older_committed.set()
            assert release_older.wait(5)
        real_sync(job_id)

    monkeypatch.setattr(jobs, "_sync_local_files_after_commit", delayed_sync)
    with ThreadPoolExecutor(1, thread_name_prefix="older-save") as executor:
        older = executor.submit(jobs.patch, done["id"], 0, {"s1": "Older saved edit"})
        try:
            assert older_committed.wait(5)
            assert jobs.get(done["id"])["revision"] == 1
            assert jobs.get(done["id"])["localFiles"]["status"] == "pending"
            newer = jobs.patch(done["id"], 1, {"s1": "Newest saved edit"})
            assert newer["revision"] == 2
        finally:
            release_older.set()
        assert older.result(timeout=5)["revision"] == 1
    assert_saved_files(jobs, done["id"])
    copy = json.loads((jobs.directory(done["id"]) / "transcript.json").read_text())
    assert copy["revision"] == 2 and copy["segments"][0]["editedText"] == "Newest saved edit"


def test_copy_transaction_serializes_delete_and_never_resurrects_job(jobs, tmp_path, monkeypatch):
    done = completed(jobs, tmp_path)
    entered, release, delete_started = threading.Event(), threading.Event(), threading.Event()
    real_write = local_files.write_saved_revision

    def paused_copy(*args):
        entered.set()
        assert release.wait(5)
        return real_write(*args)

    def delete():
        delete_started.set()
        jobs.delete(done["id"])

    monkeypatch.setattr(local_files, "write_saved_revision", paused_copy)
    with ThreadPoolExecutor(2) as executor:
        copy = executor.submit(jobs.sync_local_files, done["id"])
        try:
            assert entered.wait(5)
            removed = executor.submit(delete)
            assert delete_started.wait(5)
            assert not removed.done()
        finally:
            release.set()
        assert copy.result(timeout=5)["localFiles"]["status"] == "ready"
        removed.result(timeout=5)
    assert not jobs.directory(done["id"]).exists()
    with pytest.raises(JobError) as error:
        jobs.get(done["id"])
    assert error.value.status == 404


def test_delete_winning_before_post_commit_copy_does_not_fail_saved_edit(
    jobs, tmp_path, monkeypatch
):
    done = completed(jobs, tmp_path)
    committed, release = threading.Event(), threading.Event()
    real_sync = jobs._sync_local_files_after_commit

    def paused_after_commit(job_id):
        committed.set()
        assert release.wait(5)
        real_sync(job_id)

    monkeypatch.setattr(jobs, "_sync_local_files_after_commit", paused_after_commit)
    with ThreadPoolExecutor(1) as executor:
        saved = executor.submit(jobs.patch, done["id"], 0, {"s1": "Saved before deletion"})
        try:
            assert committed.wait(5)
            jobs.delete(done["id"])
        finally:
            release.set()
        assert saved.result(timeout=5)["revision"] == 1
    assert not jobs.directory(done["id"]).exists()


def test_deletion_tombstone_prevents_copy_creation(jobs, tmp_path, monkeypatch):
    done = completed(jobs, tmp_path)
    entered, release = threading.Event(), threading.Event()
    real_remove = __import__("shutil").rmtree

    def paused_remove(path):
        entered.set()
        assert release.wait(5)
        real_remove(path)

    monkeypatch.setattr("localscribe.jobs.shutil.rmtree", paused_remove)
    with ThreadPoolExecutor(1) as executor:
        deletion = executor.submit(jobs.delete, done["id"])
        try:
            assert entered.wait(5)
            with pytest.raises(JobError) as error:
                jobs.sync_local_files(done["id"])
            assert error.value.code == "transcript_unavailable"
        finally:
            release.set()
        deletion.result(timeout=5)
    assert not jobs.directory(done["id"]).exists()


def test_copy_database_failure_leaves_pending_saved_revision_repairable(
    jobs, tmp_path, monkeypatch
):
    done = completed(jobs, tmp_path)
    real_sync = jobs.sync_local_files

    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError("injected busy database")

    monkeypatch.setattr(jobs, "sync_local_files", unavailable)
    assert jobs.patch(done["id"], 0, {"s1": "Persisted edit"})["revision"] == 1
    assert jobs.get(done["id"])["localFiles"]["status"] == "pending"
    monkeypatch.setattr(jobs, "sync_local_files", real_sync)
    jobs.recover()
    assert_saved_files(jobs, done["id"])


def test_migration_backfills_existing_published_jobs_without_resetting_edits(jobs, tmp_path):
    done = completed(jobs, tmp_path)
    jobs.patch(done["id"], 0, {"s1": "Existing saved edit"})
    for filename in (*local_files.FILENAMES, local_files.MANIFEST):
        (jobs.directory(done["id"]) / filename).unlink()
    with jobs.storage.connect() as db:
        db.execute("ALTER TABLE jobs DROP COLUMN local_files")
        db.execute("DELETE FROM schema_migrations WHERE version=4")
    jobs.initialize()
    jobs.recover()
    assert_saved_files(jobs, done["id"])
    assert jobs.transcript(done["id"])["segments"][0]["editedText"] == "Existing saved edit"


def test_unpublished_jobs_and_rejected_late_results_have_no_readable_transcript_files(
    jobs, tmp_path
):
    job = queued(jobs, tmp_path)
    assert job["localFiles"]["status"] == "missing"
    with pytest.raises(JobError):
        jobs.sync_local_files(job["id"])
    active = jobs.claim()
    staged = result(jobs, active)
    jobs.cancel(job["id"])
    assert not jobs.publish(job["id"], 1, staged)
    assert not any((jobs.directory(job["id"]) / name).exists() for name in local_files.FILENAMES)


def test_canonical_publish_and_edit_are_committed_before_copy_io(jobs, tmp_path, monkeypatch):
    queued(jobs, tmp_path)
    active = jobs.claim()
    observed = []
    real_write = local_files.write_saved_revision

    def inspect_saved_commit(directory, transcript, attempt):
        # A separate connection must already see the saved revision while the copy
        # transaction is writing. This also verifies WAL status reads stay responsive.
        state = jobs.get(active["id"])
        canonical = jobs.transcript(active["id"])
        observed.append((state["status"], state["localFiles"]["status"], canonical["revision"]))
        assert canonical["revision"] == transcript["revision"]
        return real_write(directory, transcript, attempt)

    monkeypatch.setattr(local_files, "write_saved_revision", inspect_saved_commit)
    assert jobs.publish(active["id"], 1, result(jobs, active))
    jobs.patch(active["id"], 0, {"s1": "Committed edit"})
    assert observed == [("completed", "pending", 0), ("completed", "pending", 1)]
    assert_saved_files(jobs, active["id"])

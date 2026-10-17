"""Legacy history migration preserves the source and resumes interrupted installation."""

import fcntl
import json
import os

import pytest
from localscribe.jobs import Jobs
from localscribe.migration import JOURNAL, migrate_legacy_store
from localscribe.storage import Storage
from localscribe.worker import Worker
from test_jobs import completed, queued


@pytest.fixture
def legacy(tmp_path):
    jobs = Jobs(Storage(tmp_path / "legacy"))
    jobs.initialize()
    return jobs


def test_migrate_preserves_history_edits_media_and_original_store(legacy, tmp_path):
    job = completed(legacy, tmp_path)
    transcript = legacy.transcript(job["id"])
    transcript["segments"][0]["text"] = "Saved correction"
    legacy.patch(job["id"], 0, {"s1": "Saved correction"})
    waiting = queued(legacy, tmp_path, "waiting.wav")
    validation = legacy.storage.root / "validation"
    validation.mkdir()
    (validation / "private.txt").write_text("unrelated")
    target = tmp_path / "output"
    assert migrate_legacy_store(target, tmp_path / "models", legacy=legacy.storage.root)
    migrated = Jobs(Storage(target))
    migrated.initialize()
    assert migrated.transcript(job["id"])["segments"][0]["editedText"] == "Saved correction"
    assert migrated.get(waiting["id"])["status"] == "queued"
    assert (migrated.directory(job["id"]) / "source").read_bytes() == b"original media bytes"
    assert legacy.transcript(job["id"])["segments"][0]["editedText"] == "Saved correction"
    assert (legacy.directory(job["id"]) / "source").is_file()
    assert not (target / "validation").exists()
    assert (validation / "private.txt").read_text() == "unrelated"
    assert json.loads((target / "migration.json").read_text())["originalRetained"]
    assert not migrate_legacy_store(target, tmp_path / "models", legacy=legacy.storage.root)


@pytest.mark.parametrize("lock_name", ["launcher.lock", "worker.lock"])
def test_running_legacy_instance_is_rejected_before_copy(legacy, tmp_path, lock_name):
    target = tmp_path / "output"
    with (legacy.storage.root / lock_name).open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="Stop the previous"):
            migrate_legacy_store(target, tmp_path / "models", legacy=legacy.storage.root)
    assert not (target / "localscribe.sqlite3").exists()


def test_interrupted_installation_resumes_without_recopied_snapshot(legacy, tmp_path, monkeypatch):
    job = completed(legacy, tmp_path)
    target = tmp_path / "output"
    replace = os.replace

    def interrupt_database(source, destination):
        if str(destination) == str(target / "localscribe.sqlite3"):
            raise OSError("Simulated installation interruption")
        return replace(source, destination)

    monkeypatch.setattr("localscribe.migration.os.replace", interrupt_database)
    with pytest.raises(OSError, match="interruption"):
        migrate_legacy_store(target, tmp_path / "models", legacy=legacy.storage.root)
    assert (target / JOURNAL).is_file()
    assert not (target / "localscribe.sqlite3").exists()
    # The durable snapshot is sufficient even if the old store is unavailable.
    monkeypatch.setattr("localscribe.migration.os.replace", replace)
    assert migrate_legacy_store(target, tmp_path / "models", legacy=tmp_path / "missing")
    migrated = Jobs(Storage(target))
    migrated.initialize()
    assert (migrated.directory(job["id"]) / "source").is_file()
    assert migrated.transcript(job["id"])["originalText"] == "Hello"
    assert not (target / JOURNAL).exists()


def test_copy_failure_keeps_destination_uninitialized_and_legacy_untouched(
    legacy, tmp_path, monkeypatch
):
    job = completed(legacy, tmp_path)
    target = tmp_path / "output"

    def fail_copy(*args, **kwargs):
        raise OSError("Simulated disk full")

    monkeypatch.setattr("localscribe.migration.shutil.copytree", fail_copy)
    with pytest.raises(OSError, match="disk full"):
        migrate_legacy_store(target, tmp_path / "models", legacy=legacy.storage.root)
    assert not (target / "localscribe.sqlite3").exists()
    assert not list(target.glob(".migration-*"))
    assert (legacy.directory(job["id"]) / "source").is_file()


def test_migration_recovers_verified_children_before_copy(legacy, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        Worker, "recover_children", lambda self: calls.append(self.jobs.storage.root)
    )
    assert migrate_legacy_store(
        tmp_path / "output", tmp_path / "models", legacy=legacy.storage.root
    )
    assert calls == [legacy.storage.root]


@pytest.mark.parametrize("record", ["invalid", "{}", '{"staging":"../outside"}'])
def test_invalid_resume_record_does_not_touch_legacy(legacy, tmp_path, record):
    target = tmp_path / "output"
    target.mkdir()
    (target / JOURNAL).write_text(record)
    with pytest.raises(RuntimeError, match="record is invalid"):
        migrate_legacy_store(target, tmp_path / "models", legacy=legacy.storage.root)
    assert legacy.storage.database.is_file()


def test_schema_one_store_migrates_without_mutating_or_recovering_children(tmp_path, monkeypatch):
    source = Storage(tmp_path / "schema-one")
    source.initialize()
    monkeypatch.setattr(
        Worker,
        "recover_children",
        lambda self: pytest.fail("Schema one cannot own inference children"),
    )
    target = tmp_path / "output"
    assert migrate_legacy_store(target, tmp_path / "models", legacy=source.root)
    with source.connect() as db:
        assert db.execute("SELECT version FROM schema_migrations").fetchall()[0][0] == 1
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='jobs'").fetchall()
    migrated = Jobs(Storage(target))
    migrated.initialize()
    assert migrated.list() == {"jobs": [], "total": 0}


@pytest.mark.parametrize("missing_table", ["jobs", "attempts"])
def test_incomplete_legacy_schema_is_retained_and_rejected(legacy, tmp_path, missing_table):
    # No jobs exist, so dropping either table models incomplete historical storage.
    with legacy.storage.connect() as db:
        db.execute(f"DROP TABLE {missing_table}")
    target = tmp_path / "output"
    with pytest.raises(RuntimeError, match="incomplete job schema"):
        migrate_legacy_store(target, tmp_path / "models", legacy=legacy.storage.root)
    assert not (target / "localscribe.sqlite3").exists()
    assert legacy.storage.database.is_file()


@pytest.mark.parametrize("kill_point", ["before_mkdir", "after_copy"])
def test_hard_kill_during_copy_has_owned_journal_and_no_private_orphans_after_retry(
    legacy, tmp_path, kill_point
):
    import signal
    import subprocess
    import sys

    job = completed(legacy, tmp_path)
    target = tmp_path / "output"
    unrelated = target / ".migration-unrelated"
    unrelated.mkdir(parents=True)
    (unrelated / "keep.txt").write_text("Unrelated user data")
    script = """
import os
import shutil
import signal
import sys
from pathlib import Path
from localscribe.migration import migrate_legacy_store
original_mkdir = Path.mkdir
def kill_before_mkdir(self, *args, **kwargs):
    if sys.argv[4] == "before_mkdir" and self.name.startswith(".migration-"):
        os.kill(os.getpid(), signal.SIGKILL)
    return original_mkdir(self, *args, **kwargs)
Path.mkdir = kill_before_mkdir
original = shutil.copytree
def kill_after_copy(*args, **kwargs):
    copied = original(*args, **kwargs)
    os.kill(os.getpid(), signal.SIGKILL)
    return copied
shutil.copytree = kill_after_copy
migrate_legacy_store(Path(sys.argv[1]), Path(sys.argv[2]), legacy=Path(sys.argv[3]))
"""
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(target),
            str(tmp_path / "models"),
            str(legacy.storage.root),
            kill_point,
        ],
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert child.returncode == -signal.SIGKILL
    record = json.loads((target / JOURNAL).read_text())
    assert record["phase"] == "copying"
    staging = target / record["staging"]
    assert (staging / "jobs" / job["id"] / "source").is_file() == (kill_point == "after_copy")
    assert not (target / "localscribe.sqlite3").exists()
    assert migrate_legacy_store(target, tmp_path / "models", legacy=legacy.storage.root)
    assert not staging.exists()
    assert list(target.glob(".migration-*")) == [unrelated]
    migrated = Jobs(Storage(target))
    migrated.initialize()
    assert migrated.transcript(job["id"])["originalText"] == "Hello"
    migrated.delete(job["id"])
    assert not list(target.rglob("source"))
    assert not list(target.rglob("transcript.txt"))
    assert (unrelated / "keep.txt").read_text() == "Unrelated user data"
    assert (legacy.directory(job["id"]) / "source").is_file()


def test_interrupted_copy_requires_available_original_store(tmp_path):
    target = tmp_path / "output"
    target.mkdir()
    staging = target / ".migration-owned"
    staging.mkdir()
    (staging / "partial").write_bytes(b"Incomplete private media")
    (target / JOURNAL).write_text(json.dumps({"staging": staging.name, "phase": "copying"}))
    with pytest.raises(RuntimeError, match="Restore the previous store"):
        migrate_legacy_store(target, tmp_path / "models", legacy=tmp_path / "missing")
    assert not (target / "localscribe.sqlite3").exists()
    assert (target / JOURNAL).is_file()
    assert (staging / "partial").is_file()


@pytest.mark.parametrize("lock_name", ["launcher.lock", "worker.lock"])
def test_installation_resume_rejects_restarted_legacy_instance(
    legacy, tmp_path, monkeypatch, lock_name
):
    completed(legacy, tmp_path)
    target = tmp_path / "output"
    replace = os.replace

    def interrupt_database(source, destination):
        if str(destination) == str(target / "localscribe.sqlite3"):
            raise OSError("Simulated installation interruption")
        return replace(source, destination)

    monkeypatch.setattr("localscribe.migration.os.replace", interrupt_database)
    with pytest.raises(OSError, match="interruption"):
        migrate_legacy_store(target, tmp_path / "models", legacy=legacy.storage.root)
    monkeypatch.setattr("localscribe.migration.os.replace", replace)
    assert json.loads((target / JOURNAL).read_text())["phase"] == "installing"
    with (legacy.storage.root / lock_name).open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="Stop the previous"):
            migrate_legacy_store(target, tmp_path / "models", legacy=legacy.storage.root)
    assert not (target / "localscribe.sqlite3").exists()
    assert migrate_legacy_store(target, tmp_path / "models", legacy=legacy.storage.root)


def test_migrated_local_files_recover_latest_saved_revision_in_new_directory(legacy, tmp_path):
    job = completed(legacy, tmp_path)
    legacy.patch(job["id"], 0, {"s1": "Latest saved correction"})
    (legacy.directory(job["id"]) / "transcript.txt").write_text("Damaged external copy")
    target = tmp_path / "output"
    assert migrate_legacy_store(target, tmp_path / "models", legacy=legacy.storage.root)
    migrated = Jobs(Storage(target))
    migrated.initialize()
    migrated.recover()
    state = migrated.get(job["id"])["localFiles"]
    assert state["status"] == "ready"
    assert state["revision"] == state["savedRevision"] == 1
    assert state["directory"] == str(migrated.directory(job["id"]))
    text = (migrated.directory(job["id"]) / "transcript.txt").read_text()
    assert "Latest saved correction" in text
    assert "Damaged external copy" not in text

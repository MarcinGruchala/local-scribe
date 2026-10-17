"""Copy the old default store into ignored output while preserving existing history."""

import fcntl
import json
import os
import shutil
import sqlite3
import uuid
from contextlib import ExitStack, closing
from pathlib import Path

from .jobs import Jobs
from .storage import Storage
from .worker import Worker

JOURNAL = ".store-migration.json"


def _read_record(destination: Path):
    try:
        record = json.loads((destination / JOURNAL).read_text())
        name = record["staging"]
        # Journals from the first implementation already describe a complete copy.
        phase = record.get("phase", "installing")
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(
            "The store migration record is invalid. The previous store is retained."
        ) from exc
    if (
        not isinstance(name, str)
        or Path(name).name != name
        or not name.startswith(".migration-")
        or phase not in ("copying", "installing")
    ):
        raise RuntimeError("The store migration record is invalid. The previous store is retained.")
    if (destination / name).is_symlink():
        raise RuntimeError("The store migration directory must not be a symbolic link.")
    return {"staging": name, "phase": phase}


def _write_record(destination: Path, record: dict):
    journal = destination / JOURNAL
    temporary = journal.with_suffix(".tmp")
    with temporary.open("w") as stream:
        temporary.chmod(0o600)
        stream.write(json.dumps(record) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, journal)


def _recover_legacy_children(legacy: Path, model_root: Path):
    # Schema 1 predates jobs and cannot own inference children. Inspect without
    # upgrading the retained source, and reject a partially missing job schema.
    with closing(
        sqlite3.connect((legacy / "localscribe.sqlite3").as_uri() + "?mode=ro", uri=True)
    ) as db:
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('jobs','attempts')"
            )
        }
    if not tables:
        return
    if tables != {"jobs", "attempts"}:
        raise RuntimeError("The previous store has an incomplete job schema. It is retained.")
    # A crashed launcher may have left its child alive. Use the old exact
    # PID/creation-time/argv guard before copying any files that child owns.
    Worker(Jobs(Storage(legacy)), model_root).recover_children()


def _finish(destination: Path, record: dict):
    staging = destination / record["staging"]
    for directory in ("jobs", "imports"):
        source, target = staging / directory, destination / directory
        if source.exists():
            if target.exists() and (not target.is_dir() or any(target.iterdir())):
                raise RuntimeError(
                    "Output contains conflicting media. The previous store is retained."
                )
            os.replace(source, target)
    if (staging / "localscribe.sqlite3").exists():
        if (destination / "localscribe.sqlite3").exists():
            raise RuntimeError("Output already has a database. The previous store is retained.")
        # Database last: an interrupted installation can never appear as an empty history.
        os.replace(staging / "localscribe.sqlite3", destination / "localscribe.sqlite3")
    if not (destination / "localscribe.sqlite3").is_file():
        raise RuntimeError("Migration is incomplete. The previous store is retained.")
    if staging.exists():
        shutil.rmtree(staging)
    (destination / "migration.json").write_text(
        json.dumps({"source": "previous default store", "originalRetained": True}) + "\n"
    )
    (destination / JOURNAL).unlink()


def migrate_legacy_store(destination: Path, model_root: Path, *, legacy: Path | None = None):
    """Run under the destination launcher lock, before initializing its database.

    Only the app database and media are copied. The old store remains a backup;
    validation artifacts and unrelated files stay in their previous location.
    """
    destination = Path(destination).resolve()
    legacy = (legacy or Path.home() / "Library/Application Support/LocalScribe").resolve()
    database = legacy / "localscribe.sqlite3"
    journal = destination / JOURNAL
    record = _read_record(destination) if journal.exists() else None
    if destination == legacy:
        return False
    if record is None:
        if not database.is_file() or (destination / "localscribe.sqlite3").exists():
            return False
    elif record["phase"] == "copying" and not database.is_file():
        raise RuntimeError(
            "Migration copying was interrupted. Restore the previous store before restarting."
        )
    if record is None or record["phase"] == "copying":
        if (destination / "localscribe.sqlite3").exists():
            raise RuntimeError("Output already has a database. The previous store is retained.")
        for name in ("jobs", "imports"):
            path = destination / name
            if path.exists() and (not path.is_dir() or any(path.iterdir())):
                raise RuntimeError(
                    "Output contains media without a database. Choose another data root."
                )
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    with ExitStack() as stack:
        # A completed snapshot can resume without its source, but an available
        # previous instance must stay stopped throughout either recovery phase.
        if legacy.is_dir():
            for name in ("launcher.lock", "worker.lock"):
                lock = stack.enter_context((legacy / name).open("a+"))
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise RuntimeError(
                        "Stop the previous LocalScribe instance before migrating its history."
                    ) from exc
        if database.is_file():
            _recover_legacy_children(legacy, model_root)
        if record and record["phase"] == "installing":
            _finish(destination, record)
            return True
        if record:
            staging = destination / record["staging"]
            if staging.exists():
                shutil.rmtree(staging)
        else:
            record = {"staging": f".migration-{uuid.uuid4().hex}", "phase": "copying"}
            # Record ownership before mkdir or any private copy. Even a hard
            # process exit then leaves a recoverable, declared staging directory.
            _write_record(destination, record)
            staging = destination / record["staging"]
        try:
            staging.mkdir(mode=0o700)
            for name in ("jobs", "imports"):
                if (legacy / name).exists():
                    shutil.copytree(legacy / name, staging / name)
            with (
                closing(sqlite3.connect(database)) as source,
                closing(sqlite3.connect(staging / "localscribe.sqlite3")) as target,
            ):
                source.backup(target)
            (staging / "localscribe.sqlite3").chmod(0o600)
            record["phase"] = "installing"
            _write_record(destination, record)
        except BaseException:
            if staging.exists():
                shutil.rmtree(staging)
            journal.unlink()
            raise
        # Retain the completed snapshot on installation error, so the next
        # startup can finish without recopying or deleting unrelated data.
        _finish(destination, record)
    return True

"""Transactional queue ownership, immutable inference results, and separate user edits."""

import json
import os
import shutil
import time
import uuid
from pathlib import Path

from .contracts import Options, Transcript

ACTIVE = {"preparing", "transcribing", "diarizing", "assembling", "cancelling"}
TERMINAL = {"completed", "failed", "cancelled"}
STAGES = {"preparing", "transcribing", "diarizing", "assembling"}


class JobError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class Jobs:
    def __init__(self, storage):
        self.storage = storage

    def initialize(self):
        self.storage.initialize()
        with self.storage.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, filename TEXT NOT NULL, created REAL NOT NULL,
                    status TEXT NOT NULL, options TEXT NOT NULL, metadata TEXT NOT NULL,
                    attempt INTEGER NOT NULL DEFAULT 0, started REAL, finished REAL,
                    failure TEXT, result TEXT, revision INTEGER NOT NULL DEFAULT 0,
                    edits TEXT NOT NULL DEFAULT '{"segments":{},"speakers":{}}'
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    number INTEGER NOT NULL, options TEXT NOT NULL, started REAL NOT NULL,
                    finished REAL, status TEXT NOT NULL, pid INTEGER, process_started REAL,
                    command TEXT, PRIMARY KEY(job_id, number)
                );
                INSERT OR IGNORE INTO schema_migrations(version) VALUES (2);
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
            if "warnings" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN warnings TEXT NOT NULL DEFAULT '[]'")
                # Upgrade existing completed jobs once, never on status/history polling.
                for row in db.execute(
                    "SELECT id,result FROM jobs WHERE result IS NOT NULL"
                ).fetchall():
                    try:
                        warnings = json.loads(
                            (self.directory(row["id"]) / row["result"]).read_text()
                        ).get("warnings", [])
                    except (OSError, ValueError):
                        warnings = []
                    db.execute(
                        "UPDATE jobs SET warnings=? WHERE id=?", (json.dumps(warnings), row["id"])
                    )
            db.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (3)")

    def directory(self, job_id):
        if not isinstance(job_id, str) or len(job_id) != 32:
            raise JobError(404, "job_not_found", "The job does not exist.")
        try:
            int(job_id, 16)
        except ValueError as exc:
            raise JobError(404, "job_not_found", "The job does not exist.") from exc
        return self.storage.jobs_root / job_id

    def _row(self, db, job_id):
        self.directory(job_id)
        row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise JobError(404, "job_not_found", "The job does not exist.")
        return row

    def _serialize(self, row):
        status = row["status"]
        result = {
            "id": row["id"],
            "filename": row["filename"],
            "name": row["filename"],
            "status": status,
            "stage": status,
            "createdAt": row["created"],
            "startedAt": row["started"],
            "finishedAt": row["finished"],
            "attempt": row["attempt"],
            "options": json.loads(row["options"]),
            **json.loads(row["metadata"]),
            "failure": json.loads(row["failure"]) if row["failure"] else None,
            "revision": row["revision"],
            "warnings": json.loads(row["warnings"]),
            "error": json.loads(row["failure"]) if row["failure"] else None,
            "elapsedSeconds": max(0, (row["finished"] or time.time()) - row["started"])
            if row["started"]
            else 0,
        }
        return result

    def get(self, job_id):
        with self.storage.connect() as db:
            return self._serialize(self._row(db, job_id))

    def list(self, limit=50, offset=0):
        with self.storage.connect() as db:
            rows = db.execute(
                "SELECT * FROM jobs ORDER BY created DESC, id DESC LIMIT ? OFFSET ?",
                (min(max(limit, 1), 100), max(offset, 0)),
            ).fetchall()
            total = db.execute("SELECT count(*) FROM jobs").fetchone()[0]
            return {"jobs": [self._serialize(row) for row in rows], "total": total}

    def create_import(self, source_path, filename, metadata, options):
        options = Options.model_validate(options).model_dump()
        job_id = uuid.uuid4().hex
        directory = self.directory(job_id)
        directory.mkdir(mode=0o700)
        try:
            os.replace(source_path, directory / "source")
            with self.storage.connect() as db:
                db.execute(
                    "INSERT INTO jobs(id, filename, created, status, options, metadata) VALUES (?,?,?,'queued',?,?)",
                    (job_id, filename, time.time(), json.dumps(options), json.dumps(metadata)),
                )
        except BaseException:
            shutil.rmtree(directory)
            raise
        return self.get(job_id)

    def claim(self):
        with self.storage.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM jobs WHERE status IN ('preparing','transcribing','diarizing','assembling','cancelling')"
            ).fetchone():
                return None
            row = db.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY created,id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            now, attempt = time.time(), row["attempt"] + 1
            db.execute(
                "UPDATE jobs SET status='preparing', attempt=?, started=?,finished=NULL,failure=NULL WHERE id=?",
                (attempt, now, row["id"]),
            )
            db.execute(
                "INSERT INTO attempts(job_id,number,options,started,status) VALUES (?,?,?,?,'preparing')",
                (row["id"], attempt, row["options"], now),
            )
            return self._serialize(self._row(db, row["id"]))

    def stage(self, job_id, attempt, stage):
        if stage not in STAGES:
            raise ValueError("Invalid pipeline stage.")
        with self.storage.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, job_id)
            if row["attempt"] != attempt or row["status"] not in STAGES:
                return False
            db.execute("UPDATE jobs SET status=? WHERE id=?", (stage, job_id))
            db.execute(
                "UPDATE attempts SET status=? WHERE job_id=? AND number=?", (stage, job_id, attempt)
            )
            return True

    def record_process(self, job_id, attempt, pid, process_started, command):
        with self.storage.connect() as db:
            db.execute(
                "UPDATE attempts SET pid=?,process_started=?,command=? WHERE job_id=? AND number=?",
                (pid, process_started, json.dumps(command), job_id, attempt),
            )

    def active_processes(self):
        with self.storage.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT attempts.* FROM attempts JOIN jobs ON jobs.id=attempts.job_id AND jobs.attempt=attempts.number WHERE jobs.status IN ('preparing','transcribing','diarizing','assembling','cancelling')"
                )
            ]

    def cancel(self, job_id):
        with self.storage.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, job_id)
            if row["status"] == "queued":
                db.execute(
                    "UPDATE jobs SET status='cancelled',finished=? WHERE id=?",
                    (time.time(), job_id),
                )
            elif row["status"] in STAGES:
                db.execute("UPDATE jobs SET status='cancelling' WHERE id=?", (job_id,))
            return self._serialize(self._row(db, job_id))

    def finish_cancel(self, job_id, attempt):
        with self.storage.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, job_id)
            if row["attempt"] == attempt and row["status"] == "cancelling":
                now = time.time()
                db.execute(
                    "UPDATE jobs SET status='cancelled',finished=? WHERE id=?", (now, job_id)
                )
                db.execute(
                    "UPDATE attempts SET status='cancelled',finished=? WHERE job_id=? AND number=?",
                    (now, job_id, attempt),
                )

    def retry(self, job_id):
        with self.storage.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, job_id)
            if row["status"] not in {"failed", "cancelled"}:
                raise JobError(
                    409, "invalid_state", "Only failed or cancelled jobs can be retried."
                )
            db.execute(
                "UPDATE jobs SET status='queued',created=?,started=NULL,finished=NULL,failure=NULL WHERE id=?",
                (time.time(), job_id),
            )
            return self._serialize(self._row(db, job_id))

    def fail(self, job_id, attempt, code, message):
        with self.storage.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, job_id)
            if row["attempt"] == attempt and row["status"] in ACTIVE:
                status = "cancelled" if row["status"] == "cancelling" else "failed"
                now = time.time()
                db.execute(
                    "UPDATE jobs SET status=?,finished=?,failure=? WHERE id=?",
                    (status, now, json.dumps({"code": code, "message": message}), job_id),
                )
                db.execute(
                    "UPDATE attempts SET status=?,finished=? WHERE job_id=? AND number=?",
                    (status, now, job_id, attempt),
                )

    def publish(self, job_id, attempt, result_path):
        transcript = Transcript.model_validate_json(Path(result_path).read_text())
        if transcript.jobId != job_id or transcript.revision != 0:
            raise ValueError("The result belongs to another job or has user edits.")
        destination = self.directory(job_id) / "attempts" / str(attempt) / "published.json"
        with self.storage.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, job_id)
            if row["attempt"] != attempt or row["status"] not in STAGES:
                Path(result_path).unlink(missing_ok=True)
                return False
            if transcript.options.model_dump() != json.loads(row["options"]):
                raise ValueError("The result settings differ from immutable attempt options.")
            pinned_models = json.loads(row["metadata"]).get("modelSettings")
            if pinned_models is not None:
                for engine, profile in (
                    ("asr", transcript.options.profile),
                    ("diarization", "diarization"),
                ):
                    actual = transcript.provenance.get(engine, {})
                    if (
                        engine == "diarization"
                        and isinstance(actual, dict)
                        and actual.get("status") in {"failed", "disabled"}
                    ):
                        continue
                    expected = (
                        pinned_models.get(profile) if isinstance(pinned_models, dict) else None
                    )
                    if (
                        not isinstance(expected, dict)
                        or not isinstance(actual, dict)
                        or any(
                            not isinstance(expected.get(key), str)
                            or not expected[key]
                            or expected[key] != actual.get(key)
                            for key in ("repo", "revision")
                        )
                    ):
                        raise JobError(
                            409,
                            "model_revision_changed",
                            "The result does not match this job's pinned model revisions.",
                        )
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(result_path, destination)
            now = time.time()
            db.execute(
                "UPDATE jobs SET status='completed',finished=?,result=?,revision=0,edits=?,warnings=? WHERE id=?",
                (
                    now,
                    str(destination.relative_to(self.directory(job_id))),
                    '{"segments":{},"speakers":{}}',
                    json.dumps([warning.model_dump() for warning in transcript.warnings]),
                    job_id,
                ),
            )
            db.execute(
                "UPDATE attempts SET status='completed',finished=? WHERE job_id=? AND number=?",
                (now, job_id, attempt),
            )
        return True

    def transcript(self, job_id):
        with self.storage.connect() as db:
            row = self._row(db, job_id)
            return self._transcript(row)

    def _transcript(self, row):
        if not row["result"] or row["status"] in {"deleting", "deletion_failed"}:
            raise JobError(409, "transcript_unavailable", "No published transcript is available.")
        try:
            transcript = Transcript.model_validate_json(
                (self.directory(row["id"]) / row["result"]).read_text()
            ).model_dump()
        except (OSError, ValueError) as exc:
            raise JobError(
                409, "transcript_unavailable", "The stored transcript is unavailable."
            ) from exc
        edits = json.loads(row["edits"])
        for segment in transcript["segments"]:
            segment["editedText"] = edits["segments"].get(segment["id"])
        for speaker in transcript["speakers"]:
            speaker["displayName"] = edits["speakers"].get(speaker["id"], speaker["displayName"])
        transcript["revision"] = row["revision"]
        return transcript

    def patch(self, job_id, expected_revision, segment_texts=None, speaker_names=None):
        segment_texts, speaker_names = segment_texts or {}, speaker_names or {}
        with self.storage.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, job_id)
            if row["status"] != "completed":
                raise JobError(409, "invalid_state", "Only completed transcripts can be edited.")
            if row["revision"] != expected_revision:
                raise JobError(
                    409, "stale_revision", "The transcript changed. Reload before saving again."
                )
            transcript = self._transcript(row)
            known_segments = {segment["id"] for segment in transcript["segments"]}
            known_speakers = {speaker["id"] for speaker in transcript["speakers"]}
            if (
                set(segment_texts) - known_segments
                or set(speaker_names) - known_speakers
                or any(
                    value is not None and (not isinstance(value, str) or len(value) > 100_000)
                    for value in segment_texts.values()
                )
                or any(
                    not isinstance(value, str) or not value.strip() or len(value) > 200
                    for value in speaker_names.values()
                )
            ):
                raise JobError(
                    422, "invalid_edit", "Use existing segment/speaker IDs and valid text or names."
                )
            edits = json.loads(row["edits"])
            edits["segments"].update(segment_texts)
            edits["speakers"].update(speaker_names)
            db.execute(
                "UPDATE jobs SET edits=?,revision=revision+1 WHERE id=?",
                (json.dumps(edits), job_id),
            )
            return self._transcript(self._row(db, job_id))

    def media_path(self, job_id):
        self.get(job_id)
        path = self.directory(job_id) / "normalized.wav"
        if not path.is_file():
            raise JobError(
                409, "media_unavailable", "Normalized playback audio is not available yet."
            )
        return path

    def delete(self, job_id):
        with self.storage.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, job_id)
            if row["status"] not in TERMINAL | {"deleting", "deletion_failed"}:
                raise JobError(
                    409, "invalid_state", "Cancel this job and wait for it to stop before deleting."
                )
            db.execute("UPDATE jobs SET status='deleting',failure=NULL WHERE id=?", (job_id,))
        try:
            directory = self.directory(job_id)
            if directory.exists():
                shutil.rmtree(directory)
        except OSError as exc:
            with self.storage.connect() as db:
                db.execute(
                    "UPDATE jobs SET status='deletion_failed',failure=? WHERE id=?",
                    (
                        json.dumps(
                            {
                                "code": "deletion_failed",
                                "message": "Some local files could not be removed. Retry deletion.",
                            }
                        ),
                        job_id,
                    ),
                )
            raise JobError(
                409, "deletion_failed", "Some local files could not be removed. Retry deletion."
            ) from exc
        with self.storage.connect() as db:
            db.execute("DELETE FROM jobs WHERE id=? AND status='deleting'", (job_id,))

    def recover(self):
        """Call only under the launcher lock after surviving children have been stopped."""
        with self.storage.connect() as db:
            rows = db.execute("SELECT id,attempt,status FROM jobs").fetchall()
        for row in rows:
            if row["status"] in ACTIVE:
                self.fail(
                    row["id"],
                    row["attempt"],
                    "interrupted",
                    "Processing was interrupted by an application restart. Retry this job.",
                )
            elif row["status"] in {"deleting", "deletion_failed"}:
                try:
                    self.delete(row["id"])
                except JobError:
                    pass
        # Imports and unreferenced owned directories can only be abandoned at startup.
        for path in self.storage.imports_root.iterdir():
            if path.is_file():
                path.unlink()
        with self.storage.connect() as db:
            known = {row[0] for row in db.execute("SELECT id FROM jobs")}
            published = {
                row[0]: row[1]
                for row in db.execute("SELECT id,result FROM jobs WHERE result IS NOT NULL")
            }
        for path in self.storage.jobs_root.iterdir():
            if path.is_dir() and path.name not in known:
                shutil.rmtree(path)
            elif path.is_dir():
                for orphan in path.glob("attempts/*/published.json"):
                    if str(orphan.relative_to(path)) != published.get(path.name):
                        orphan.unlink()
        for job_id, result in published.items():
            if not (self.directory(job_id) / result).is_file():
                with self.storage.connect() as db:
                    db.execute(
                        "UPDATE jobs SET status='failed',result=NULL,failure=? WHERE id=?",
                        (
                            json.dumps(
                                {
                                    "code": "missing_result",
                                    "message": "The stored result is missing. Retry this job.",
                                }
                            ),
                            job_id,
                        ),
                    )

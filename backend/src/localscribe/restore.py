"""Restore an existing local inference export into history without rerunning models."""

import argparse
import hashlib
import json
import shutil
import time
import uuid
import wave
from pathlib import Path

from .config import Settings
from .contracts import Transcript
from .jobs import JobError, Jobs
from .launcher import instance_lock
from .storage import Storage


def restore_transcript(jobs: Jobs, transcript_path: Path, source: Path, normalized: Path):
    """Caller owns the launcher lock. Original artifacts are copied, never consumed."""
    content = transcript_path.read_bytes()
    transcript = Transcript.model_validate_json(content).model_dump()
    digest = hashlib.sha256(content).hexdigest()
    job_id = uuid.uuid5(uuid.NAMESPACE_URL, f"localscribe:restored-transcript:{digest}").hex
    try:
        existing = jobs.get(job_id)
    except JobError as exc:
        if exc.code != "job_not_found":
            raise
    else:
        # A repeat must not overwrite any edits made since the original restoration.
        return existing
    with wave.open(str(normalized), "rb") as audio:
        duration = audio.getnframes() / audio.getframerate()
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (
            1,
            2,
            16000,
        ) or abs(duration - transcript["duration"]) > 0.01:
            raise ValueError(
                "Normalized audio must match the saved transcript duration and format."
            )
    metadata = {
        "duration": duration,
        "sizeBytes": source.stat().st_size,
        "restoration": {"transcriptSha256": digest, "inferenceRerun": False},
        "modelSettings": {
            profile: {key: transcript["provenance"][engine][key] for key in ("repo", "revision")}
            for engine, profile in (
                ("asr", transcript["options"]["profile"]),
                ("diarization", "diarization"),
            )
            if all(key in transcript["provenance"].get(engine, {}) for key in ("repo", "revision"))
        },
    }
    original_id, revision = transcript["jobId"], transcript["revision"]
    edits = {
        "segments": {
            segment["id"]: segment["editedText"]
            for segment in transcript["segments"]
            if segment["editedText"] is not None
        },
        "speakers": {},
    }
    transcript["jobId"], transcript["revision"] = job_id, 0
    transcript["provenance"]["restoration"] = {
        **metadata["restoration"],
        "originalJobId": original_id,
        "originalRevision": revision,
    }
    for segment in transcript["segments"]:
        segment["editedText"] = None
    directory = jobs.directory(job_id)
    directory.mkdir(mode=0o700)
    try:
        shutil.copyfile(source, directory / "source")
        shutil.copyfile(normalized, directory / "normalized.wav")
        for filename in ("source", "normalized.wav"):
            (directory / filename).chmod(0o600)
        result = directory / "attempts/1/published.json"
        result.parent.mkdir(parents=True, mode=0o700)
        result.write_text(json.dumps(transcript, ensure_ascii=False, allow_nan=False))
        result.chmod(0o600)
        now = time.time()
        with jobs.storage.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO jobs(id,filename,created,status,options,metadata,attempt,finished,result,revision,edits,warnings,local_files) "
                "VALUES (?,?,?,'completed',?,?,1,?,?,?,?,?,?)",
                (
                    job_id,
                    source.name,
                    now,
                    json.dumps(transcript["options"]),
                    json.dumps(metadata),
                    now,
                    str(result.relative_to(directory)),
                    revision,
                    json.dumps(edits),
                    json.dumps(transcript["warnings"]),
                    json.dumps({"status": "pending"}),
                ),
            )
            db.execute(
                "INSERT INTO attempts(job_id,number,options,started,finished,status) VALUES (?,1,?,?,?,'completed')",
                (job_id, json.dumps(transcript["options"]), now, now),
            )
    except BaseException:
        shutil.rmtree(directory)
        raise
    jobs._sync_local_files_after_commit(job_id)
    return jobs.get(job_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--normalized", required=True, type=Path)
    parser.add_argument("--data-root", type=Path)
    args = parser.parse_args()
    settings = Settings.from_env(data_root=args.data_root)
    with instance_lock(settings.data_root):
        jobs = Jobs(Storage(settings.data_root))
        jobs.initialize()
        job = restore_transcript(jobs, args.transcript, args.source, args.normalized)
    print(json.dumps({"jobId": job["id"], "status": job["status"], "inferenceRerun": False}))


if __name__ == "__main__":
    main()

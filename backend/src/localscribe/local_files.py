"""Readable copies of one saved transcript revision inside its owned job directory."""

import hashlib
import json
import os
import uuid
from pathlib import Path

from .exports import render

FORMATS = ("txt", "srt", "vtt", "json")
FILENAMES = tuple(f"transcript.{format}" for format in FORMATS)
MANIFEST = "transcript-files.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def matches_saved_revision(directory: Path, job_id: str, attempt: int, revision: int) -> bool:
    """Validate all content hashes, so missing or manually changed copies are repaired."""
    try:
        manifest_path = directory / MANIFEST
        if manifest_path.is_symlink() or manifest_path.stat().st_size > 16 * 1024:
            return False
        manifest = json.loads(manifest_path.read_text())
        if (
            not isinstance(manifest, dict)
            or manifest.get("schemaVersion") != 1
            or manifest.get("jobId") != job_id
            or manifest.get("attempt") != attempt
            or manifest.get("revision") != revision
            or set(manifest["files"]) != set(FILENAMES)
        ):
            return False
        for filename in FILENAMES:
            path = directory / filename
            expected = manifest["files"][filename]
            if (
                path.is_symlink()
                or path.stat().st_size != expected["sizeBytes"]
                or _sha256(path) != expected["sha256"]
            ):
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def write_saved_revision(directory: Path, transcript: dict, attempt: int) -> None:
    """Caller holds queue ownership transaction; this function never creates a job folder."""
    if not directory.is_dir():
        raise FileNotFoundError("The owned job directory is unavailable.")
    temporary = []
    manifest = {
        "schemaVersion": 1,
        "jobId": transcript["jobId"],
        "attempt": attempt,
        "revision": transcript["revision"],
        "files": {},
    }
    try:
        # Prepare every format before replacing any public file. Saved inference text
        # remains immutable; these copies use the canonical, explicitly saved edits.
        for format, filename in zip(FORMATS, FILENAMES, strict=True):
            content = render(transcript, format)[0].encode("utf-8")
            path = directory / f".{filename}.{uuid.uuid4().hex}.pending"
            temporary.append((path, directory / filename))
            with path.open("xb") as handle:
                path.chmod(0o600)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            manifest["files"][filename] = {
                "sha256": hashlib.sha256(content).hexdigest(),
                "sizeBytes": len(content),
            }
        manifest_path = directory / MANIFEST
        staged_manifest = directory / f".{MANIFEST}.{uuid.uuid4().hex}.pending"
        temporary.append((staged_manifest, manifest_path))
        with staged_manifest.open("x") as handle:
            staged_manifest.chmod(0o600)
            json.dump(manifest, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # A partial series of replacements must never leave a ready manifest behind.
        # Publication of the manifest is the last operation in a complete copy set.
        manifest_path.unlink(missing_ok=True)
        for staged, destination in temporary:
            os.replace(staged, destination)
    finally:
        for staged, _ in temporary:
            staged.unlink(missing_ok=True)

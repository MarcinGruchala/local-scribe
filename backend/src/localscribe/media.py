"""Bounded local media import and shell-free FFmpeg decoding."""

import asyncio
import json
import math
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from .contracts import Options

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".mp4", ".mov"}


class MediaError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass(frozen=True)
class Limits:
    max_bytes: int = 2 * 1024**3
    max_duration: float = 7200
    reserve_bytes: int = 64 * 1024**2
    chunk_bytes: int = 1024**2


def probe(path: Path, limits: Limits | None = None) -> dict:
    limits = limits or Limits()
    if not path.is_file() or path.stat().st_size == 0:
        raise MediaError(422, "empty_media", "The recording is empty.")
    if path.stat().st_size > limits.max_bytes:
        raise MediaError(413, "media_too_large", "The recording exceeds the byte limit.")
    try:
        process = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            capture_output=True,
            timeout=30,
            check=True,
        )
        data = json.loads(process.stdout)
    except FileNotFoundError as exc:
        raise MediaError(409, "ffmpeg_not_ready", "Install FFmpeg and FFprobe first.") from exc
    except (subprocess.SubprocessError, ValueError) as exc:
        raise MediaError(422, "undecodable_media", "FFprobe cannot decode this recording.") from exc
    audio = [stream for stream in data.get("streams", []) if stream.get("codec_type") == "audio"]
    if not audio:
        raise MediaError(422, "no_audio", "The selected file has no audio stream.")
    try:
        duration = float(data.get("format", {}).get("duration") or audio[0].get("duration"))
    except (TypeError, ValueError) as exc:
        raise MediaError(
            422, "invalid_duration", "The recording duration cannot be determined."
        ) from exc
    if not math.isfinite(duration) or duration <= 0:
        raise MediaError(
            422, "invalid_duration", "The recording must have a positive finite duration."
        )
    if duration > limits.max_duration:
        raise MediaError(413, "media_too_long", "The recording exceeds the duration limit.")
    return {
        "duration": duration,
        "sizeBytes": path.stat().st_size,
        "sampleRate": audio[0].get("sample_rate"),
        "channels": audio[0].get("channels"),
    }


def validate_decode(path: Path, limits: Limits | None = None) -> float:
    """Decode to the null sink before enqueueing; container metadata is insufficient."""
    limits = limits or Limits()
    try:
        process = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-xerror",
                "-err_detect",
                "explode",
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(path),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-t",
                str(limits.max_duration + 1),
                "-progress",
                "pipe:1",
                "-nostats",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            timeout=max(60, limits.max_duration),
            check=True,
        )
    except FileNotFoundError as exc:
        raise MediaError(409, "ffmpeg_not_ready", "Install FFmpeg and FFprobe first.") from exc
    except subprocess.SubprocessError as exc:
        raise MediaError(
            422, "undecodable_media", "FFmpeg cannot decode the complete recording."
        ) from exc
    durations = []
    for line in process.stdout.decode("ascii", errors="replace").splitlines():
        if line.startswith("out_time_us="):
            try:
                durations.append(float(line.split("=", 1)[1]) / 1_000_000)
            except ValueError:
                continue
    duration = max(durations, default=0)
    if not math.isfinite(duration) or duration <= 0:
        raise MediaError(422, "undecodable_media", "The recording contains no decodable audio.")
    if duration > limits.max_duration:
        raise MediaError(413, "media_too_long", "The decoded recording exceeds the duration limit.")
    return duration


def normalize(source: Path, target: Path, limits: Limits | None = None) -> dict:
    """Decode the complete audio to mono PCM16 while retaining the source unchanged."""
    limits = limits or Limits()
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial.wav")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-y",
                "-xerror",
                "-err_detect",
                "explode",
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(source),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                "-t",
                str(limits.max_duration + 1),
                str(partial),
            ],
            capture_output=True,
            timeout=max(60, limits.max_duration),
            check=True,
        )
        metadata = probe(
            partial,
            Limits(
                max_bytes=max(limits.max_bytes, 240_000_000),
                max_duration=limits.max_duration,
                reserve_bytes=limits.reserve_bytes,
            ),
        )
        os.replace(partial, target)
        return metadata
    except FileNotFoundError as exc:
        raise MediaError(409, "ffmpeg_not_ready", "Install FFmpeg and FFprobe first.") from exc
    except subprocess.SubprocessError as exc:
        raise MediaError(
            422, "undecodable_media", "FFmpeg cannot decode the complete recording."
        ) from exc
    finally:
        partial.unlink(missing_ok=True)


async def import_upload(upload, storage, options, jobs, limits: Limits | None = None) -> dict:
    """Copy bounded chunks, validate on disk, then create the durable queue record."""
    limits = limits or Limits()
    options = Options.model_validate(options)
    filename = str(upload.filename or "recording")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise MediaError(
            415, "unsupported_media", "Supported formats: WAV, MP3, M4A, FLAC, OGG, MP4, MOV."
        )
    temporary = storage.imports_root / f"{uuid.uuid4().hex}{suffix}"
    count = 0
    try:
        with temporary.open("xb") as handle:
            os.chmod(temporary, 0o600)
            while chunk := await upload.read(limits.chunk_bytes):
                count += len(chunk)
                if count > limits.max_bytes:
                    raise MediaError(
                        413, "media_too_large", "The recording exceeds the byte limit."
                    )
                if shutil.disk_usage(storage.root).free < len(chunk) + limits.reserve_bytes:
                    raise MediaError(
                        409, "insufficient_storage", "Free more local storage before importing."
                    )
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        metadata = await asyncio.to_thread(probe, temporary, limits)
        metadata["duration"] = await asyncio.to_thread(validate_decode, temporary, limits)
        required = math.ceil(metadata["duration"] * 16000 * 2) + limits.reserve_bytes
        if shutil.disk_usage(storage.root).free < required:
            raise MediaError(
                409, "insufficient_storage", "Insufficient storage for normalized audio."
            )
        return await asyncio.to_thread(
            jobs.create_import, temporary, filename, metadata, options.model_dump()
        )
    finally:
        temporary.unlink(missing_ok=True)
        await upload.close()

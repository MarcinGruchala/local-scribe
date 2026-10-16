"""Real FFmpeg plumbing fixtures and bounded streaming import checks."""

import asyncio
import io
import shutil
import subprocess
import wave

import pytest
from localscribe.jobs import Jobs
from localscribe.media import Limits, MediaError, import_upload, normalize, probe
from localscribe.storage import Storage
from starlette.datastructures import UploadFile

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and FFprobe are required for media plumbing",
)


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "tone.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(48000)
        audio.writeframes(b"\0" * 48000 * 4)
    return path


@pytest.fixture
def jobs(tmp_path):
    service = Jobs(Storage(tmp_path / "store"))
    service.initialize()
    return service


def test_normalize_retains_original_and_produces_expected_wav(source, tmp_path):
    before = source.read_bytes()
    target = tmp_path / "normalized.wav"
    metadata = normalize(source, target)
    assert source.read_bytes() == before
    assert metadata["channels"] == 1 and metadata["sampleRate"] == "16000"
    assert metadata["duration"] == pytest.approx(1, abs=0.01)
    assert not target.with_name("normalized.wav.partial.wav").exists()


@pytest.mark.parametrize("extension", ["wav", "mp3", "m4a", "flac", "ogg", "mp4", "mov"])
def test_all_supported_audio_containers_import_durably(extension, source, tmp_path, jobs):
    converted = tmp_path / f"input.{extension}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(source), str(converted)], check=True)
    original = converted.read_bytes()
    upload = UploadFile(io.BytesIO(original), filename=f"../../escape.{extension}")
    job = asyncio.run(import_upload(upload, jobs.storage, {}, jobs))
    assert job["status"] == "queued" and job["duration"] == pytest.approx(1, abs=0.1)
    assert (jobs.directory(job["id"]) / "source").read_bytes() == original
    assert not (tmp_path / f"escape.{extension}").exists()
    assert list(jobs.storage.imports_root.iterdir()) == []
    restarted = Jobs(Storage(jobs.storage.root))
    assert restarted.get(job["id"])["options"] == job["options"]


@pytest.mark.parametrize(
    "payload,filename,status,code",
    [
        (b"", "empty.wav", 422, "empty_media"),
        (b"not audio", "broken.wav", 422, "undecodable_media"),
        (b"some data", "unsupported.exe", 415, "unsupported_media"),
    ],
)
def test_bad_uploads_leave_no_owned_files(jobs, payload, filename, status, code):
    upload = UploadFile(io.BytesIO(payload), filename=filename)
    with pytest.raises(MediaError) as error:
        asyncio.run(import_upload(upload, jobs.storage, {}, jobs))
    assert (error.value.status, error.value.code) == (status, code)
    assert jobs.list()["total"] == 0
    assert list(jobs.storage.imports_root.iterdir()) == []
    assert list(jobs.storage.jobs_root.iterdir()) == []


def test_audio_free_video_is_rejected(tmp_path, jobs):
    path = tmp_path / "no-audio.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=size=16x16:duration=0.2",
            "-y",
            str(path),
        ],
        check=True,
    )
    with pytest.raises(MediaError) as error:
        asyncio.run(
            import_upload(
                UploadFile(io.BytesIO(path.read_bytes()), filename=path.name),
                jobs.storage,
                {},
                jobs,
            )
        )
    assert error.value.code == "no_audio"
    assert jobs.list()["total"] == 0 and list(jobs.storage.imports_root.iterdir()) == []


def test_configurable_byte_duration_boundaries(source, jobs):
    payload = source.read_bytes()
    for limits, code in [
        (Limits(max_bytes=100), "media_too_large"),
        (Limits(max_duration=0.5), "media_too_long"),
    ]:
        with pytest.raises(MediaError) as error:
            asyncio.run(
                import_upload(
                    UploadFile(io.BytesIO(payload), filename="tone.wav"),
                    jobs.storage,
                    {},
                    jobs,
                    limits,
                )
            )
        assert error.value.status == 413 and error.value.code == code
    assert jobs.list()["total"] == 0 and list(jobs.storage.imports_root.iterdir()) == []
    assert probe(source, Limits(max_bytes=len(payload), max_duration=1))["duration"] == 1


def test_upload_reads_bounded_chunks_and_invalid_options_do_not_queue(source, jobs):
    class TrackingUpload(UploadFile):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.reads = []

        async def read(self, size=-1):
            self.reads.append(size)
            return await super().read(size)

    upload = TrackingUpload(io.BytesIO(source.read_bytes()), filename="tone.wav")
    asyncio.run(import_upload(upload, jobs.storage, {}, jobs, Limits(chunk_bytes=4096)))
    assert len(upload.reads) > 2 and set(upload.reads) == {4096}
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        asyncio.run(
            import_upload(
                UploadFile(io.BytesIO(b""), filename="tone.wav"),
                jobs.storage,
                {"speakerCount": 11},
                jobs,
            )
        )
    assert jobs.list()["total"] == 1


def test_insufficient_storage_cleans_partial_upload(source, jobs, monkeypatch):
    monkeypatch.setattr(
        "localscribe.media.shutil.disk_usage", lambda _: type("Disk", (), {"free": 0})()
    )
    with pytest.raises(MediaError) as error:
        asyncio.run(
            import_upload(
                UploadFile(io.BytesIO(source.read_bytes()), filename="tone.wav"),
                jobs.storage,
                {},
                jobs,
            )
        )
    assert error.value.code == "insufficient_storage"
    assert jobs.list()["total"] == 0 and list(jobs.storage.imports_root.iterdir()) == []


def test_truncated_decodable_header_never_creates_a_queue_record(source, jobs):
    # The valid WAV header survives; FFprobe still discovers an audio stream.
    truncated = source.read_bytes()[:-100]
    with pytest.raises(MediaError) as error:
        asyncio.run(
            import_upload(
                UploadFile(io.BytesIO(truncated), filename="truncated.wav"), jobs.storage, {}, jobs
            )
        )
    assert error.value.code == "undecodable_media"
    assert jobs.list()["total"] == 0 and list(jobs.storage.imports_root.iterdir()) == []


def test_decoded_duration_enforces_limit_even_when_metadata_claims_less(source, jobs, monkeypatch):
    real_probe = probe

    def misleading_probe(path, limits):
        metadata = real_probe(path)
        metadata["duration"] = 0.1
        return metadata

    monkeypatch.setattr("localscribe.media.probe", misleading_probe)
    with pytest.raises(MediaError) as error:
        asyncio.run(
            import_upload(
                UploadFile(io.BytesIO(source.read_bytes()), filename="misleading.wav"),
                jobs.storage,
                {},
                jobs,
                Limits(max_duration=0.5),
            )
        )
    assert error.value.status == 413 and error.value.code == "media_too_long"
    assert jobs.list()["total"] == 0 and list(jobs.storage.imports_root.iterdir()) == []


def test_saved_duration_uses_complete_decoded_audio(source, jobs, monkeypatch):
    real_probe = probe

    def misleading_probe(path, limits):
        metadata = real_probe(path, limits)
        metadata["duration"] = 0.1
        return metadata

    monkeypatch.setattr("localscribe.media.probe", misleading_probe)
    job = asyncio.run(
        import_upload(
            UploadFile(io.BytesIO(source.read_bytes()), filename="recording.wav"),
            jobs.storage,
            {},
            jobs,
        )
    )
    assert job["duration"] == pytest.approx(1, abs=0.001)

"""Explicit test-only HTTP harness. Never uses or downloads model weights.

Run with: uv run python tests/browser_server.py
The data root must be outside the repository. Fixture text is synthetic evidence
for UI plumbing only and cannot establish ASR or diarization quality.
"""

import json
import shutil
import struct
import sys
import time
import uuid
import wave
from contextlib import asynccontextmanager
from pathlib import Path

from localscribe.api import create_app
from localscribe.config import Settings
from localscribe.media import normalize
from localscribe.worker import Worker

ROOT = Path("/private/tmp/localscribe-browser")


def child(request_path: Path, output: Path):
    request = json.loads(request_path.read_text())
    directory = request_path.parent
    normalize(Path(request["source"]), Path(request["normalized"]))
    if request["job"]["name"].startswith("slow") and request["job"]["attempt"] == 1:
        (directory / "stage.json").write_text(json.dumps({"stage": "transcribing"}))
        while not (ROOT / "release").exists():
            time.sleep(0.05)
    for stage in (
        ["transcribing", "diarizing", "assembling"]
        if request["options"]["diarization"]
        else ["transcribing", "assembling"]
    ):
        (directory / "stage.json").write_text(json.dumps({"stage": stage}))
        time.sleep(1.8)
    speakers = [
        {"id": "speaker_1", "displayName": "Speaker 1"},
        {"id": "speaker_2", "displayName": "Speaker 2"},
    ]
    segments = [
        {
            "id": "s1",
            "start": 0,
            "end": 2,
            "speakerId": "speaker_1",
            "text": "Synthetic browser fixture first speaker.",
        },
        {
            "id": "s2",
            "start": 2,
            "end": 5,
            "speakerId": "speaker_2",
            "text": "Synthetic browser fixture second speaker.",
        },
    ]
    turns = [{"start": s["start"], "end": s["end"], "speakerId": s["speakerId"]} for s in segments]
    result = {
        "jobId": request["jobId"],
        "duration": 6,
        "language": "en",
        "requestedLanguage": request["options"]["language"],
        "detectedLanguage": "en",
        "options": request["options"],
        "originalText": "Synthetic browser fixture.",
        "segments": segments,
        "speakers": speakers,
        "modelSegments": [],
        "words": [],
        "regularTurns": turns,
        "exclusiveTurns": turns,
        "warnings": [],
        "provenance": {"fixture": True, "qualityEvidence": False},
    }
    degraded = request["job"]["name"] == "degraded.wav"
    if degraded or not request["options"]["diarization"]:
        for segment in result["segments"]:
            segment["speakerId"] = None
        result["speakers"] = []
        result["regularTurns"] = []
        result["exclusiveTurns"] = []
        result["provenance"]["diarization"] = {"status": "failed" if degraded else "disabled"}
    if degraded:
        result["warnings"] = [
            {
                "code": "diarization_failed",
                "message": "Speaker diarization failed. Text is preserved; speaker labels are unavailable.",
            }
        ]
    if request["job"]["name"] == "overlap.wav":
        result["segments"][0]["overlap"] = True
        result["regularTurns"] = [
            {"start": 0, "end": 3, "speakerId": "speaker_1"},
            {"start": 1, "end": 5, "speakerId": "speaker_2"},
        ]
    output.write_text(json.dumps(result))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--seed-pagination":
        app = create_app(
            Settings.from_env(
                data_root=ROOT / "store", model_root=ROOT / "unused-models", port=8766
            )
        )
        jobs = app.state.jobs
        with jobs.storage.connect() as connection:
            previous = connection.execute("SELECT id, filename, status FROM jobs").fetchall()
        for previous_job in previous:
            if (
                previous_job["filename"].startswith("Pagination terminal ")
                or previous_job["filename"] == "slow-pagination.wav"
            ) and previous_job["status"] in {"completed", "cancelled", "failed", "deletion_failed"}:
                jobs.delete(previous_job["id"])
        seeded = []
        for index in range(51):
            source = ROOT / (uuid.uuid4().hex + ".wav")
            shutil.copyfile(ROOT / "fixtures" / "picker.wav", source)
            job = jobs.create_import(
                source,
                f"Pagination terminal {index:02}.wav",
                {"duration": 6, "sizeBytes": source.stat().st_size},
                {},
            )
            jobs.cancel(job["id"])
            seeded.append(job["id"])
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and any(
            jobs.get(job_id)["status"] != "cancelled" for job_id in seeded
        ):
            time.sleep(0.05)
        assert all(jobs.get(job_id)["status"] == "cancelled" for job_id in seeded)
        source = ROOT / (uuid.uuid4().hex + ".wav")
        shutil.copyfile(ROOT / "fixtures" / "picker.wav", source)
        active = jobs.create_import(
            source, "slow-pagination.wav", {"duration": 6, "sizeBytes": source.stat().st_size}, {}
        )
        (ROOT / "pagination-seed.json").write_text(
            json.dumps({"terminalIds": seeded, "activeId": active["id"]})
        )
        print("Seeded 51 terminal fixture jobs and one long-running deterministic child.")
        return
    ROOT.mkdir(parents=True, exist_ok=True)
    fixtures = ROOT / "fixtures"
    fixtures.mkdir(exist_ok=True)
    for name in (
        "picker.wav",
        "drop.wav",
        "slow-active.wav",
        "slow-queued.wav",
        "degraded.wav",
        "overlap.wav",
        "text-only.wav",
    ):
        with wave.open(str(fixtures / name), "wb") as stream:
            stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            stream.writeframes(struct.pack("<h", 50) * (16000 * 6))
    settings = Settings.from_env(
        data_root=ROOT / "store", model_root=ROOT / "unused-models", port=8766
    )
    app = create_app(settings)
    app.state.readiness = lambda: {
        name: {
            "ready": name != "quality" and not (ROOT / "missing-models").exists(),
            "fixture": True,
        }
        for name in ("fast", "quality", "diarization")
    }
    worker = Worker(
        app.state.jobs,
        settings.model_root,
        command_factory=lambda request, result: [
            sys.executable,
            str(Path(__file__).resolve()),
            "--child",
            str(request),
            str(result),
        ],
        stop_grace=0.1,
    )

    @asynccontextmanager
    async def lifespan(application):
        worker.start()
        try:
            yield
        finally:
            worker.stop()

    app.router.lifespan_context = lifespan
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8766, access_log=False)


if __name__ == "__main__":
    main()

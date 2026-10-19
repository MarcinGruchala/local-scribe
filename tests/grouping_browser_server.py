"""Model-free browser fixture, isolated store, no worker or model downloads.

Run with LOCALSCRIBE_GROUPING_TEST_ROOT pointing outside the checkout.
Restart this server against the same root to test durable history.
"""

import json
import os
import shutil
import wave
from pathlib import Path

from localscribe.api import create_app
from localscribe.config import Settings


def fixture_app():
    root = Path(os.environ["LOCALSCRIBE_GROUPING_TEST_ROOT"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    port = int(os.environ.get("LOCALSCRIBE_GROUPING_TEST_PORT", "8770"))
    app = create_app(Settings.from_env(data_root=root / "store", model_root=root / "no-models", port=port))
    jobs = app.state.jobs
    fixture = root / "fixture.json"
    if not fixture.exists():
        marker = root / "no-models" / "shared-ownership-sentinel"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("Synthetic ownership marker, not model weights.")
        source = root / "synthetic.wav"
        with wave.open(str(source), "wb") as audio:
            audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\0\0" * 8000 * 400)
        job = jobs.create_import(source, "Grouping synthetic 400 segments.wav", {"duration": 400}, {})
        claimed = jobs.claim()
        assert claimed["id"] == job["id"]
        directory = jobs.directory(job["id"])
        shutil.copyfile(directory / "source", directory / "normalized.wav")
        segments = [
            {"id": f"s{i:03}", "start": i, "end": i + 0.8,
             "speakerId": "speaker_1" if i < 200 or i >= 201 else "speaker_2",
             "text": f"Word{i}."}
            for i in range(400)
        ]
        result = {"jobId": job["id"], "duration": 400, "language": "en",
                  "requestedLanguage": "auto", "detectedLanguage": "en", "options": job["options"],
                  "originalText": " ".join(s["text"] for s in segments), "segments": segments,
                  "speakers": [{"id": "speaker_1", "displayName": "Speaker 1"},
                               {"id": "speaker_2", "displayName": "Speaker 2"}],
                  "modelSegments": [], "words": [], "regularTurns": [], "exclusiveTurns": [],
                  "warnings": [], "provenance": {"fixture": True, "qualityEvidence": False}}
        result_path = root / "result.json"
        result_path.write_text(json.dumps(result))
        assert jobs.publish(job["id"], claimed["attempt"], result_path)
        fixture.write_text(json.dumps({"jobId": job["id"]}))
    return app, root, port


def main():
    import uvicorn
    app, _, port = fixture_app()
    uvicorn.run(app, host="127.0.0.1", port=port, access_log=False)


if __name__ == "__main__":
    main()

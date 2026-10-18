"""Fresh sequential inference child; only the supervisor can publish its output."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import shutil
import subprocess
import time
from pathlib import Path

from localscribe.alignment import assemble
from localscribe.contracts import Options, Transcript
from localscribe.engines.asr_mlx import transcribe
from localscribe.engines.diarization import diarize
from localscribe.media import normalize
from localscribe.models import ModelRevisionError, require_revisions


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False))
    temporary.chmod(0o600)
    temporary.replace(path)


def run(request: dict, output: Path) -> None:
    options = Options.model_validate(request["options"]).model_dump()
    directory = Path(request["attempt_dir"])
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    stage_file = directory / "stage.json"
    model_root = Path(request["model_root"])
    expected = request.get("job", {}).get("modelSettings", {})
    require_revisions(model_root, expected)
    audio = Path(request["normalized"])
    timings = {}
    started = time.monotonic()

    def stage(name: str):
        atomic_json(stage_file, {"stage": name})

    stage("preparing")
    begin = time.monotonic()
    normalize(Path(request["source"]), audio)
    timings["preparing"] = time.monotonic() - begin
    import wave

    with wave.open(str(audio)) as stream:
        duration = stream.getnframes() / stream.getframerate()
    if duration > 7200 or duration <= 0:
        raise ValueError("Decoded recording is outside the supported duration limit.")
    stage("transcribing")
    asr = transcribe(audio, model_root, options["profile"], options["language"])
    timings.update(asr.get("stageTimings", {}))
    provenance = asr.pop("provenance", {})
    packages = {}
    for name in ("mlx", "mlx-whisper", "pyannote.audio", "torch", "torchaudio", "torchcodec"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    ffmpeg_version = None
    if shutil.which("ffmpeg"):
        version = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=10, check=True
        )
        ffmpeg_version = version.stdout.splitlines()[0]
    provenance["runtime"] = {
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "packages": packages,
        "ffmpeg": ffmpeg_version,
    }
    provenance["requestedModels"] = expected
    regular, exclusive, warnings = [], [], []
    if options["diarization"]:
        stage("diarizing")
        begin = time.monotonic()
        try:
            speaker = diarize(audio, model_root, options["speakerCount"])
            regular, exclusive = speaker["regular"], speaker["exclusive"]
            provenance["diarization"] = speaker["provenance"]
        except Exception:  # noqa: BLE001 - redact third-party errors at the process boundary
            # Cancellation is a terminated process, never converted into this warning.
            warnings.append(
                {
                    "code": "diarization_failed",
                    "message": "Speaker diarization failed. Text is preserved; speaker labels are unavailable.",
                }
            )
            provenance["diarization"] = {"status": "failed", "device": "cpu"}
        timings["diarization"] = time.monotonic() - begin
    else:
        provenance["diarization"] = {"status": "disabled"}
    stage("assembling")
    result = assemble(
        asr, regular, exclusive, duration, request["jobId"], options, warnings, provenance
    )
    timings["total"] = time.monotonic() - started
    result["stageTimings"] = timings
    Transcript.model_validate(result)
    atomic_json(output, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        run(json.loads(args.request.read_text()), args.output)
    except ModelRevisionError:
        atomic_json(
            args.output.with_name("error.json"),
            {
                "code": "model_revision_changed",
                "message": "The cached model revision changed. Restore the recording's original snapshots before retrying.",
            },
        )
        raise SystemExit(1)
    except Exception:  # noqa: BLE001 - redact third-party errors at the process boundary
        # Keep private media paths, model output, and credentials out of logs.
        atomic_json(
            args.output.with_name("error.json"),
            {
                "code": "inference_failed",
                "message": "Processing failed. Check local model integrity and audio decoding, then retry.",
            },
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()

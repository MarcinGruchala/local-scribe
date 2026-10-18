"""Explicit heavyweight compatibility run; private output remains outside Git."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import resource
import time
import wave
from pathlib import Path

from localscribe.alignment import assemble
from localscribe.engines.asr_mlx import transcribe
from localscribe.engines.diarization import diarize
from localscribe.media import normalize
from localscribe.models import default_root, inspect


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model-root", type=Path, default=default_root())
    parser.add_argument("--language", choices=["auto", "en", "pl"], default="auto")
    parser.add_argument("--profile", choices=["fast", "quality"], default="fast")
    parser.add_argument("--diarization", action="store_true")
    parser.add_argument("--speaker-count", type=int, choices=range(1, 11))
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[3]
    if args.output.resolve().is_relative_to(repository):
        parser.error("Private spike output must be outside the repository.")
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    normalized = args.output.with_suffix(".wav")
    started = time.monotonic()
    normalize(args.sample, normalized)
    with wave.open(str(normalized)) as stream:
        duration = stream.getnframes() / stream.getframerate()
    asr = transcribe(normalized, args.model_root, args.profile, args.language)
    provenance = asr.pop("provenance", {})
    regular, exclusive = [], []
    timings = dict(asr.get("stageTimings", {}))
    if args.diarization:
        speaker = diarize(normalized, args.model_root, args.speaker_count)
        regular, exclusive = speaker["regular"], speaker["exclusive"]
        provenance["diarization"] = speaker["provenance"]
        timings["diarization"] = speaker["seconds"]
    else:
        provenance["diarization"] = {"status": "disabled"}
    options = {
        "language": args.language,
        "profile": args.profile,
        "diarization": args.diarization,
        "speakerCount": args.speaker_count,
    }
    result = assemble(asr, regular, exclusive, duration, "spike", options, provenance=provenance)
    timings["total"] = time.monotonic() - started
    result.update(
        stageTimings=timings,
        totalSeconds=timings["total"],
        realTimeFactor=timings["total"] / duration,
        peakRssBytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        architecture=platform.machine(),
        versions={
            name: importlib.metadata.version(name)
            for name in ["mlx-whisper", "mlx", "torch", "pyannote.audio", "torchcodec"]
        },
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    args.output.chmod(0o600)
    if result["segments"]:
        revision = inspect(args.model_root, args.profile)["revision"]
        evidence = {
            "revision": revision,
            "passed": True,
            "scope": "native timestamp compatibility only; reference quality pending",
        }
        (args.model_root / args.profile / "compatibility.json").write_text(
            json.dumps(evidence) + "\n"
        )
    print(
        json.dumps(
            {
                "segments": len(result["segments"]),
                "language": result["language"],
                "finiteTimestamps": True,
                "duration": duration,
                "totalSeconds": timings["total"],
                "realTimeFactor": result["realTimeFactor"],
                "peakRssBytes": result["peakRssBytes"],
            }
        )
    )


if __name__ == "__main__":
    main()

"""Explicit heavyweight compatibility run; private output remains outside Git."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import resource
import subprocess
import time
from pathlib import Path

from localscribe.engines.asr_mlx import transcribe
from localscribe.engines.diarization import diarize
from localscribe.models import default_root


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
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    normalized = args.output.with_suffix(".wav")
    start = time.monotonic()
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-i",
            str(args.sample),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(normalized),
        ],
        check=True,
        capture_output=True,
    )
    result = transcribe(normalized, args.model_root, args.profile, args.language)
    if args.diarization:
        result["diarization"] = diarize(normalized, args.model_root, args.speaker_count)
    result["totalSeconds"] = time.monotonic() - start
    result["peakRssBytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result["versions"] = {
        name: importlib.metadata.version(name)
        for name in ["mlx-whisper", "mlx", "torch", "pyannote.audio", "torchcodec"]
    }
    result["architecture"] = platform.machine()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.output.chmod(0o600)
    segments = result.get("segments", [])
    import math

    valid = all(
        math.isfinite(s["start"]) and math.isfinite(s["end"]) and s["start"] < s["end"]
        for s in segments
    )
    print(
        json.dumps(
            {
                "segments": len(segments),
                "language": result.get("language"),
                "finiteTimestamps": valid,
                "totalSeconds": result["totalSeconds"],
                "peakRssBytes": result["peakRssBytes"],
            }
        )
    )
    if not valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

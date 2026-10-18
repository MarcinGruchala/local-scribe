"""Offline Community-1 speaker turns on the CPU."""

from __future__ import annotations

import importlib.metadata
import time
from pathlib import Path

from localscribe.models import inspect, local_path


def diarize(audio: Path, model_root: Path, speaker_count: int | None) -> dict:
    folder = local_path(model_root, "diarization")
    import torch
    from pyannote.audio import Pipeline

    start = time.monotonic()
    pipeline = Pipeline.from_pretrained(str(folder), token=False)
    if pipeline is None:
        raise RuntimeError("Community-1 could not load local assets.")
    pipeline.to(torch.device("cpu"))
    output = pipeline(str(audio), **({"num_speakers": speaker_count} if speaker_count else {}))

    def turns(annotation):
        return [
            {"start": float(t.start), "end": float(t.end), "speakerId": str(s)}
            for t, _, s in annotation.itertracks(yield_label=True)
        ]

    return {
        "regular": turns(output.speaker_diarization),
        "exclusive": turns(output.exclusive_speaker_diarization),
        "seconds": time.monotonic() - start,
        "provenance": {
            **inspect(model_root, "diarization"),
            "engine": "pyannote.audio",
            "device": "cpu",
            "version": importlib.metadata.version("pyannote.audio"),
        },
    }

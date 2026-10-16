"""Native MLX transcription with local snapshots and original-language output."""

from __future__ import annotations

import gc
import importlib.metadata
import time
from pathlib import Path

from localscribe.models import inspect, local_path


def transcribe(audio: Path, model_root: Path, profile: str, language: str) -> dict:
    model = local_path(model_root, profile)
    import mlx.core as mx
    import mlx_whisper

    start = time.monotonic()
    result = mlx_whisper.transcribe(
        str(audio),
        path_or_hf_repo=str(model),
        task="transcribe",
        language=None if language == "auto" else language,
        word_timestamps=True,
        verbose=None,
        temperature=0.0,
        condition_on_previous_text=False,
    )
    result["stageTimings"] = {"asr": time.monotonic() - start}
    result["provenance"] = {
        "asr": {
            **inspect(model_root, profile),
            "engine": "mlx-whisper",
            "device": "gpu",
            "version": importlib.metadata.version("mlx-whisper"),
            "task": "transcribe",
        },
    }
    # The child exits after the job. Clear the library cache before CPU diarization.
    module = importlib.import_module("mlx_whisper.transcribe")
    holder = getattr(module, "ModelHolder", None)
    if holder is not None:
        holder.model = None
    gc.collect()
    mx.clear_cache()
    return result

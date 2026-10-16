"""LocalScribe: local file transcription."""

import os

# Set these before any inference library import, including in fresh children.
for _key, _value in {
    "HF_HUB_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "DO_NOT_TRACK": "1",
    "PYANNOTE_METRICS_ENABLED": "0",
    "PYANNOTE_TELEMETRY_ENABLED": "0",
    "TOKENIZERS_PARALLELISM": "false",
}.items():
    os.environ[_key] = _value

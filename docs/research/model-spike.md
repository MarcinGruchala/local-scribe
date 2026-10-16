# Local model compatibility spike

Date: 2026-10-16. Status: in progress; no release gate is implied by successful imports.

## Observations

- Native arm64 CPython 3.11.6, FFmpeg/FFprobe available, approximately 194 GiB available at initial inspection.
- The sandbox cannot expose Metal. An explicitly approved host-side import confirmed `mlx.metal.is_available() == True`.
- Host-side imports of MLX, pyannote.audio, PyTorch, and torchcodec succeeded.
- Locked set includes mlx 0.32.4, mlx-whisper 0.4.3, pyannote.audio 4.0.7, torch 2.14.1, torchcodec 0.17.0. `uv.lock` is the authoritative complete dependency list.
- Explicit turbo provisioning is in progress; weights remain outside Git. No Community-1 credential/cache was detected at initial inspection. Its gated conditions remain a user action.
- The public Whisper JFK smoke fixture was fetched outside Git from the upstream tests. SHA-256: `63a4b1e4c1dc655ac70961ffbf518acd249df237e5a0152faae9a4a836949715`. It is a compatibility input, not a representative bilingual or speaker-quality reference.

## Reproduction

```sh
make setup
make models PROFILE=fast
# User accepts Community-1 terms and configures an external download credential.
make models PROFILE=diarization
make doctor
uv run --frozen --no-sync localscribe-spike /absolute/sample.flac \
  --output /absolute/private-results/spike.json --language en --diarization
```

Outputs contain private model text and belong outside the checkout. Console summaries contain counts/timing/language only. Stages run sequentially, ASR caches are released before CPU speaker inference, and the model child exits after each attempt. All model loading uses hash-checked local snapshots. HF offline and telemetry settings are set before model-library imports. Runtime removes download credentials from child environments.

## Provisional choice and pending gates

Keep the accepted MLX turbo candidate and Community-1 CPU baseline pending actual inference. Large-v3 is a comparison candidate, not an accepted Quality profile. Do not expose it until its compatibility/quality comparison evidence is recorded.

Actual ASR timing/timestamp evidence, actual Community-1 regular/exclusive turns, a second network-disabled run, English/Polish/mixed-language quality, speaker accuracy, cold/warm timings, peak memory, sustained memory pressure, 30-minute performance, and 60-minute stability remain pending. Corrected user-approved references are unavailable. Successful library imports are not inference evidence.

The turbo MLX conversion card has no explicit license metadata in the planning research; upstream turbo is MIT. Preserve the [upstream model provenance](https://huggingface.co/openai/whisper-large-v3-turbo) and [conversion card](https://huggingface.co/mlx-community/whisper-large-v3-turbo). Community-1 is CC-BY-4.0; [its model card](https://huggingface.co/pyannote/speaker-diarization-community-1) documents user acceptance and local loading. Conversion provenance/license gaps remain explicit rather than asserting a license for someone else's conversion.

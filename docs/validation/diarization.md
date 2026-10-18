# Actual offline Community-1 validation

Date: 2026-10-16. Native CPU compatibility **passed** after the user personally accepted the model conditions and authenticated locally. This is functional model evidence, not the representative speaker-quality or performance gate.

## Assets and execution

The explicit provisioning command downloaded all 10 files at Community-1 revision `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee`, totalling 33,695,573 bytes. The external SHA-256 manifest covers segmentation, embedding and PLDA assets. Its local `config.yaml` references `$model/segmentation`, `$model/embedding` and `$model/plda`; no separate repository download is needed by this snapshot. Full hash-checking `doctor` reports all three profiles ready with offline and telemetry-disabled settings.

Actual runs use MLX Whisper on GPU followed by `pyannote.audio` 4.0.7 on CPU. Models are never run concurrently. The app and its inference children run under `scripts/offline.sb`, which denies external networking. The EN and recurring-voice runs additionally set `HF_HOME` to an empty external directory: successful inference therefore does not depend on an authenticated Hugging Face home or its transitive caches. The adapter passes `token=False` and loads the explicit local snapshot. Tokens, weights, audio and raw output stay outside Git.

## Measured short compatibility runs

| Input / speaker setting | Duration | ASR | Diarization | Total | Peak process RSS | Regular / exclusive turns | Speakers |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Public FLEURS PL / automatic | 12.12 s | 1.254 s | 24.990 s | 30.659 s | 3,385,507,840 bytes | 2 / 2 | 1 |
| Public FLEURS EN / exact 1 | 10.56 s | 0.998 s | 1.198 s | 5.621 s | 2,039,889,920 bytes | 3 / 3 | 1 |
| Constructed PL–EN–PL–EN / automatic | 45.36 s | 2.200 s | 18.928 s | 24.832 s | 5,928,353,792 bytes | 12 / 12 | 2 |
| PL Quality / exact 1, clean full environment | 12.12 s | 2.999 s | 11.121 s | 59.472 s | 3,738,025,984 bytes | 2 / 2 | 1 |

These are fresh process runs with differing filesystem/runtime cache state; the first model use was much slower. Do not extrapolate their real-time factors or memory peaks to a representative 30-minute meeting. No sustained-memory-pressure acceptance is claimed.

The clean full runtime was installed separately from the lock; its speaker assets were independently provisioned into a fresh directory and matched the main manifest. It then completed actual Quality ASR plus CPU diarization with no transcript warnings under OS network denial and empty HF home. The spike's engine timers exclude imports before their internal start points; total includes normalization, hash checks and imports. In this clean run roughly 45 s fell outside the two engine timers. Preserve the measured total rather than reporting their sum as end-to-end runtime; warm snippets do not establish cold-start or long-form speed.

The two unmodified human utterances and their permission/source hashes are documented in [public samples](public-samples.md). The recurring-voice probe concatenates their normalized PCM in the order PL, EN, PL, EN without changing individual frames. SHA-256 of the resulting WAV: `f2cf1f886dff95c8cbaa2cbabc7638886ae4e12a16baac05a2fa229fb60ff138`. Both first and repeated PL blocks have the same anonymous ID; both EN blocks have a second recurring ID. A brief 0.101 s erroneous label inside the first EN block remains in the result. This is a constructed two-voice compatibility probe, not a natural conversation or a manually labelled quality reference.

Individual EN/PL runs completed without transcript warnings. The constructed mixed-language run emitted `alignment_fallback` for incomplete model word timestamps; assembly retained the text and used segment overlap. Its successful diarization does not resolve the previously recorded mixed-language ASR omission. The library also emitted a `std(): degrees of freedom is <= 0` warning for a very short pooling window; it did not prevent regular/exclusive output. This observation remains visible rather than suppressing the warning globally.

## Reproduction

```sh
make models PROFILE=diarization
make doctor
mkdir -p /private/tmp/localscribe-no-hf-home
HF_HOME=/private/tmp/localscribe-no-hf-home /usr/bin/sandbox-exec -f scripts/offline.sb \
  .venv/bin/python -m localscribe.spike \
  /private/tmp/localscribe-validation/fleurs-en.wav \
  --output /private/tmp/localscribe-validation/fleurs-en-fast-diarization-offline.json \
  --language en --diarization --speaker-count 1
```

Repeat sequentially for Polish with `--language pl` and omit `--speaker-count` to exercise automatic count. Representative corrected 5–10 minute two-speaker references, overlap/music/three-speaker challenges, and 30/60-minute inputs remain required by [the release report](mvp-release.md).

## Actual cancellation during diarization

The normal OS-offline application imported the constructed 45.36 s two-voice probe with diarization enabled. The explicit live checker observed `diarizing`, waited 0.9 s, confirmed it was still in that stage, then cancelled attempt 1. The job reached `cancelled`; no transcript was available immediately or after a further 2 s; a repeated cancel was idempotent. Retry preserved both options and pinned model settings. Attempt 2 completed with genuine CPU Community-1 provenance, after which the checker deleted only its own job and verified `404`. Retry took 17.755 s total (ASR 1.252 s, diarization 15.298 s). This is cancellation/retry evidence, not a representative performance benchmark.

```sh
.venv/bin/python scripts/check-live-cancellation.py \
  --base-url http://127.0.0.1:8767 \
  --sample /private/tmp/localscribe-validation/fleurs-voices-abab.wav \
  --output /private/tmp/localscribe-validation/live-cancellation-diarization.json \
  --diarization --stage diarizing --timeout 300
```

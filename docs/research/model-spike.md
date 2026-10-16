# Local model compatibility spike

Date: 2026-10-16. Status: **Native ASR and CPU diarization compatibility passed, including full cached offline runs.** No release-quality gate is implied by these short measurements.

## Inspected environment

Host: Apple M5 Pro, 64 GiB RAM, native arm64 CPython 3.11.6, FFmpeg/FFprobe available. The ordinary execution sandbox cannot expose Metal. Explicitly approved host execution and the external-network-denial validation sandbox both confirmed Metal availability. Host imports of MLX, pyannote.audio, PyTorch, and torchcodec succeeded. An actual offline pyannote Audio/torchcodec decode of normalized PL audio returned mono 16 kHz, 193,920 finite frames. Actual Community-1 CPU inference now returns regular and exclusive turns on EN/PL human samples and two recurring IDs on a constructed two-voice probe; see [diarization evidence](../validation/diarization.md).

The lock includes mlx 0.32.4, mlx-whisper 0.4.3, pyannote.audio 4.0.7, torch 2.14.1, torchaudio 2.11.0, and torchcodec 0.17.0. `uv.lock` is authoritative. Two separate clean environments installed the locked core and complete model dependency sets offline from cache. Fast tests remain independent of these model libraries.

## Exact snapshots and provenance

| Profile | Repository | Immutable revision | Result |
| --- | --- | --- | --- |
| Fast | `mlx-community/whisper-large-v3-turbo` | `a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb` | Explicitly downloaded; hash manifest; real EN/PL GPU inference offline |
| Quality | `mlx-community/whisper-large-v3-mlx` | `49e6aa286ad60c14352c404340ded53710378a11` | Explicitly downloaded; hash manifest; real EN/PL GPU inference offline |
| Speakers | `pyannote/speaker-diarization-community-1` | `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee` | Explicitly downloaded after user-owned acceptance/login; all 10 files hashed; real CPU regular/exclusive turns offline |

`model-lock.json` pins repositories and revisions. External per-profile manifests contain each asset's SHA-256 and byte count. Provisioning is explicit; runtime verifies local files and never downloads. The optional Quality profile requires a successful explicit compatibility sidecar matching the exact snapshot. Neither profile is accepted against representative quality references yet.

The turbo MLX conversion card had no explicit license metadata in planning; [upstream turbo](https://huggingface.co/openai/whisper-large-v3-turbo) declares MIT. Preserve [conversion provenance](https://huggingface.co/mlx-community/whisper-large-v3-turbo) rather than inventing its license field. The [large-v3 conversion](https://huggingface.co/mlx-community/whisper-large-v3-mlx) declares MIT while the [upstream large-v3 card](https://huggingface.co/openai/whisper-large-v3) identifies Apache-2.0; these notices are not flattened into a single invented claim. [Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) is CC-BY-4.0 with user-owned gated acceptance.

## Actual smoke results

The public upstream Whisper JFK sample is 11.00 s. SHA-256: `63a4b1e4c1dc655ac70961ffbf518acd249df237e5a0152faae9a4a836949715`. The initial Fast run took 15.359 s (peak RSS 1,922,449,408 bytes), and a second OS-offline run took 2.725 s (1,897,381,888 bytes). English text and finite timestamps were returned. [Public FLEURS sample evidence](../validation/public-samples.md) records licenses/revisions/hashes for short actual human EN/PL inputs.

| Input / profile | Duration | Total spike | Peak RSS | Result |
| --- | --- | --- | --- | --- |
| FLEURS PL / Fast, forced pl |12.12s |2.607s |1,908,539,392bytes | Polish with diacritics, valid timestamps |
| FLEURS PL / Fast, Auto |12.12s |2.556s |1,910,538,240bytes | Detects pl |
| FLEURS EN / Fast, forced en |10.56s |2.325s |1,908,244,480bytes | English, valid timestamps |
| FLEURS PL / Quality, forced pl |12.12s |4.328s |3,669,344,256bytes | Polish, valid timestamps |
| FLEURS EN / Quality, forced en |10.56s |3.597s |3,704,586,240bytes | English, valid timestamps |

Each run starts a fresh process. They use identical normalized audio and decoding settings within each language. Filesystem/runtime caches are warm; the values do not establish representative cold/warm performance. The normal offline application also passed actual English and Polish browser import/play/edit/export/delete workflows and real ASR cancellation/retry. See [browser evidence](../validation/browser-smoke.md) and [lifecycle evidence](../validation/lifecycle.md).

The unguarded model hallucinated 10 non-whitespace characters on 5 seconds of digital silence. A bounded correction recognizes exact PCM zeros and returns an empty transcript without loading the model; even one nonzero sample remains eligible for inference. The corrected offline check returned zero segments and an empty-result notice. This does not filter quiet speech, noise or music; those challenge cases remain pending. Full details and the retained initial failure are in [release evidence](../validation/mvp-release.md).

## Reproduction

```sh
make setup
make build
make models PROFILE=fast
make models PROFILE=quality
# The user personally accepts Community-1 terms and runs .venv/bin/hf auth login.
make models PROFILE=diarization
make doctor
.venv/bin/python scripts/fetch-fleurs-samples.py --output /private/tmp/localscribe-validation
/usr/bin/sandbox-exec -f scripts/offline.sb .venv/bin/python -m localscribe.spike \
  /private/tmp/localscribe-validation/fleurs-pl.wav \
  --output /private/tmp/localscribe-validation/fleurs-pl-fast-offline.json --language pl
# Repeat with --profile quality; add --diarization for the full sequential pipeline.
```

`doctor --asr-only` is available for intentional text-only use while speaker assets are absent. Private outputs are refused inside the checkout. Console summaries contain counts/language/timing only. Inference snapshots load locally under offline/telemetry flags; the worker removes HF token environment variables. The OS sandbox denies external network connections for the entire app process hierarchy while retaining loopback and Metal. Flags alone are not the offline proof.

## Recommendation and unresolved evidence

Retain Fast as the provisional default and Quality as a verified compatibility alternative. Do not change the accepted default on a handful of read-speech words. Both profiles scored PL 0/20 and EN 2/19 errors on these same tiny references. Representative English, Polish, mixed-language and speaker quality are **pending references**. Small public samples cannot certify the 15% WER or 90% speaker-attribution thresholds.

Retain the accepted Community-1 CPU baseline: real EN/PL and recurring-voice runs return regular/exclusive turns under OS external-network denial, including with an empty HF home. Explicit provisioning of all transitive assets was repeated in a clean locked dependency environment and produced an identical 10-file hash manifest. No gated terms were accepted for the user. Representative 30 minute RTF/memory pressure, approximately 60 minute stability, and corrected two-speaker quality references remain pending. There is no evidence of an MLX compatibility failure requiring whisper.cpp fallback.

## Constructed language-switch observation

The public PL then EN utterances were concatenated into 22.68 s of actual human speech solely for a short language-switch probe. Fast/Auto detected pl and omitted the English portion (19 deletions / 39 reference words, combined WER 48.718%). This failure remains visible and does not become a passed mixed-language gate. Quality is evaluated on the same input; manually corrected representative multilingual conversation references are still pending.

The Quality/Auto probe on the identical constructed input also detected pl and omitted the English portion (19 deletions / 39 words, WER 48.718%; 4.178 s, peak RSS 3,715,563,520 bytes). Neither profile solved this short language-switch challenge; no default or acceptance threshold was changed to hide the result.

## Completed Community-1 compatibility gate

After the user personally accepted access conditions and authenticated locally, the initial access blocker was resolved. The first full PL spike took 30.659 s (ASR 1.254 s, CPU diarization 24.990 s); the later EN spike took 5.621 s (ASR 0.998 s, diarization 1.198 s). The EN run used an empty HF home and no external network. A constructed 45.36 s PL–EN–PL–EN sample produced two recurring anonymous IDs, 12 regular and 12 exclusive turns, in 24.832 s total. Its incomplete word timestamps triggered the documented alignment fallback. Short-window pooling warnings and a brief spurious turn remain recorded in [the detailed evidence](../validation/diarization.md). These are compatibility measurements, not sustained-performance or reference-attribution acceptance.

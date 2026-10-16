# LocalScribe MVP release evidence

Date: 2026-10-16. **Release decision: NOT READY.** The application is runnable and its functional workflows are implemented. Real English and Polish ASR works offline. Required Community-1 diarization, representative conversation quality, and sustained performance evidence remain missing. This report does not certify the complete MVP.

## Environment and reproducibility

The inspected host reports Apple M5 Pro, 68,719,476,736 bytes (64 GiB) RAM, native arm64 CPython 3.11.6, and available FFmpeg/FFprobe. Metal is accessible in the host session and under the network-denial validation policy. The ordinary execution sandbox does not expose Metal; inference tests used explicitly approved host execution.

`uv.lock` and `frontend/package-lock.json` pin dependencies. A separate clean core-only Python environment installed from the cached lock offline and passed the then-current 80 tests without model libraries. A second clean environment installed all 124 runtime/development/model packages from the same lock offline. This establishes reproducible dependency installation from cache, not successful gated model provisioning in a fresh account. Frontend build/TypeScript checks pass. Vite is pinned to 7.3.7; the recorded npm installation reported zero vulnerabilities.

`model-lock.json` pins all three candidate repositories. Local model manifests contain file sizes and SHA-256 hashes; weights and manifests remain in the external model cache. Runtime verifies local integrity and never requests downloads. Quality is hidden until a matching explicit compatibility spike succeeds. Compatibility success does not establish representative quality acceptance.

## Functional requirements

| Requirement | Result | Evidence and reproduction |
| --- | --- | --- |
| FR-01: local loopback application | PASS | Normal launcher served the built UI/API at 127.0.0.1; security and single-instance tests reject invalid hosts/origins/tokens and duplicate owners. `tests/test_scaffold.py`; actual browser report. |
| FR-02: validated bounded imports | PASS | All seven formats exercised with actual FFmpeg, byte/duration/storage/invalid-input failures and cleanup. Full audio decode validates duration before enqueue. Only supported local container/protocol inputs are permitted. `tests/test_media.py`, `tests/test_api.py`. |
| FR-03: original-language EN/PL ASR | PASS, short samples | Actual human FLEURS EN and PL plus JFK; PL retains diacritics, automatic detection returns pl, forced language selects transcription. These do not establish the long-form WER gate. Model spike and public-sample reports. |
| FR-04: recurring real speaker IDs | PENDING | Deterministic assignment implemented/tested; actual Community-1 access/assets unavailable. No synthetic IDs stand in for real recurring-voice evidence. |
| FR-05: valid timestamp/data contracts | PASS | Validated schemas, finite bounded intervals, explicit unknown attribution; actual EN/PL results assembled through this contract. `tests/test_contracts.py`, `tests/test_alignment.py`, real app flow. |
| FR-06: playback and seeking | PASS | Every supported input normalizes to mono 16 kHz WAV; Chromium plays and seeks real/synthetic results, active segment follows time. Media/API tests and browser report. Safari/Firefox unverified. |
| FR-07: persistent edits | PASS | Model data stays immutable; atomic revisions reject stale/invalid edits, restart/reload preserves saved text/names; browser draft survives 409 and injected 500. Jobs/API tests and browser report. |
| FR-08: four saved exports | PASS | Independent SRT/VTT parsers, Unicode/empty/degraded cases, latest saved edits, all four actual browser downloads; JSON preserves original/edit/provenance/turn data. Export/API tests. |
| FR-09: history and restart recovery | PASS | Completed/queued work and edits survive new store instances; interrupted attempts fail with retry; orphan/missing results reconciled. Lifecycle tests/report. |
| FR-10: cancellation and retry | PASS | FIFO/claim and cancel/publish races, duplicate retry rejection, process-group termination and immutable attempts; actual browser controls. Real-model cancellation evidence recorded separately when run. |
| FR-11: preserve ASR after speaker failure | PASS, injected failure | Pipeline test preserves text, explicit failed-speaker provenance/warning, null labels; focused Chromium degraded-result flow. Actual Community-1 inference remains pending. |
| FR-12: complete explicit deletion | PASS | Confirm dismiss/accept, active rejection, retry/delete race, partial-failure recovery, originals retained until deletion, shared assets preserved. Real ASR browser flow deletes owned job data. |
| FR-13: full cached offline inference | PARTIAL | Actual EN and PL ASR-only application workflows succeed under OS external-network denial. Full ASR plus Community-1 offline run remains pending. |

Fast verification: `.venv/bin/python -m pytest -q` and `.venv/bin/ruff check backend tests scripts`; frontend: `make build`. The latest full suite passed 130 tests with no skips, including immutable model-reference checks; the final command result is recorded in implementation progress. Model tests remain explicit; fast checks require no weights, credentials, or network. See [lifecycle evidence](lifecycle.md) and [browser evidence](browser-smoke.md).

## Actual ASR measurements

Fast values below are short compatibility measurements on snapshot `a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb`. Quality uses revision `49e6aa286ad60c14352c404340ded53710378a11`. Both profiles produced PL 0/20 and EN 2/19 errors on these same tiny references. Each run starts a fresh process. “Warm” means filesystem/runtime caches are warm; models are not persistently resident across jobs.

| Input / mode | Audio | Total spike | Peak RSS | Observed result |
| --- | --- | --- | --- | --- |
| JFK, initial host run, forced en |11.00s |15.359s |1,922,449,408 bytes | English, finite timestamps |
| JFK, warm OS-offline, forced en |11.00s |2.725s |1,897,381,888 bytes | Cached native ASR succeeds |
| FLEURS PL, OS-offline, forced pl |12.12s |2.607s |1,908,539,392 bytes | Polish diacritics, valid assembled timestamps |
| FLEURS PL, OS-offline, auto |12.12s |2.556s |1,910,538,240 bytes | Detects pl |
| FLEURS EN, OS-offline, forced en |10.56s |2.325s |1,908,244,480 bytes | English, valid assembled timestamps |
| FLEURS PL, Quality, OS-offline |12.12s |4.328s |3,669,344,256 bytes | Valid Polish timestamps |
| FLEURS EN, Quality, OS-offline |10.56s |3.597s |3,704,586,240 bytes | Valid English timestamps |

The actual browser application additionally completed the JFK ASR-only child pipeline in 2.548 s (ASR 1.064 s), and the PL child pipeline in 2.652 s (ASR 1.224 s). Browser submit-to-visible-result was 3.332 s and 4.334 s respectively. Playback, persisted edit/reload, four downloads, and confirmed deletion succeeded in both runs, with no observed external requests or uncaught page errors.

Against the official single-utterance FLEURS references, the disclosed normalization/scorer measured PL 0/20 errors (0%) and EN 2/19 errors (10.526%). These tiny, single-person read-speech samples are compatibility diagnostics. They **do not pass** the required independent 5–10 minute, two-speaker EN/PL reference gates. Source/license/revisions/hashes are in [public sample evidence](public-samples.md). Reference format and scoring policy are in [reference preparation](reference-format.md).

## Silence finding and bounded correction

The unguarded model hallucinated 10 non-whitespace characters on 5 seconds of exact digital silence. Its diagnostic no-speech probability was approximately 1.13e-10, illustrating that confidence-like values cannot certify correctness. No transcript content is published here.

The adapter now detects only exact zero-valued normalized PCM, skips model loading, and returns an empty transcript with the standard notice. The corrected offline run returned zero segments in 0.630 s with peak RSS 42,565,632 bytes. Tests establish that even one nonzero sample remains eligible for inference. No amplitude threshold or speech/music classifier was added. Quiet speech, room noise, music, overlap, and language switches still require representative challenge recordings; the initial failure remains documented.

## Offline gate

The application and every inference descendant ran under `scripts/offline.sb`, a macOS sandbox policy denying external networking while allowing loopback. A direct external socket connection was denied while Metal remained available. The browser additionally rejected any request outside its local app origin. Successful ASR runs required no download token and used hash-checked cached assets. Offline flags/telemetry settings are applied before inference imports; the worker removes HF token environment variables.

Reproduce after explicit model setup, with no other model job active:

```sh
/usr/bin/sandbox-exec -f scripts/offline.sb .venv/bin/python -m localscribe.launcher \
  --data-root /private/tmp/localscribe-real --port 8767 --no-browser
# Run tests/browser-real-asr.cjs with the browser dependency documented in browser-smoke.md.
# For Polish: REAL_SAMPLE=/absolute/fleurs-pl.wav REAL_LANGUAGE=pl node tests/browser-real-asr.cjs
```

The remaining full offline gate must repeat startup, real ASR and Community-1, playback, edits, all exports, and deletion with all assets cached. An ASR-only result cannot satisfy it.

## Required release gates and blockers

| Gate | Status | Required action |
| --- | --- | --- |
| Native MLX EN/PL compatibility | PASS | Short real samples and offline application flow recorded. |
| Native Community-1 CPU, regular/exclusive turns | BLOCKED | User personally accepts its access conditions and provides an external read/download credential. Explicit download currently fails without authenticated access. |
| Turbo versus large-v3 comparison | PENDING | Both snapshots passed short EN/PL compatibility; compare on identical representative conversation references before accepting a default. |
| English WER <=15% | PENDING | Approved 5–10 minute two-speaker recording plus corrected text. |
| Polish WER <=15% | PENDING | Approved 5–10 minute two-speaker recording plus corrected text. |
| Speaker-attributed speech >=90% | PENDING | Actual model plus hand-labelled turns; permutation-invariant mapping, ±250 ms collar, overlap excluded/reported separately. |
| Mixed language / three speakers / music / overlap | PENDING | Approved challenge recordings and applicable references. Exact-zero silence finding/correction is recorded separately. |
| 30 minute total RTF <=1.0 and no sustained memory pressure | PENDING | Representative 30 minute input, per-stage timing, peak memory and pressure observations. Short snippets cannot establish this target. |
| Approximately 60 minute stability/recovery | PENDING | Approved long recording. Deterministic interruption/recovery already passes. |
| Full cached network-disabled ASR+diarization | BLOCKED | Community-1 assets/access and real conversation input. |
| Reproducible clean full model setup | PARTIAL | Dependencies install cleanly from lock; gated setup and complete transitive-assets validation await user access. |

No failed or pending gate is labelled passed. Private recordings, corrected references, detailed outputs, tokens, database files and weights stay outside Git. No gated conditions were accepted for the user.

## Ticket disposition

LS-002, LS-003, LS-004, LS-005, LS-007, LS-008, LS-009, LS-010 have implementation and acceptance evidence. LS-001 and LS-006 remain incomplete pending real diarization/offline evidence; LS-011 remains incomplete pending full cached-model setup/run; LS-012 remains incomplete pending the release gates above. GitHub checkboxes and local Completion records track exact criterion-level evidence. Historical planning-status fields remain publication snapshots.

## Constructed language-switch challenge

A short challenge concatenated the two public FLEURS human recordings, PL then EN, without modifying their speech. Its duration was 22.68 s and the combined dataset reference had 39 words. Fast/Auto detected pl but returned only the Polish portion: 19 deletions, 39 reference words, WER 48.718%. This is a measured language-switch failure on a constructed challenge, not a representative conversation or a passed bilingual quality gate. No text was repaired, translated, or discarded by application postprocessing. The accepted specification already cautions that global detection/forcing does not guarantee correct language switches. A Quality run on the identical input is recorded separately.

The Quality/Auto probe on the identical constructed input also detected pl and omitted the English portion (19 deletions / 39 words, WER 48.718%; 4.178 s, peak RSS 3,715,563,520 bytes). Neither profile solved this short language-switch challenge; no default or acceptance threshold was changed to hide the result.

The final actual Polish browser repeat additionally verified per-recording model references and full runtime provenance after the model-pinning fix. Cached snapshots changing between import, queue, retry or publication cannot silently change a recording: preflight/retry/publication reject mismatches with `model_revision_changed`. Restore the originally pinned assets before retrying.

## Follow-up input validation

A follow-up audit verified that the constructed mixed input's normalized PCM is byte-identical to the concatenation of the separately normalized PL and EN samples: 193,920 and 168,960 frames respectively, 362,880 total at 16 kHz. PCM payload SHA-256: `aa28d02322e0a69987bb23d5b860dfbf98e9cee1854946f11a42dceca1444c8f`. Both portions retain the same RMS/peak values as their single-language inputs. The observed English omission is therefore not caused by dropped or altered audio during fixture construction.

The installed mlx-whisper 0.4.3 decoder explicitly rejects non-null `beam_size` with `NotImplementedError`; beam search is not an available alternative in this adapter. No decoding settings or acceptance thresholds were changed. The application had no active or stored jobs at this audit; Community-1 readiness remained false and no external Hugging Face credential was available. Representative conversation/reference prerequisites remain unresolved.

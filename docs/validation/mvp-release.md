# LocalScribe MVP release evidence

Date: 2026-10-18. **Release decision: MVP ACCEPTED FOR PERSONAL USE BY THE OWNER.**

## Owner acceptance and closeout

On 2026-10-18, Marcin reported that he had practically tested and improved the MVP, accepted the iteration as complete, and explicitly requested closure of the related tickets and merge into `main`. This is the new scope/acceptance decision required by the original plan. It supersedes the earlier NOT READY delivery decision for this personal-use MVP.

Functional FR-01–FR-13, real EN/PL ASR plus CPU Community-1, cached network-disabled workflows, long-recording operation, editing/history, exports and lifecycle handling retain their recorded evidence. The dark recording studio and the owner's practical improvements are included in the accepted source.

Accepted exceptions are explicit: the measured Polish WER remains above 15%; representative English comparison and the independent 90% attribution measurement remain unfinished; the exact selected-profile 30-minute benchmark is deferred despite the recorded 62-minute stability result. Instrumental-music and constructed language-switch failures remain disclosed. The owner accepts the current Fast profile for practical personal use. No target value, model output or historical result is changed to a numerical pass, and no further model/corpus search is required to close this MVP. These are known limitations for future work, not unresolved work in the accepted iteration.

LS-012 is resolved by this recorded owner decision; LS-001–LS-011 already have completion evidence. The merge pull request links the closure. Historical validation statuses below describe the original quantitative targets and remain evidence rather than a claim of full accuracy certification.

Closeout verification on 2026-10-18: `make check` passes all 213 model-free tests, Ruff and frontend TypeScript; `make build` passes. Actual Chromium on the accepted studio opens the restored 724-segment long recording, seeks/plays beyond one hour, checks editable drafts and reloads unchanged saved text, with zero page errors or external requests. Earlier model inference evidence retains its original dates.

## Historical validation checkpoint (2026-10-17)

The prior delivery decision was NOT READY because representative conversation quality and some formal performance/reference evidence were missing. The application was runnable and real English/Polish ASR plus CPU Community-1 already worked offline, including playback, saved text/speaker edits, exports and deletion. The owner's later acceptance above closes the MVP with these limitations explicitly accepted.

## Environment and reproducibility

The inspected host reports Apple M5 Pro, 68,719,476,736 bytes (64 GiB) RAM, native arm64 CPython 3.11.6, and available FFmpeg/FFprobe. Metal is accessible in the host session and under the network-denial validation policy. The ordinary execution sandbox does not expose Metal; inference tests used explicitly approved host execution.

`uv.lock` and `frontend/package-lock.json` pin dependencies. A separate clean core-only Python environment installed from the cached lock offline and passed the then-current 80 tests without model libraries. A second clean environment installed all 124 runtime/development/model packages from the same lock offline. After the user personally accepted Community-1 and authenticated locally, the clean full environment independently provisioned its pinned snapshot into a fresh isolated model directory. Its 10-file hash manifest exactly matches the main cache, and full doctor passes. A new account still requires user-owned authorization. Frontend build/TypeScript checks pass. Vite is pinned to 7.3.7; the recorded npm installation reported zero vulnerabilities.

`model-lock.json` pins all three candidate repositories. Local model manifests contain file sizes and SHA-256 hashes; weights and manifests remain in the external model cache. Runtime verifies local integrity and never requests downloads. Quality is hidden until a matching explicit compatibility spike succeeds. Compatibility success does not establish representative quality acceptance.

## Functional requirements

| Requirement | Result | Evidence and reproduction |
| --- | --- | --- |
| FR-01: local loopback application | PASS | Normal launcher served the built UI/API at 127.0.0.1; security and single-instance tests reject invalid hosts/origins/tokens and duplicate owners. `tests/test_scaffold.py`; actual browser report. |
| FR-02: validated bounded imports | PASS | All seven formats exercised with actual FFmpeg, byte/duration/storage/invalid-input failures and cleanup. Full audio decode validates duration before enqueue. Only supported local container/protocol inputs are permitted. `tests/test_media.py`, `tests/test_api.py`. |
| FR-03: original-language EN/PL ASR | PASS, short samples | Actual human FLEURS EN and PL plus JFK; PL retains diacritics, automatic detection returns pl, forced language selects transcription. These do not establish the long-form WER gate. Model spike and public-sample reports. |
| FR-04: recurring real speaker IDs | PASS, functional | Actual Community-1 CPU runs return regular/exclusive turns on human EN/PL; a constructed PL–EN–PL–EN sample returns two recurring anonymous IDs. This does not pass the reference-attribution quality gate. [Diarization evidence](diarization.md). |
| FR-05: valid timestamp/data contracts | PASS | Validated schemas, finite bounded intervals, explicit unknown attribution; actual EN/PL results assembled through this contract. `tests/test_contracts.py`, `tests/test_alignment.py`, real app flow. |
| FR-06: playback and seeking | PASS | Every supported input normalizes to mono 16 kHz WAV; Chromium plays and seeks real/synthetic results, active segment follows time. Media/API tests and browser report. Safari/Firefox unverified. |
| FR-07: persistent edits | PASS | Model data stays immutable; atomic revisions reject stale/invalid edits, restart/reload preserves saved text/names; browser draft survives 409 and injected 500. Jobs/API tests and browser report. |
| FR-08: four saved exports | PASS | Independent SRT/VTT parsers, Unicode/empty/degraded cases, latest saved edits, all four actual browser downloads; JSON preserves original/edit/provenance/turn data. Export/API tests. |
| FR-09: history and restart recovery | PASS | Completed/queued work and edits survive new store instances; interrupted attempts fail with retry; orphan/missing results reconciled. Lifecycle tests/report. |
| FR-10: cancellation and retry | PASS | FIFO/claim and cancel/publish races, duplicate retry rejection, process-group termination and immutable attempts; actual browser controls. Real-model ASR cancellation and CPU-diarization cancellation/retry both pass with no late result; [diarization evidence](diarization.md). |
| FR-11: preserve ASR after speaker failure | PASS, injected failure | Pipeline test preserves text, explicit failed-speaker provenance/warning, null labels; focused Chromium degraded-result flow. Successful actual Community-1 is separately verified; failure preservation remains an injected-error check. |
| FR-12: complete explicit deletion | PASS | Confirm dismiss/accept, active rejection, retry/delete race, partial-failure recovery, originals retained until deletion, shared assets preserved. Real ASR browser flow deletes owned job data. |
| FR-13: full cached offline inference | PASS | Actual EN and PL ASR plus CPU Community-1 browser workflows succeed under OS external-network denial and empty HF_HOME. Real labels/turns, playback, saved name/text edits, all exports and deletion pass with no observed external browser requests. [Browser evidence](browser-smoke.md), [model evidence](diarization.md). |

Fast verification: `.venv/bin/python -m pytest -q` and `.venv/bin/ruff check backend tests scripts`; frontend: `make build`. The latest full suite passed 210 tests with no skips, including immutable model-reference checks; the final command result is recorded in implementation progress. Model tests remain explicit; fast checks require no weights, credentials, or network. See [lifecycle evidence](lifecycle.md) and [browser evidence](browser-smoke.md).

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

The application and every inference descendant ran under `scripts/offline.sb`, a macOS sandbox policy denying external networking while allowing loopback. A direct external socket connection was denied while Metal remained available. The browser additionally rejected any request outside its local app origin. Successful ASR plus Community-1 runs required no download token and used hash-checked cached assets. Offline flags/telemetry settings are applied before inference imports; the worker removes HF token environment variables.

Reproduce after explicit model setup, with no other model job active:

```sh
HF_HOME=/private/tmp/localscribe-no-hf-home /usr/bin/sandbox-exec -f scripts/offline.sb \
  .venv/bin/python -m localscribe.launcher \
  --data-root /private/tmp/localscribe-full-offline --port 8767 --no-browser
# Run tests/browser-real-diarization.cjs with NODE_PATH documented in browser-smoke.md.
# For Polish: REAL_SAMPLE=/absolute/fleurs-pl.wav REAL_LANGUAGE=pl node tests/browser-real-diarization.cjs
```

Full real browser runs now pass nine checks each for EN and PL, with no mocks: default speaker-enabled import; source-language MLX GPU transcription; CPU Community-1 regular/exclusive turns; stable IDs; playback/seek; saved text/name edits and reload; four independent downloads; confirmed deletion. EN child total is 6.201 s (ASR 1.445 s, diarization 3.107 s), PL 6.768 s (ASR 1.215 s, diarization 3.906 s). Browser submit-to-result is 8.524 s and 8.523 s. Each had zero external-origin requests and zero uncaught page errors. These short functional passes do not establish long-form quality or performance.

## Original validation gates and recorded limitations

| Original validation target | Recorded result | Accepted limitation or future work |
| --- | --- | --- |
| Native MLX EN/PL compatibility | PASS | Short real samples and offline application flow recorded. |
| Native Community-1 CPU, regular/exclusive turns | PASS | User-owned access resolved; pinned complete snapshot and real offline EN/PL/recurring-voice inference verified. |
| Turbo versus large-v3 comparison | PENDING | Both snapshots passed short EN/PL compatibility; compare on identical representative conversation references before accepting a default. |
| English WER <=15% | PENDING | Prepared 300.89 s natural two-speaker SBC005 candidate; two source uncertain-hearing spans need audit. Both profile runs pending. |
| Polish WER <=15% | FAIL on predeclared natural sample | Human-corrected SpokesBiz 582.59 s: Fast 410/1929 = 21.2545%; Quality 390/1929 = 20.2177%. Neither profile passes; investigate justified alternatives without changing the threshold. |
| Speaker-attributed speech >=90% | PENDING | Actual model works; public reference times are automatically aligned or intonation units. Independently audited speech boundaries/labels remain required. |
| Mixed language / three speakers / music / overlap | PARTIAL / recognition failures | Natural three-voice/overlap processing succeeds; hand-label accuracy remains unverified. Instrumental music produces two spurious words; a review warning now preserves/exposes the result. Constructed mixed-language omission and exact-zero silence findings remain recorded. See [practical challenges](challenges.md). |
| 30 minute total RTF <=1.0 and no sustained memory pressure | PENDING | Representative 30 minute input, per-stage timing, peak memory and pressure observations. Short snippets cannot establish this target. |
| Approximately 60 minute stability/recovery | PASS, provisional Fast stability | Actual approved private 3762.517 s normalized recording completes offline in 1732.320 s wrapper wall, RTF 0.4604, peak RSS 4598317056 bytes; 866/866 pressure samples normal. Final release-profile selection and separate deterministic recovery evidence remain explicit. |
| Full cached network-disabled ASR+diarization | PASS | Complete actual EN/PL browser workflow with cached models, OS network denial and empty HF_HOME. |
| Reproducible clean full model setup | PASS | Clean locked full dependencies; independently repeated pinned speaker download yields identical complete SHA-256 manifest; full doctor ready. Runtime transitive assets verified by empty-HF-home offline inference. Initial account acceptance remains user-owned. |

No failed or pending gate is labelled passed. Private recordings, corrected references, detailed outputs, tokens, database files and weights stay outside Git. No gated conditions were accepted for the user.

## Ticket disposition

LS-002, LS-003, LS-004, LS-005, LS-007, LS-008, LS-009, LS-010 have implementation and acceptance evidence. LS-001, LS-006 and LS-011 are also complete with native full offline, recurring-voice, actual diarization-cancellation and clean-setup evidence. At the historical validation checkpoint, LS-012 remained incomplete pending the representative quality/performance/stability gates above. It is now closed under the owner acceptance decision recorded at the top of this report. GitHub checkboxes and local Completion records track exact criterion-level evidence. Historical planning-status fields remain publication snapshots.

## Constructed language-switch challenge

A short challenge concatenated the two public FLEURS human recordings, PL then EN, without modifying their speech. Its duration was 22.68 s and the combined dataset reference had 39 words. Fast/Auto detected pl but returned only the Polish portion: 19 deletions, 39 reference words, WER 48.718%. This is a measured language-switch failure on a constructed challenge, not a representative conversation or a passed bilingual quality gate. No text was repaired, translated, or discarded by application postprocessing. The accepted specification already cautions that global detection/forcing does not guarantee correct language switches. A Quality run on the identical input is recorded separately.

The Quality/Auto probe on the identical constructed input also detected pl and omitted the English portion (19 deletions / 39 words, WER 48.718%; 4.178 s, peak RSS 3,715,563,520 bytes). Neither profile solved this short language-switch challenge; no default or acceptance threshold was changed to hide the result.

The final actual Polish browser repeat additionally verified per-recording model references and full runtime provenance after the model-pinning fix. Cached snapshots changing between import, queue, retry or publication cannot silently change a recording: preflight/retry/publication reject mismatches with `model_revision_changed`. Restore the originally pinned assets before retrying.

## Follow-up input validation

A follow-up audit verified that the constructed mixed input's normalized PCM is byte-identical to the concatenation of the separately normalized PL and EN samples: 193,920 and 168,960 frames respectively, 362,880 total at 16 kHz. PCM payload SHA-256: `aa28d02322e0a69987bb23d5b860dfbf98e9cee1854946f11a42dceca1444c8f`. Both portions retain the same RMS/peak values as their single-language inputs. The observed English omission is therefore not caused by dropped or altered audio during fixture construction.

The installed mlx-whisper 0.4.3 decoder explicitly rejects non-null `beam_size` with `NotImplementedError`; beam search is not an available alternative in this adapter. No decoding settings or acceptance thresholds were changed. The application had no active or stored jobs at this audit; Community-1 readiness was false and no external Hugging Face credential was available at that earlier audit. The user has since resolved access; actual complete offline inference is now verified above. Representative conversation/reference prerequisites remain unresolved.

## Natural Polish comparison and long-recording checkpoint

The user requested a pause before shutting down the Mac. All model processes finished; both application launchers are stopped cleanly. Detailed private/public artifacts were preserved outside Git in `~/Library/Application Support/LocalScribe/validation/2026-10-16/` rather than relying on temporary files surviving restart.

A user-approved private stereo AAC recording normalized to 3762.5173125 seconds completed the full Fast/Auto plus CPU Community-1 pipeline under OS external-network denial and empty HF home. ASR took 74.215 s, diarization 1647.990 s, spike total 1731.359 s, observed child wall 1732.304 s and wrapper wall 1732.320 s. Peak process RSS was 4598317056 bytes. All 866 pressure samples were normal (1), zero unknown/unavailable, maximum sample gap 2.010 s; no sampled warning/critical interval occurred. Brief spikes between polls cannot be excluded. This passes the approximately 60-minute execution/memory-stability case for the provisional Fast profile, not reference accuracy or final model acceptance.

The output detected English and contained 724 display segments, five anonymous speaker IDs, 9160 words, 633 regular and 592 exclusive turns. An `alignment_fallback` warning remains visible; 12 segments have unknown attribution and 58 are marked overlapping. These are model observations, not independently verified speaker or text correctness. Validated private TXT/SRT/VTT/JSON exports were saved; independent subtitle parsers accepted all 724 cues including timestamps beyond one hour. The original remains untouched. No private filename, path, fingerprint or transcript text is published here.

Before model predictions, the Polish reference window was fixed to 0–582.59 s of the permitted natural SpokesBiz conversation. Human-corrected source text has 1929 tokens under the fixed scorer (the corpus's own count is 1933). Both profiles used identical forced-Polish ASR-only options and the same audio/reference. Diarization was intentionally disabled for this text comparison; these timings are not full-pipeline performance.

| Profile | Substitutions | Deletions | Insertions | WER | ASR / total spike | Peak RSS |
| --- | --- | --- | --- | --- | --- | --- |
| Fast | 143 | 255 | 12 | 410/1929 = 21.2545% | 16.543 / 18.207 s | 2201632768 bytes |
| Quality | 146 | 224 | 20 | 390/1929 = 20.2177% | 56.427 / 59.137 s | 3824828416 bytes |

**Neither profile passes the 15% target on this predeclared natural sample.** The earlier tiny FLEURS scores do not override this failure. The source was not reclassified or the threshold changed after observing results. Quality's short run also observed nine system-pressure warning samples, a 17.370 s sampled interval; this cannot be attributed exclusively to the model and is not a passed no-pressure gate. Fast's text run had all 11 pressure samples normal. Both returned the documented alignment fallback.

Next after the user's explicit resume: investigate deletion/substitution causes and evaluate the accepted first fallback, whisper.cpp/Metal, before any engine/scope decision; complete English comparison, representative 30-minute performance with the selected profile and remaining challenge/manual reference gates. No release profile was accepted against the original quantitative gates at that checkpoint; the current personal-use acceptance is recorded above. See [reference provenance and preparation](../research/reference-corpora.md). The 2026-10-16 pause was ended by the user on 2026-10-17; the Goal was still incomplete at that checkpoint; the later owner closeout decision supersedes that delivery status.

## Project-local history follow-up (2026-10-17)

The user requested transcript history and discoverable disk files in ignored `output/`. Implemented the new default, resumable/source-preserving migration, four automatic saved-revision copies, copyable folder paths, separate optional-copy failures and regeneration/startup repair. 208 model-free tests, Ruff, TypeScript/build and nine actual Chromium checks pass. The actual previous empty default store migrated successfully; populated history/edit/media migration is tested deterministically. See [local history evidence](local-history.md). This functional extension does not change or pass the unresolved inference quality gates.

The same history extension additionally passes 20 actual cached-model EN/PL browser checks under external-network denial and an empty HF home, including automatic copies after inference, saved edits matching disk exports and owned-folder deletion. Decoder diagnostics in [ASR diagnosis](asr-diagnosis.md) retain all five additional failures; no production profile changed. The user deferred independent manual speaker-boundary auditing to later practical checking on 2026-10-17. That metric remains unverified, and this report does not certify 90% attribution; personal-use MVP acceptance is a separate owner decision recorded above.

## Final practical diagnostics (2026-10-17)

The one pinned whisper.cpp/Metal Turbo beam5 comparison also fails Polish WER: 394/1929 = 20.4251%. CLI wall 21.268 s, peak RSS 2137702400 bytes, 13 normal pressure samples. Backend MTL0 and cached offline operation are verified; native zero-duration token/segment limitations and the reporter correction are disclosed in [ASR diagnosis](asr-diagnosis.md). No production engine change is justified by this result. No larger model was downloaded.

Natural three-voice/overlap processing succeeds in 58.712 s for 120 s audio with three recurring IDs. Instrumental 30 s music generates two spurious words and no speaker turns: a recorded recognition failure. The application now warns when ASR produces text but successful diarization detects no turns, preserving all model text. A real offline repeat verifies the warning; the complete fast suite has 210 passes. See [practical challenges](challenges.md). Manual attribution auditing remains deferred, and formal English/30-minute selected-profile gates remain pending. The application is available for practical use; the original quantitative quality targets remain uncertified; the MVP is accepted for personal use as recorded above.

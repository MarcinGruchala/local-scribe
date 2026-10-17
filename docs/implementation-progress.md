# Implementation progress

Updated: 2026-10-17. Branch: `codex/mvp-implementation`. Goal is **not complete**.

## Delivered

- Runnable source application: `make setup`, `make build`, explicit `make models`, `make doctor`, `make start`.
- Loopback/security, streamed validated media import, persistent FIFO worker, cancellation/retry/recovery, timestamped ASR/speaker adapters, deterministic assignment, playback/editing, saved TXT/SRT/VTT/JSON, complete confirmed deletion.
- Model repository/revisions pinned per recording and guarded across retry/publication; full runtime provenance in JSON. Private data now defaults to Git-ignored project `output/` by the user’s 2026-10-17 decision; models remain outside the checkout.
- Focused commits preserve planning baseline and implementation increments. Historical planning-status fields remain unchanged; local Completion records updated.

## Verification

- Final fast suite: 167 tests pass without weights/credentials; Ruff, TypeScript and production frontend build pass. A separate clean core-only environment also runs the suite; complete model dependencies install offline from the same cached lock.
- Actual FFmpeg covers all seven supported formats, full decoded validation, duration/byte/storage failures, local-only formats/protocols and original-byte retention.
- Actual Chromium fixture checks cover picker/drop, measured upload, refresh/stages, keyboard, playback, editing, all exports, save failures, cancellation/retry/deletion, degraded/overlap states, dirty navigation and paginated history. Reports: validation/browser-smoke.md and validation/lifecycle.md.
- Actual native MLX Fast and Quality EN/PL inference succeeds under OS external-network denial. Polish diacritics and Auto detection verified. Real EN/PL ASR-only browser workflows plus actual cancellation/retry pass. Final PL browser repeat verifies model pinning/runtime provenance.
- Public short FLEURS references: both profiles PL 0/20 errors, EN 2/19. These tiny diagnostics do not satisfy representative quality gates.
- Constructed PL→EN challenge: both profiles omit EN, 19/39 deletions. Initial exact-zero silence hallucination documented; exact-zero guard now returns empty result without loading models. No thresholds changed or failures hidden.
- All three pinned model snapshots are downloaded and hashed outside Git. User personally accepted Community-1 and authenticated locally. Real CPU regular/exclusive turns pass on EN/PL; constructed two-voice A-B-A-B returns two recurring IDs. All runs deny external networking; EN and two-voice runs also use empty HF_HOME. See validation/diarization.md. Clean full dependency environment independently provisions the same 10-file speaker manifest and passes full doctor.

## Resumed work (2026-10-17)

- User requested discoverable project-local history and disk exports. Implemented ignored `output/` default, source-preserving/resumable migration of the previous default store, automatic four-format copies after completion and saved edits, copy status/path UI, manual regeneration and startup repair. All 208 fast tests, Ruff, frontend checks/build and nine actual Chromium checks pass. The real empty legacy store migrated successfully; populated/edit/media cases pass deterministic tests. Evidence: validation/local-history.md. Normal app is running offline on8768; fixture harness8766 is stopped. Two real cached-model EN/PL browser runs pass20checks including automatic files, saved edits and deletion; raw artifacts are preserved in ignored output/validation/local-history.
- ASR diagnosis retains the fixed Polish reference and all failures. Fast context-only improves WER to 346/1929=17.9368%, still failing 15%. Default fallback alone is identical to baseline; removing word timestamps also fails and is diagnostic only. Quality context-only regresses to 66.5111%; standard context+temperature fallback recovers to 18.6625%, still failing. No production model/decoding change has been accepted.
- Heavy slot: alignment owns one pinned whisper.cpp/Metal Turbo comparison (weights downloading, build complete); root EN/PL actual offline file checks finished and the slot was returned. No production decoding/model change accepted. User defers independent manual boundary auditing to practical use; stop further gold-corpus acquisition and keep the90%metric unverified.

## Tracking

LS-001 through LS-011 are complete and closed on GitHub, with synchronized acceptance checkboxes and evidence. LS-012 remains open: functional FR-01–FR-13 and actual offline inference criteria pass; representative quality/performance/stability gates remain incomplete. Sanitized release decision: **NOT READY**, in validation/mvp-release.md.

## Previous paused checkpoint (2026-10-16)

Paused explicitly by the user on 2026-10-16. All inference finished, no model/validation child remains, and both the isolated8767 server and normal8768 app were shut down cleanly. The user explicitly resumed work on 2026-10-17. Models remain cached outside Git; originals remain untouched. Commits through975515b are pushed; this checkpoint is the next commit.

**Persistent artifacts:** `~/Library/Application Support/LocalScribe/validation/2026-10-16/` contains copied `localscribe-private-validation`, `localscribe-reference-research`, `localscribe-validation` and `localscribe-full-offline` directories plus `resume-checkpoint.json`. Do not depend on `/private/tmp` surviving reboot. Old metadata may contain temporary paths; substitute the corresponding persistent files. The exact private source path is only in the external private `run-source.json`, never Git.

## Verified since model access resumed

- Full offline EN/PL/recurring-voice browser flows: 27 checks; text/name edits, all exports, deletion, zero remote requests/page errors. Actual diarization cancellation and immutable retry pass.
- Clean full runtime independently provisions identical speaker hashes and completes actual Quality/CPU inference offline.
- The user's private62-minute recording completes full Fast/Auto + CPU offline: normalized3762.517 s; ASR74.215 s; diarization1647.990 s; wrapper1732.320 s; peak4598317056 bytes. All866 pressure samples normal, maximum gap2.010 s. Output724segments/5anonymousIDs; alignment_fallback retained. Private four-format exports and independent724-cue parsers pass; original retained. This is long stability for provisional Fast, not reference accuracy.
- Natural Polish predeclared582.59 s text comparison: Fast410/1929=21.2545% WER; Quality390/1929=20.2177%. **Both fail15%; neither profile is accepted for release quality.** Quality's short run also sampled17.370 s system-pressure warning; do not conceal or attribute it exclusively to the model.
- Latest fast suite:167 pass; Ruff and frontend build pass. Reproducible reference scripts and independent English parser review complete.

## Remaining sequential work

1. Investigate Polish deletion/substitution failures; evaluate accepted first fallback whisper.cpp/Metal if justified. No alternate engine was downloaded/run. Alignment's read-only fallback research was interrupted for pause. Never weaken15%/90% thresholds or reclassify the sample after seeing results.
2. Compare both candidates on `sbc005-en-300.89s.wav` plus matching reference. The predeclared source window374.19–675.08 has721normalizedwords, zeroindecipherable text, two uncertain-hearing spans and audit clips. Its IU times are not gold speech turns. `scripts/prepare-sbc-reference.py` is independently reviewed and reproducible.
3. Polish clip `pl-luz-000000-582590.wav` and matching reference contain100whole human-corrected segments; automatic times are diagnostic, ineligible for the hand-labelled90% attribution gate. Obtain an independent boundary/label audit before claiming that gate.
4. Run natural `CBIZ_LUZ_013.wav` (1801.301 s) for representative30-minute performance with the accepted profile. If profile changes, repeat long-profile checks as needed. `CBIZ_BIO_051.wav` (3752.384 s) and AMI EN2009d (5324.373 s) are available backups.
5. Run actual challenges sequentially: `en-sbc003-0540000-0660000-three-speaker.wav` (120 s, natural3voices/lexicaloverlap; reference diagnostic), `instrumental-piano-30s.wav` plus empty-speech reference, silence and documented mixed-language cases. No pending challenge is passed by source availability alone.
6. Update sanitized release evidence and LS-012. Only12 remains open; Goal is not complete. Latest public source records: docs/research/reference-corpora.md. Private/reference content never enters Git.

To start the normal app after resume: `LOCALSCRIBE_PORT=8768 make start` (8765 was previously occupied). Check current process ownership first. All model inference remains sequential; coordinate a single heavy slot. Models are in the persistent default cache. User recording paths are not needed for the prepared public comparisons, but independent manual reference audits and final model quality remain unresolved.

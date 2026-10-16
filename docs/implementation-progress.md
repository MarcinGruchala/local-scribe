# Implementation progress

Updated: 2026-10-16. Branch: `codex/mvp-implementation`. Goal is **not complete**.

## Delivered

- Runnable source application: `make setup`, `make build`, explicit `make models`, `make doctor`, `make start`.
- Loopback/security, streamed validated media import, persistent FIFO worker, cancellation/retry/recovery, timestamped ASR/speaker adapters, deterministic assignment, playback/editing, saved TXT/SRT/VTT/JSON, complete confirmed deletion.
- Model repository/revisions pinned per recording and guarded across retry/publication; full runtime provenance in JSON. Private roots and spike outputs cannot be placed inside the checkout.
- Focused commits preserve planning baseline and implementation increments. Historical planning-status fields remain unchanged; local Completion records updated.

## Verification

- Final fast suite: 153 tests pass without weights/credentials; Ruff, TypeScript and production frontend build pass. A separate clean core-only environment also runs the suite; complete model dependencies install offline from the same cached lock.
- Actual FFmpeg covers all seven supported formats, full decoded validation, duration/byte/storage failures, local-only formats/protocols and original-byte retention.
- Actual Chromium fixture checks cover picker/drop, measured upload, refresh/stages, keyboard, playback, editing, all exports, save failures, cancellation/retry/deletion, degraded/overlap states, dirty navigation and paginated history. Reports: validation/browser-smoke.md and validation/lifecycle.md.
- Actual native MLX Fast and Quality EN/PL inference succeeds under OS external-network denial. Polish diacritics and Auto detection verified. Real EN/PL ASR-only browser workflows plus actual cancellation/retry pass. Final PL browser repeat verifies model pinning/runtime provenance.
- Public short FLEURS references: both profiles PL 0/20 errors, EN 2/19. These tiny diagnostics do not satisfy representative quality gates.
- Constructed PL→EN challenge: both profiles omit EN, 19/39 deletions. Initial exact-zero silence hallucination documented; exact-zero guard now returns empty result without loading models. No thresholds changed or failures hidden.
- All three pinned model snapshots are downloaded and hashed outside Git. User personally accepted Community-1 and authenticated locally. Real CPU regular/exclusive turns pass on EN/PL; constructed two-voice A-B-A-B returns two recurring IDs. All runs deny external networking; EN and two-voice runs also use empty HF_HOME. See validation/diarization.md. Clean full dependency environment independently provisions the same 10-file speaker manifest and passes full doctor.

## Tracking

LS-001 through LS-011 are complete and closed on GitHub, with synchronized acceptance checkboxes and evidence. LS-012 remains open: functional FR-01–FR-13 and actual offline inference criteria pass; representative quality/performance/stability gates remain incomplete. Sanitized release decision: **NOT READY**, in validation/mvp-release.md.

## Current release validation

The user supplied a private stereo AAC/M4A recording, 3762.55 s (62m42.55), for the long test. The original is untouched. Its exact input path is stored only in `/private/tmp/localscribe-private-validation/run-source.json`; do not copy that path, filename or content into Git.

Root owns the exclusive inference slot. Full Fast/Auto ASR plus CPU diarization runs under `scripts/offline.sb` and empty HF_HOME with the new pressure monitor (exec session **35730**, spike PID **48612**). Output: `/private/tmp/localscribe-private-validation/long-fast-offline.json`, with private `.spike.json`/`.spike.wav` alongside. Latest sampled pressure is normal (1); the run has not finished. No other model job may start until it exits.

The isolated browser server at 8767 was stopped cleanly. The normal user app at 8768 remains running, idle, all models ready, zero jobs. Preserve it and user originals. Commits through dcaebc0 are pushed; benchmark monitor b61ce79 is committed and awaiting push. Fast checks now pass **153 tests**, Ruff and frontend build. LS-001–011 are closed; LS-012 remains open with functional/offline criteria checked and quality/performance gates pending.

## Available independent reference work

All media, annotations and raw results remain in `/private/tmp/localscribe-reference-research/`:

| Input | Evidence / remaining limit |
| --- | --- |
| SpokesBiz LUZ, 1801.301 s | Natural two-speaker Polish conversation; possible 30-minute performance input. |
| SpokesBiz BIO, 3752.384 s | Natural two-speaker interview; backup long input. |
| `pl-luz-000000-582590.wav` and `-reference.json` | Predeclared 582.59 s window, 100 complete human-corrected segments. Automatic speaker alignment is diagnostic, ineligible for the hand-labelled 90% gate. |
| English SBC005 | Prepared 300.89 s window (source 374.19–675.08), 721 normalized manual words, zero indecipherable text, two uncertain spans and audit clips. Earlier window was abandoned before inference after an indexed-overlap parser correction. Intonation units are not gold speech turns. |
| AMI EN2009d | Complete official CC BY 4.0 WAV acquired: 5324.373 s, 170379992 bytes, SHA eeb4a5ff47cadba8c75bdf32213b9264805027faa943c7f55eec0423c6ea4312. No inference yet. |
| `instrumental-piano-30s.wav` | Actual CC0 studio piano, empty speech reference and provenance; needs model challenge run. No manual-audition claim. |

The fixed-source Polish download/preparation CLI and four passing conversion tests are committed. Alignment owns `docs/research/reference-corpora.md`; genuine three-speaker SBC003 source window 540–660 s is ready externally as `en-sbc003-0540000-0660000-three-speaker.wav` with manifests. It has lexical overlap, but intonation-unit timestamps remain diagnostic. Scaffold is promoting audited English preparation to a repository CLI and parser regression tests. Agents must not run models.

## Next steps

1. Finish the private 62-minute run; inspect sanitized timing, warnings, peak RSS and sampled pressure. Do not declare a pass from an unfinished process.
2. Run Fast and Quality sequentially on the Polish 582.59 s and English 300.89 s references. Score immutable original text with the fixed policy; disclose the English uncertain word and unaudited speaker boundaries.
3. Select the profile only after both language comparisons. Run representative 30-minute LUZ performance with that profile, then genuine three-speaker/overlap/music/silence challenges. Repeat performance if the selected profile changes.
4. Commit reproducible public-reference tools and sanitized results, synchronize release evidence and LS-012. Never lower 15% WER or 90% attribution thresholds. The remaining independent manual reference audits must be resolved before release.

The long private input has no corrected text or speaker reference. The earlier request for recording paths can be narrowed to remaining manual audits after measured diagnostics. Do not repeat obsolete model-access blockers or substitute repeated voices for natural quality/performance evidence. Goal is not complete.

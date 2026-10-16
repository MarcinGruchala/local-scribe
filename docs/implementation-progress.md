# Implementation progress

Updated: 2026-10-16. Branch: `codex/mvp-implementation`. Goal is **not complete**.

## Delivered

- Runnable source application: `make setup`, `make build`, explicit `make models`, `make doctor`, `make start`.
- Loopback/security, streamed validated media import, persistent FIFO worker, cancellation/retry/recovery, timestamped ASR/speaker adapters, deterministic assignment, playback/editing, saved TXT/SRT/VTT/JSON, complete confirmed deletion.
- Model repository/revisions pinned per recording and guarded across retry/publication; full runtime provenance in JSON. Private roots and spike outputs cannot be placed inside the checkout.
- Focused commits preserve planning baseline and implementation increments. Historical planning-status fields remain unchanged; local Completion records updated.

## Verification

- Final fast suite: 136 tests pass without weights/credentials; Ruff, TypeScript and production frontend build pass. A separate clean core-only environment also runs the suite; complete model dependencies install offline from the same cached lock.
- Actual FFmpeg covers all seven supported formats, full decoded validation, duration/byte/storage failures, local-only formats/protocols and original-byte retention.
- Actual Chromium fixture checks cover picker/drop, measured upload, refresh/stages, keyboard, playback, editing, all exports, save failures, cancellation/retry/deletion, degraded/overlap states, dirty navigation and paginated history. Reports: validation/browser-smoke.md and validation/lifecycle.md.
- Actual native MLX Fast and Quality EN/PL inference succeeds under OS external-network denial. Polish diacritics and Auto detection verified. Real EN/PL ASR-only browser workflows plus actual cancellation/retry pass. Final PL browser repeat verifies model pinning/runtime provenance.
- Public short FLEURS references: both profiles PL 0/20 errors, EN 2/19. These tiny diagnostics do not satisfy representative quality gates.
- Constructed PL→EN challenge: both profiles omit EN, 19/39 deletions. Initial exact-zero silence hallucination documented; exact-zero guard now returns empty result without loading models. No thresholds changed or failures hidden.
- All three pinned model snapshots are downloaded and hashed outside Git. User personally accepted Community-1 and authenticated locally. Real CPU regular/exclusive turns pass on EN/PL; constructed two-voice A-B-A-B returns two recurring IDs. All runs deny external networking; EN and two-voice runs also use empty HF_HOME. See validation/diarization.md. Clean full dependency environment independently provisions the same 10-file speaker manifest and passes full doctor.

## Tracking

LS-001 through LS-011 are complete and closed on GitHub, with synchronized acceptance checkboxes and evidence. LS-012 remains open: functional FR-01–FR-13 and actual offline inference criteria pass; representative quality/performance/stability gates remain incomplete. Sanitized release decision: **NOT READY**, in validation/mvp-release.md.

## Required human prerequisites

Provide approved 5–10 minute English and Polish two-speaker recordings with corrected text/turns, mixed-language/three-speaker/music/overlap challenges, representative 30 minute performance and approximately 60 minute stability inputs. See validation/reference-format.md. Public snippets and constructed repeated voices cannot replace these gates. A request for available paths is pending; a research subagent is checking whether suitable licensed annotated public conversations are available.

## Current resumed work

The user resolved model access: explicit Community-1 download succeeds, native CPU and complete offline inference pass. Full actual browser EN/PL and constructed A-B-A-B cases each pass 9 checks with saved name/text edits, all exports and deletion, zero external requests/page errors. Actual cancel during diarizing prevents immediate/late publication; retry preserves model/options, completes, and deletes its own job. Clean locked full environment + independently provisioned speaker assets completes Quality/PL ASR+diarization under OS network denial and empty HF home (59.472 s total, including substantial first-use/import overhead; not a performance gate).

All model inference remains sequential. Root currently owns a free heavy slot. Validation server at http://127.0.0.1:8767 uses /private/tmp/localscribe-full-offline under scripts/offline.sb and empty HF_HOME (exec session 83952, PID 29472). Browser/cancellation jobs were deleted. Existing normal app at port 8768 still responds; inspect its state before any user-store actions. Shut down only the owned isolated server after checks.

Commits a3f14cc, 66d748d and 47d9c72 are pushed; LS-001/006/011 closed and LS-012 functional/offline checkboxes updated. Next: acquire and audit suitable public conversation references, then run remaining gates sequentially. Alignment subagent is checking public licensed manually annotated natural conversations: LUNA.PL (official BSD-2, Polish manual TRS/XML) and UCSB Santa Barbara Corpus (EN manual timestamped TRN). Fixed public metadata downloads use narrow scoped requests; generic curl requests were auto-review rejected. LUNA official archive is 1,171,789,169 bytes and ignores Range; agent is reading only a bounded 64 MiB prefix for WAV/TRS feasibility, not the whole corpus. Determine actual durations/access/annotation suitability before any quality claim. Root owns release/progress/ticket/GitHub records. Scaffold agent owns final browser report/setup docs; jobs agent completed configurable cancellation checker + 6 fast tests. No separate user-owned chats.

Representative quality/challenge/performance/stability gates remain required; no pending gate is complete. Do not repeat obsolete credential/access blockers. A request for user recording paths is pending, while public reference acquisition remains useful independent work.

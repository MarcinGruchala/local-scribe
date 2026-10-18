# Implementation progress

Updated: 2026-10-18. Branch: `codex/mvp-implementation`. **Goal is not complete.**

## Current checkpoint

- UI redesign (2026-10-18, user request): dark theme for the whole app and a unified recording studio replacing the separate Transcript / Listen & review views — sidebar navigation, transcript editor with speaker column, details inspector (speakers with talk-time share, current/selected segment, exports, local files), player dock with a zoomable speaker timeline, transcript search and keyboard shortcuts. No API or backend change. Fixture Chromium suites `browser-smoke`, `browser-review`, `browser-history`, `browser-states`, `browser-local-files` and `browser-navigation` pass; view-toggle steps were replaced with studio checks. `browser-restored-transcript` (needs the restored private recording) was updated for the removed toggle but not rerun; the model-backed `browser-real-*` scripts needed no change and were not rerun.

- The previously uncommitted history/review frontend work is now included in the repository: searchable paginated transcript history, direct listening/editing view, playback controls and draft-preserving navigation. Verification on 2026-10-18: 213 backend tests, Ruff, TypeScript/build and both new Chromium scripts pass (six review checks and five history checks). Private output remains ignored.

- The user resumed work and requested discoverable project-local history. Commit `39a7cc4` is pushed: ignored `output/` default, source-preserving/resumable legacy-store migration, automatic TXT/SRT/VTT/JSON after completion and saved edits, copyable folder paths, separate copy failures and repair. Decoder findings are documented in pushed `da6f1ef` and the latest validation update.
- Normal app is running at `http://127.0.0.1:8768` under OS external-network denial with empty `HF_HOME`. Fixture server 8766 is stopped. All model diagnostics are finished; the heavy slot is free. Do not start competing inference if a user job is active/queued.
- The user deferred independent manual speaker-boundary auditing to later practical checking. Do not pursue further gold-corpus acquisition or broad model/decoder searches. The 90% metric remains unverified; no threshold is silently weakened.
- LS-001–LS-011 remain complete/closed, with English follow-up evidence posted to #8/#9. LS-012 remains open with current failures/deferrals documented. Historical ticket planning-status fields are preserved. Release decision remains **NOT READY**.

## Verified

- Long-recording restoration: the new history view originally had no database entry for the saved benchmark export. A locked maintenance command now registers the existing real result atomically, preserves edits/model data, copies playback/original media and avoids duplicates. Actual Chromium confirms all 724 segments, playback/seek beyond one hour, editable drafts and unchanged saved text after reload. See `docs/validation/transcript-restoration.md`.

- Latest fast suite: 213 model-free tests; Ruff, TypeScript and frontend production build pass. Clean locked core/full environments were previously verified separately. All seven media formats, security, FIFO, cancellation/retry/recovery, editing, four exports and deletion have evidence.
- History extension: nine actual Chromium fixture checks plus 20 actual cached-model EN/PL offline browser checks pass. Disk bytes match exports before/after saved edits; owned folders are deleted. Migration tests cover schema 1, SIGKILL before mkdir/after copying, restart locks, canonical edits/media, and repair in the new folder. See `docs/validation/local-history.md`.
- Cached native MLX ASR and CPU Community-1 work offline in EN/PL and constructed recurring-voice cases, including real cancellation/retry. All three production snapshots are hashed outside Git; the user personally resolved model authorization.
- Private long run: 3762.517 s normalized audio, Fast/Auto+CPU, wrapper 1732.320 s, peak 4598317056 bytes, 866 normal pressure samples. Four private exports/724 cues pass independent parsers; original retained. This establishes provisional Fast stability, not reference quality.
- Fixed Polish 582.59 s / 1929 words: baseline Fast 21.2545%, Quality 20.2177% WER. Five standard MLX diagnostics all fail 15%; best 17.9368%. One pinned whisper.cpp/Metal Turbo beam5 run also fails:394 /  1929 = 20.4251%, 21.268 s CLI, 2137702400 bytes peak, 13 normal pressure samples. No production model/decoding change accepted. See `docs/validation/asr-diagnosis.md`.
- Natural 120 s three-voice/overlap challenge completes offline: 29 segments, three recurring anonymous IDs, eight overlap segments, 58.712 s child total, 5270323200 bytes peak, 31 normal pressure samples. Label/boundary accuracy is unverified.
- Instrumental 30 s challenge produces two spurious words and zero speaker turns. This is a recorded recognition failure. Added `no_speaker_turns` review warning without suppressing text; a real offline repeat verifies the warning and preserved output. Prior silence/mixed-language failures remain documented. See `docs/validation/challenges.md`.

## Data and artifacts

- Active history/media/database/transcripts: ignored project `output/`; per-job files under `output/jobs/<job-id>/`. Existing previous default store is retained as a backup; validation files are not migrated. Deletion affects the active store only.
- Prior private long exports: ignored `output/validation/long-recording/transcript.{txt,srt,vtt,json}`. The user requested access from the new history/review view. The real benchmark result has now been explicitly restored as a completed editable history entry, with copied original/normalized audio and restoration provenance; no inference was rerun. Original benchmark artifacts remain intact. New browser JSON/screenshots: `output/validation/local-history/`.
- Models: `~/Library/Caches/LocalScribe/models/`. Prior persistent references/results: `~/Library/Application Support/LocalScribe/validation/2026-10-16/`, including `localscribe-reference-research`, `localscribe-validation`, `localscribe-private-validation`, `localscribe-full-offline`, `localscribe-asr-diagnosis-2026-10-17`, and `localscribe-whisper-cpp-2026-10-17`. The exact private input path is only in external `run-source.json`.
- New challenge raw/aggregate reports: `~/Library/Application Support/LocalScribe/validation/2026-10-17/challenges/`. Do not depend on temporary directories surviving restart. Raw recordings/transcripts/weights/credentials never enter Git.

## Remaining formal release evidence

1. Polish WER target fails; neither production profile nor the alternative diagnostic is accepted for release quality. Broader searches are deferred in favor of practical use.
2. English candidate `sbc005-en-300.89s.wav` / matching reference has 721 normalized words and two source uncertain-hearing spans. Representative profile comparison is not run. IU times are not gold speech boundaries.
3. Manual attribution accuracy is deferred/unverified at the user's request. Do not claim 90%.
4. Representative 30-minute performance with an accepted release profile remains pending. Available natural input: `CBIZ_LUZ_013.wav` (1801.301 s). The private 62-minute provisional run does not replace this specific gate.
5. Challenge recognition failures remain explicit; functional success does not certify text or speaker accuracy. Update #12/release evidence on any later practical or formal evaluation; do not mark the Goal complete while required evidence is missing.

Start when stopped: `LOCALSCRIBE_PORT=8768 make start`; check current port ownership first. Preserve original media and ignored output; keep inference sequential.

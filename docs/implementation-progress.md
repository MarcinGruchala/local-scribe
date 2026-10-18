# Implementation progress

Updated: 2026-10-18. Delivery status: **MVP ACCEPTED BY MARCIN; closeout and merge authorized.**

## Closeout decision

Marcin practically tested and improved the application, accepted this MVP as complete, and requested closure of its tickets and merge to `main`. Specification section 13 and the release report record that explicit acceptance. The prior NOT READY status is superseded for this personal-use iteration. Failed and unfinished formal quality/benchmark targets remain documented accepted limitations; none is relabelled a numerical pass. No additional reference audit or model search is required for closeout.

The accepted source includes the dark unified recording studio, searchable history, restored long-recording playback/editing, local exports, and the full existing offline workflow. LS-001–LS-011 already have completed GitHub issues; LS-012 is resolved by the recorded acceptance/waivers and linked to the merge pull request. Local publication planning-status fields remain unchanged.

## Merge handoff

Closeout is prepared in an isolated managed worktree on `codex/mvp-closeout`, based on implementation/UI commit `dfb9f0b`. Target: `main`. Closeout verification on 2026-10-18: `make check` (213 passes, Ruff, TypeScript), `make build`, and the actual read-only long-recording Chromium check all pass. PR/merge identity and final remote states are recorded in the closeout PR. Runtime/process statements from earlier checkpoints are historical, not current monitoring. Private `output/` and external cached models remain untouched and excluded from Git.

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

## Accepted limitations and future work

Polish WER remains above 15%; representative English comparison, independent 90% attribution scoring and the exact selected-profile 30-minute benchmark are deferred. Instrumental-music hallucination and mixed-language omission remain recorded. The separate 62-minute stability result does not prove the deferred formal targets. These limitations are accepted by the owner for this MVP; further investigation requires a separate request. See `docs/validation/mvp-release.md`, `asr-diagnosis.md` and `challenges.md`.

Start locally: `make start`, or `LOCALSCRIBE_PORT=8768 make start` if the default port is occupied. Check port/job ownership before runtime tests, preserve original media and ignored output, and keep heavy inference sequential.

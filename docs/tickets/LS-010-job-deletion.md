# LS-010 — Delete recordings and all owned data

Planning status at publication: open  
GitHub issue: [#10](https://github.com/MarcinGruchala/local-scribe/issues/10) — live status tracker  
Dependencies: LS-007, LS-008  
Requirements: FR-12; accepted retention decision 4.1; specification sections 4 and 8

## Outcome

Explicit deletion removes a terminal job and every file it owns. Conversion and normal processing retain the original recording.

## Work

- Add an in-app confirmation that names the selected recording and explains source/transcript removal.
- Implement job-scoped deletion for completed, failed, and cancelled jobs. Reject queued/active jobs with `409` and explain cancel-first behavior.
- Remove original media, normalized/playback media, immutable results, edits, attempt outputs, and database records; preserve shared model snapshots.
- Make interrupted deletion recoverable without exposing a completed success while owned data remains. Handle missing files and repeated requests according to a documented contract.
- Invalidate history/detail/player/editor state after successful removal and avoid deletion races with concurrent retry.

## Acceptance criteria

- [ ] Cancelling the confirmation leaves the complete job intact.
- [ ] Successful delete removes all job data, including retained source and failed-attempt files.
- [ ] Active/queued deletion cannot race a worker into using removed media.
- [ ] Partial filesystem failure remains visible and can be retried/reconciled after restart.
- [ ] Shared models and other jobs remain intact.
- [ ] Normal conversion, export, and application shutdown do not delete originals.

## Verification

Use temporary data roots with two jobs and a shared model fixture. Inject a filesystem failure during deletion, restart, and verify recovery. Test retry/delete races and the confirmation flow.

## Completion record

Not started.

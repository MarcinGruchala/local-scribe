# LS-004 — Run durable jobs with cancellation and recovery

Planning status at publication: open  
GitHub issue: [#4](https://github.com/MarcinGruchala/local-scribe/issues/4) — live status tracker  
Dependencies: LS-003  
Requirements: FR-09, FR-10; specification sections 7 and 10

## Outcome

One supervised worker processes the persistent queue without blocking HTTP requests. Cancel, retry, restart, and late-result races have defined outcomes.

## Work

- Implement transactional FIFO claims, immutable attempt options, stage status, elapsed time, and one active inference child.
- Run normalization and inference outside the HTTP event loop. Start with a deterministic fake model adapter so lifecycle behavior is independently testable.
- Implement idempotent cancel and explicit retry endpoints. Cancel requests terminate the child process group with a grace period and forced-stop fallback.
- Permit publication only from the current active uncancelled attempt. Resolve publish/cancel races transactionally and discard stale child output.
- Stage and atomically publish validated results. Reconcile orphan files/results after an interrupted publication.
- On restart stop any safely identified surviving child, fail interrupted attempts with `interrupted`, retain queued work, and preserve completed results. Avoid treating a reused PID as a known child.

## Acceptance criteria

- [ ] Two queued jobs run sequentially in FIFO order; the API stays responsive during model work.
- [ ] Cancelling queued or active work has the documented terminal outcome and prevents stale publication.
- [ ] Repeating cancel is safe; retry enqueues exactly one new attempt and rejects invalid states.
- [ ] A crash/restart preserves completed and queued jobs and exposes a retry action for interrupted attempts.
- [ ] Publication failure or orphaned temporary output does not produce a broken completed job.
- [ ] No worker holds a SQLite transaction through model inference.

## Verification

Use child fixtures that pause at explicit synchronization points to test cancel/publish races, duplicate claims, process termination, and restart recovery deterministically. Tests must not need real models. Record the single-instance ownership strategy.

## Completion record

Not started.

# LS-006 — Assign speakers and preserve degraded results

Planning status at publication: open  
GitHub issue: [#6](https://github.com/MarcinGruchala/local-scribe/issues/6) — live status tracker  
Dependencies: LS-005, LS-001 diarization compatibility evidence  
Requirements: FR-04, FR-05, FR-11, FR-13; specification sections 5, 6, and 7

## Outcome

Completed transcripts show stable within-recording speaker IDs. If diarization fails, successful text remains available with an explicit warning and null speaker labels.

## Work

- Implement the Community-1 adapter with local snapshots, CPU as the baseline, automatic count or validated exact count, and regular/exclusive turns.
- Implement deterministic word assignment: greatest positive overlap, then earliest turn start, then stable ID; unmatched words keep a null speaker.
- Use segment overlap when word timestamps are absent and emit an alignment warning. Preserve all text and original model segments.
- Assemble display segments at speaker changes and model boundaries, keep IDs in first-occurrence order, and mark overlap using regular turns.
- Persist immutable inference output, words, both forms of turns, warnings, and provenance through the guarded publication path.
- Honor the accepted fallback: a speaker-stage error after ASR produces `completed` with warnings and unavailable labels. User cancellation is cancellation, never a degraded success. A shared assembly/storage failure remains a job failure.

## Acceptance criteria

- [ ] Real multi-speaker audio produces recurring anonymous IDs, not real-person identity claims.
- [ ] Assignment is deterministic for turns, gaps, ties, short words, and overlapping speech.
- [ ] Missing word timestamps trigger the documented fallback and warning without dropping text.
- [ ] A forced diarization failure preserves ASR text, sets null labels, and states that diarization failed.
- [ ] Disabled diarization is recorded as intentional and does not show a failure warning.
- [ ] Cancel during diarization cannot publish any result for that cancelled attempt.
- [ ] Offline inference does not download missing transitive assets or send telemetry.

## Verification

Unit-test alignment and assembly against hand-authored words/turns. Use an injected diarization failure for deterministic degraded-result tests. Run a real local two-speaker sample separately; LS-012 measures final attribution quality.

## Completion record

Not started.

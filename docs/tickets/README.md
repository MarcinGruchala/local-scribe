# LocalScribe MVP implementation backlog

Date: 2026-10-16. Status: published to GitHub; all 12 issues were open at publication. [GitHub Issues with the MVP label](https://github.com/MarcinGruchala/local-scribe/issues?q=is%3Aissue%20label%3AMVP) are the live status tracker. Local ticket files preserve the planning baseline and issue links. No application code was implemented during planning.

Source of truth: [accepted specification](../specs/mvp.md). Supporting evidence: [model research](../research/local-asr-models.md). Review artifact: [interactive plan](../plans/mvp.packed.html).

## MVP closeout — 2026-10-18

Marcin accepted the iteration after practical testing and improvements and requested ticket closure and merge into `main`. LS-001–LS-011 already have completion evidence; LS-012 is resolved by that explicit owner acceptance with the documented quality/benchmark exceptions. The original planning statuses and execution policy below are retained as history. Their strict quantitative blocking rule is superseded for this iteration by [specification section 13](../specs/mvp.md#13-owner-acceptance-and-mvp-closure--2026-10-18). No missing or failed measurement is labelled passed; see [release evidence](../validation/mvp-release.md).

## Accepted product decisions

- If diarization fails after successful ASR, keep the transcript and show a clear warning with unavailable speaker labels.
- Retain original media until explicit job deletion. Deletion also removes all derived job data, but not shared models.
- Import existing audio/video files. Use dedicated local ASR and diarization engines without requiring LM Studio or Ollama.

## Tickets and dependencies

| ID | Ticket | GitHub issue | Depends on | Requirement coverage |
| --- | --- | --- | --- | --- |
| LS-001 | [Validate local model compatibility](LS-001-model-spike.md) | [#1](https://github.com/MarcinGruchala/local-scribe/issues/1) | None; gated access needed for real diarization | FR-03, FR-04, FR-05, FR-13 |
| LS-002 | [Create the local application scaffold](LS-002-app-scaffold.md) | [#2](https://github.com/MarcinGruchala/local-scribe/issues/2) | None; use LS-001 findings for model dependency locks | FR-01, FR-13 |
| LS-003 | [Import and retain local media](LS-003-media-import.md) | [#3](https://github.com/MarcinGruchala/local-scribe/issues/3) | LS-002 | FR-02, FR-12 |
| LS-004 | [Run durable jobs with cancellation and recovery](LS-004-job-worker.md) | [#4](https://github.com/MarcinGruchala/local-scribe/issues/4) | LS-003 | FR-09, FR-10 |
| LS-005 | [Produce timestamped ASR results](LS-005-asr-adapter.md) | [#5](https://github.com/MarcinGruchala/local-scribe/issues/5) | LS-001 ASR evidence, LS-004 | FR-03, FR-05, FR-13 |
| LS-006 | [Assign speakers and preserve degraded results](LS-006-speaker-pipeline.md) | [#6](https://github.com/MarcinGruchala/local-scribe/issues/6) | LS-005, LS-001 diarization evidence | FR-04, FR-05, FR-11, FR-13 |
| LS-007 | [Build import, readiness, and job history screens](LS-007-job-ui.md) | [#7](https://github.com/MarcinGruchala/local-scribe/issues/7) | LS-004; live inference follows LS-005/006 | FR-01, FR-02, FR-09, FR-10, FR-11 |
| LS-008 | [Play and edit saved transcripts](LS-008-transcript-editor.md) | [#8](https://github.com/MarcinGruchala/local-scribe/issues/8) | LS-006, LS-007; fixtures permit earlier UI work | FR-05, FR-06, FR-07, FR-11 |
| LS-009 | [Export the last saved transcript](LS-009-exports.md) | [#9](https://github.com/MarcinGruchala/local-scribe/issues/9) | LS-008 | FR-08 |
| LS-010 | [Delete recordings and all owned data](LS-010-job-deletion.md) | [#10](https://github.com/MarcinGruchala/local-scribe/issues/10) | LS-007, LS-008 | FR-12 |
| LS-011 | [Package explicit setup and offline startup](LS-011-local-setup.md) | [#11](https://github.com/MarcinGruchala/local-scribe/issues/11) | LS-001, LS-006, LS-007 | FR-01, FR-13 |
| LS-012 | [Validate the complete offline MVP](LS-012-release-validation.md) | [#12](https://github.com/MarcinGruchala/local-scribe/issues/12) | LS-009, LS-010, LS-011 | FR-01 through FR-13 |

Dependencies express implementation order, not an instruction to run separate agents. One agent can work sequentially. LS-002 through LS-004 can proceed while model access is unavailable. UI and deterministic tests can use fixtures when a model gate is pending; real inference and release gates cannot.

## Execution policy

1. Read the specification and the current ticket before changing code. Preserve the accepted behavior and module contracts.
2. Start with LS-001. Record native runtime compatibility and model access separately from transcription quality. Create no claim of measured quality without reference audio.
3. Continue through available dependencies. Implement one ticket at a time unless a later instruction explicitly requests parallel work.
4. Track live progress in the corresponding GitHub issue. Keep it open while work or prerequisites remain; update acceptance checkboxes and record any blocker and completed evidence. Close it only after its acceptance criteria pass. Local planning statuses are publication snapshots.
5. Record changed paths and relevant verification under each ticket's Completion record. Use a distinct result for real inference and fixture-based checks.
6. Run checks appropriate to the change. Fast tests must not download models, access private samples, or require tokens. Keep heavyweight model checks explicit.
7. Do not ask again about the accepted fallback or retention behavior. Resolve routine implementation choices within the specification.
8. Report only blockers that need human action: gated access acceptance, missing reference recordings, a failed model/hardware gate, or a scope decision. Continue independent work.
9. Keep private recordings, transcripts, credentials, models, and machine-specific benchmark output outside Git. Commit only redistributable fixtures and sanitized evidence.
10. Mark LS-012 done only when actual offline inference and the documented acceptance gates pass. A functional prototype with pending model evidence is not a verified release.

GitHub issue state and planning records are project tracking data; they do not control the Codex goal tool.

## Evidence and completion

Use relative links in committed records and include reproducible commands when those commands exist. Record an exact dependency/model manifest after the spike, not an invented version set. Put a sanitized model compatibility report in `docs/research/model-spike.md` and a sanitized release report in `docs/validation/mvp-release.md` during implementation. Keep detailed private benchmark outputs in the local data root and link to them only from uncommitted local records.

All LS-001 through LS-012 tickets must be complete for the verified MVP. If a target fails, preserve the measured result and state what remains outstanding; do not silently lower a threshold.

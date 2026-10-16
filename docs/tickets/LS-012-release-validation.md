# LS-012 — Validate the complete offline MVP

Planning status at publication: open  
GitHub issue: [#12](https://github.com/MarcinGruchala/local-scribe/issues/12) — live status tracker  
Dependencies: LS-009, LS-010, LS-011; representative user-approved recordings and references  
Requirements: FR-01 through FR-13; specification sections 9 and 10

## Outcome

A recorded end-to-end result establishes whether the application meets the accepted functional, bilingual quality, speaker, privacy, and performance targets on the target Mac.

## Work

- Run the fast checks, frontend build, and browser workflow: import, refresh, stage status, playback, text/name edits, all exports, cancel/retry, and deletion.
- Run real English and Polish jobs with two speakers and corrected references. Include mixed language, three speakers, silence/music, and overlap as challenge cases.
- Compare turbo and large-v3 with the same inputs/settings. Record model revisions, cold/warm timing, per-stage timing, total real-time factor, peak memory, and memory pressure.
- Measure WER separately per language. Measure speaker attribution with permutation-invariant labels, a 250 ms collar, and overlap excluded; report overlap separately.
- Run a representative 30-minute performance case and a longer approximately 60-minute stability/recovery case when available.
- Run the complete cached-model workflow with network disabled, including startup, speaker processing, media playback, edits, export, and deletion.
- Publish a sanitized `docs/validation/mvp-release.md` acceptance matrix and update ticket/spec references as appropriate. Keep private samples and detailed transcripts outside Git.

## Acceptance criteria

- [ ] FR-01 through FR-13 each have concrete pass/fail evidence and a reproducible command or workflow.
- [ ] Clean reference WER is at most 15% separately for English and Polish, or the failed target is explicitly recorded for a scope/model decision.
- [ ] Speaker-attributed reference speech duration is at least 90% correct under the specified scoring policy, or the failed target is explicitly recorded.
- [ ] Total real-time factor is at most 1.0 on the representative 30-minute file without sustained memory pressure, or the measured shortfall is explicitly presented for review.
- [ ] Actual offline ASR plus diarization succeeds; fixture adapters do not stand in for model evidence.
- [ ] All earlier tickets are done, setup is reproducible, and remaining human prerequisites are resolved.
- [ ] The release report distinguishes functional success, quality, performance, and unresolved limitations. No failed or pending gate is labelled passed.

## Verification

Use the specification's normalization/scoring policy and report fixture duration, language, speaker count, and reference preparation without private contents. A missing sample or model gate leaves the relevant release criterion pending and this ticket incomplete; it does not invalidate unrelated verified work.

## Completion record

2026-10-16: Incomplete; paused at the user's request before shutdown. Functional FR-01–FR-13 and actual offline inference pass; LS-001–011 are closed. The user's private 62-minute full Fast/CPU run completed offline (1732.320 s wrapper wall, peak RSS 4598317056 bytes, 866 normal pressure samples); original and private exports preserved outside Git. Predeclared natural Polish WER fails for both Fast (21.2545%) and Quality (20.2177%), so neither profile is accepted for release quality. English comparison, hand-audited speaker boundaries, selected-profile 30-minute performance and remaining challenges still require work. All artifacts are preserved in the persistent external validation root; see docs/implementation-progress.md and docs/validation/mvp-release.md. No pending or failed gate is labelled passed.

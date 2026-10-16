# LS-005 — Produce timestamped ASR results

Planning status at publication: open  
GitHub issue: [#5](https://github.com/MarcinGruchala/local-scribe/issues/5) — live status tracker  
Dependencies: LS-001 ASR compatibility evidence, LS-004  
Requirements: FR-03, FR-05, FR-13; specification sections 6 and 9

## Outcome

The worker uses the accepted local ASR model to produce original-language text and timestamps for English or Polish recordings.

## Work

- Implement the MLX ASR adapter against the normalized audio contract. Load pinned local model paths only.
- Map `auto`, `en`, and `pl` to transcription settings and preserve requested/detected language. Never enable translation implicitly.
- Return words, model segments, timings, and model/device provenance. Validate finite timestamps against audio duration and preserve text when word timestamps are unavailable.
- Expose `Fast` by default and `Quality` only when its snapshot and compatibility evidence exist. Make any default change traceable to the benchmark result.
- Integrate stage updates and cancellation through LS-004. Release model memory before the next stage where supported.
- Support an empty transcript with an explicit notice. Keep hallucination and silence handling visible in evidence rather than claiming the model cannot hallucinate.

## Acceptance criteria

- [ ] Real English and Polish samples yield their source languages, including Polish diacritics.
- [ ] ASR results obey the timestamp/data contract and preserve model text and provenance.
- [ ] Forced language selects transcription rather than translation; automatic mode records its detection result.
- [ ] Missing/corrupt model assets fail readiness or inference clearly without network downloads.
- [ ] Cancellation stops model work and cannot publish stale output.
- [ ] An ASR-only job can complete through the shared worker/result contract.

## Verification

Test adapter mapping and validation with fixtures in the fast suite. Run actual local inference as an explicit heavyweight check and preserve sanitized stage/device evidence. Do not treat fixture output as evidence of bilingual accuracy.

## Completion record

Not started.

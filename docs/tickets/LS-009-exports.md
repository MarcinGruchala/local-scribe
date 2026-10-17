# LS-009 — Export the last saved transcript

Planning status at publication: open  
GitHub issue: [#9](https://github.com/MarcinGruchala/local-scribe/issues/9) — live status tracker  
Dependencies: LS-008  
Requirements: FR-08; specification sections 5 and 7

## Outcome

The user exports readable text, valid subtitles, or a structured JSON record using the last saved text and speaker names.

## Work

- Implement TXT, SRT, VTT, and versioned JSON exporters plus the job export endpoint and UI controls.
- Generate all exports from one consistent saved revision. Prefer `editedText` when present, including an intentional empty edit.
- Include readable speaker names/prefixes and valid subtitle timing. Keep unknown speakers explicit. Define and test a deterministic cue policy without claiming perfect subtitle layout.
- Preserve segments, raw words/turns, warnings, language, revisions, and provenance in JSON. Clearly distinguish saved display text from immutable model text.
- Use safe download filenames and correct content types. Unsupported formats and unavailable results return structured errors.

## Acceptance criteria

- [ ] All four formats download and include the latest saved edits and speaker names.
- [ ] SRT/VTT parse successfully, use their required headers/time separators, and have ordered nonnegative cues.
- [ ] JSON declares schema version 1 and retains the required inference/edit metadata.
- [ ] Empty and degraded transcripts produce defined valid exports with appropriate warnings or notices.
- [ ] Unsaved editor text is not silently substituted for the saved revision.

## Verification

Test timestamp rounding, Unicode/Polish diacritics, multiline text, null speakers, empty edits, and empty transcripts. Parse subtitles with an independent parser or a standards-based validation routine. Compare export behavior to the persisted transcript contract rather than mirroring formatter internals.

## Completion record

2026-10-16: Completed. TXT/SRT/VTT/JSON use one saved revision including intentional empty edits, Unicode and names. Independent subtitle parsers validate cues; JSON retains raw/edit/provenance/turn data. Empty/degraded cases pass tests; all four real browser downloads pass. See tests/test_exports.py and browser evidence.

2026-10-17 follow-up: User requested project-local history/files. Saved transcripts now automatically maintain four readable formats under ignored `output/jobs/<job-id>/`, with copyable paths, repair feedback and source-preserving legacy-store migration. Canonical edits remain successful if optional file copies fail. 208 fast tests and nine actual Chromium checks pass; see docs/validation/local-history.md. Historical planning status is preserved.

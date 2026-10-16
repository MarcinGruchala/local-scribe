# LS-008 — Play and edit saved transcripts

Planning status at publication: open  
GitHub issue: [#8](https://github.com/MarcinGruchala/local-scribe/issues/8) — live status tracker  
Dependencies: LS-006 and LS-007; transcript fixtures permit earlier UI work  
Requirements: FR-05, FR-06, FR-07, FR-11; specification sections 4 and 7

## Outcome

The user reads timestamped speaker segments, seeks the recording, corrects text, and renames speakers without losing saved work.

## Work

- Implement the normalized WAV media endpoint with byte-range support and job-scoped paths. Cover unsupported/invalid range behavior.
- Implement transcript read/patch endpoints with an expected revision and atomic persistence of text/name edits, separate from model output.
- Build the player and segment list, timestamp seek, active-segment indication, text edit controls, and job-local speaker display names.
- Keep unknown speakers and overlap warnings visible. Do not provide timestamp editing, split/merge, or speaker reassignment in this iteration.
- Handle failed saves and stale revision conflicts without overwriting saved text. Provide explicit save state and prevent silent loss of unsaved edits on navigation.

## Acceptance criteria

- [ ] Each supported input plays through normalized audio and a timestamp seeks to the intended position.
- [ ] The active segment follows playback and null/overlap labels render clearly.
- [ ] Saved text edits and speaker names survive refresh and application restart.
- [ ] Speaker renames affect all relevant segments only within that job.
- [ ] A stale PATCH returns `409`; a failed save leaves the prior saved revision intact.
- [ ] Model text and inference provenance remain unchanged by user edits.

## Verification

Test edit revision conflicts, invalid segment/name updates, and media ranges at the API boundary. Run a browser smoke test for seeking, renaming, editing, failed save, and reload using a short redistributable fixture.

## Completion record

Not started.

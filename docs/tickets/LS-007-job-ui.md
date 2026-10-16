# LS-007 — Build import, readiness, and job history screens

Planning status at publication: open  
GitHub issue: [#7](https://github.com/MarcinGruchala/local-scribe/issues/7) — live status tracker  
Dependencies: LS-004; real model integration follows LS-005 and LS-006  
Requirements: FR-01, FR-02, FR-09, FR-10, FR-11; specification sections 3 and 4

## Outcome

The user can import a recording, inspect readiness, follow queued/running jobs, cancel or retry, and reopen saved history in the local browser.

## Work

- Build the English UI from the approved behavior/mocks: readiness, file picker/drop area, language, available profile, diarization toggle, and optional speaker count.
- Show actual upload progress, then stage/elapsed time. Avoid fabricated model percentages and ETA.
- Add newest-first paginated history and a reload-safe job detail route. Poll active jobs approximately once per second and stop in terminal states.
- Show structured errors with clear recovery actions. Distinguish successful, cancelled, failed, intentionally ASR-only, and completed-with-warnings jobs.
- Connect cancel/retry and prevent accidental duplicate submissions. Keep keyboard navigation, visible focus, labels, and status announcements usable.
- Display the gated-access setup requirement without requesting the Hugging Face token through the frontend.

## Acceptance criteria

- [ ] A user imports a supported file through both picker and drag/drop with valid options.
- [ ] Missing assets disable the affected workflow and explain the setup action.
- [ ] Queue/stage state survives refresh and matches backend status.
- [ ] Cancel/retry controls reflect valid states and backend race outcomes.
- [ ] A degraded result is clearly labelled and can open the preserved transcript.
- [ ] The UI requires no remote fonts/scripts/assets and works at desktop and narrow widths.

## Verification

Run a browser flow against deterministic adapters for pending, active, failed, cancelled, and degraded states. Check refresh, keyboard navigation, duplicate submit, and polling termination. Record separately when the same flow is exercised with real models.

## Completion record

Not started.

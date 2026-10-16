# LS-011 — Package explicit setup and offline startup

Planning status at publication: open  
GitHub issue: [#11](https://github.com/MarcinGruchala/local-scribe/issues/11) — live status tracker  
Dependencies: LS-001, LS-006, LS-007  
Requirements: FR-01, FR-13; specification sections 7 and 8

## Outcome

A documented one-time setup prepares local dependencies and pinned model assets. One normal start command then launches the complete application offline.

## Work

- Finish the setup, model-download, doctor, and start commands introduced by earlier tickets. Use exact locked dependencies and the LS-001 model manifest.
- Keep downloads explicit and separate from normal startup/inference. Verify hashes and completeness of transitive assets before marking readiness.
- Document user-owned Hugging Face access acceptance and narrowly scoped token use. Read credentials outside the browser and redact diagnostics.
- Set offline/telemetry flags before library imports, including Hugging Face and pyannote settings. Package all frontend assets locally.
- Diagnose missing native arm64 support, FFmpeg, permissions, disk capacity, model assets, and incompatible packages with actionable English messages.
- Start one backend/worker, open the local browser, and shut down children cleanly. Preserve data across upgrades/restarts.
- Document data/cache locations, deletion, limits, quality caveats, backup guidance, and recovery. Do not promise a native signed installer.

## Acceptance criteria

- [ ] A clean environment can follow the documented setup using lockfiles and explicit model downloads.
- [ ] `doctor` reports useful readiness without exposing tokens, private paths unnecessarily, or transcript content.
- [ ] Normal start and a complete cached-model job work with network disabled.
- [ ] Missing assets produce an actionable readiness failure instead of implicit downloads.
- [ ] Runtime needs no cloud account, LM Studio, Ollama, remote UI assets, or active download token.
- [ ] The documented single start command opens the app and preserves stored work on restart.

## Verification

Exercise setup in a clean isolated environment and normal use with network disabled. Check a missing/corrupt asset case and a token-redaction case. Capture sanitized instructions/versions; leave gated acceptance to the user.

## Completion record

Not started.

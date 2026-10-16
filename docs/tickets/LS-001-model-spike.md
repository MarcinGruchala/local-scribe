# LS-001 — Validate local model compatibility

Planning status at publication: open  
GitHub issue: [#1](https://github.com/MarcinGruchala/local-scribe/issues/1) — live status tracker  
Dependencies: none; user-managed Hugging Face access for the gated diarization model  
Requirements: FR-03, FR-04, FR-05, FR-13; specification sections 6, 8, and 9

## Outcome

A small reproducible command proves that the chosen local runtimes load the required model assets and return usable text, timestamps, and speaker turns on the target Mac. The result identifies the compatible dependency set before the application relies on it.

## Work

- Inspect native arm64 Python, available MLX GPU support, FFmpeg/FFprobe, available disk space, and the current dependency constraints.
- Resolve compatible versions for MLX Whisper, PyTorch, pyannote, and audio decoding. Record exact versions, local device selection, model repository IDs, immutable revisions, hashes, and license/provenance notices.
- Use `mlx-community/whisper-large-v3-turbo` as the starting ASR candidate and `pyannote/speaker-diarization-community-1` on CPU. Compare large-v3 when the quality candidate is available. Evaluate whisper.cpp only if the MLX route fails a recorded compatibility gate.
- Implement an explicit smoke/spike command that accepts a local sample path, emits normalized JSON, and records stage times without writing private text to console logs.
- Download assets only during an explicit setup step. Require the user to accept gated conditions; never automate acceptance or expose the token. Disable telemetry and prove loading from cached local paths with network disabled.
- Write a sanitized `docs/research/model-spike.md` report. Put raw results and private inputs outside Git.

## Acceptance criteria

- [ ] Native ASR inference succeeds on a real short file, with original-language text and finite timestamps.
- [ ] Local diarization succeeds and returns regular and exclusive turns; CPU selection is explicit.
- [ ] A second smoke run succeeds offline without model downloads or credentials in output.
- [ ] Model snapshots and dependency versions are reproducible; conversion provenance/license gaps are explicitly recorded.
- [ ] English, Polish, mixed-language, and speaker-quality checks have measured results or an explicit `pending references` status. Missing references do not masquerade as a passed quality gate.
- [ ] The report recommends an engine and profiles, lists unresolved evidence, and gives exact commands to reproduce the compatibility checks.

## Verification

Run the actual spike on this Mac. Record package/model versions, stage time, device, and memory observations. Separate cold setup from warm inference. Model access failure blocks diarization evidence; ASR-only evidence and unrelated scaffold work can continue. LS-012 owns final quality thresholds and sustained-performance acceptance.

## Completion record

Not started. No models were downloaded or measured during planning.

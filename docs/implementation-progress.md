# Implementation progress

Updated: 2026-10-16. Branch: `codex/mvp-implementation`. Goal is **not complete**.

## Delivered

- Runnable source application: `make setup`, `make build`, explicit `make models`, `make doctor`, `make start`.
- Loopback/security, streamed validated media import, persistent FIFO worker, cancellation/retry/recovery, timestamped ASR/speaker adapters, deterministic assignment, playback/editing, saved TXT/SRT/VTT/JSON, complete confirmed deletion.
- Model repository/revisions pinned per recording and guarded across retry/publication; full runtime provenance in JSON. Private roots and spike outputs cannot be placed inside the checkout.
- Focused commits preserve planning baseline and implementation increments. Historical planning-status fields remain unchanged; local Completion records updated.

## Verification

- Final fast suite: 130 tests pass without weights/credentials; Ruff, TypeScript and production frontend build pass. A separate clean core-only environment also runs the suite; complete model dependencies install offline from the same cached lock.
- Actual FFmpeg covers all seven supported formats, full decoded validation, duration/byte/storage failures, local-only formats/protocols and original-byte retention.
- Actual Chromium fixture checks cover picker/drop, measured upload, refresh/stages, keyboard, playback, editing, all exports, save failures, cancellation/retry/deletion, degraded/overlap states, dirty navigation and paginated history. Reports: validation/browser-smoke.md and validation/lifecycle.md.
- Actual native MLX Fast and Quality EN/PL inference succeeds under OS external-network denial. Polish diacritics and Auto detection verified. Real EN/PL ASR-only browser workflows plus actual cancellation/retry pass. Final PL browser repeat verifies model pinning/runtime provenance.
- Public short FLEURS references: both profiles PL 0/20 errors, EN 2/19. These tiny diagnostics do not satisfy representative quality gates.
- Constructed PL→EN challenge: both profiles omit EN, 19/39 deletions. Initial exact-zero silence hallucination documented; exact-zero guard now returns empty result without loading models. No thresholds changed or failures hidden.
- Model weights remain outside Git. Both ASR snapshots downloaded and hashed; Community-1 explicit download failed without authenticated access. Native CPU pyannote audio decoding works; actual model inference still unverified.

## Tracking

Acceptance evidence supports completion of LS-002, LS-003, LS-004, LS-005, LS-007, LS-008, LS-009, LS-010. GitHub issue synchronization is the final tracking step. LS-001, LS-006, LS-011, LS-012 remain incomplete. Sanitized release decision: **NOT READY**, in validation/mvp-release.md.

## Required human prerequisites

1. User personally accepts Community-1 conditions, if not already accepted, and authenticates an external Hugging Face credential store. No accessible HF token was present on the final check. Never paste credentials into chat/source/UI. Then run `make models PROFILE=diarization`; no conditions were accepted by the agent.
2. Provide approved 5–10 minute English and Polish two-speaker recordings with corrected text/turns, mixed-language/three-speaker/music/overlap challenges, representative 30 minute performance and approximately 60 minute stability inputs. See validation/reference-format.md. Public snippets cannot replace these gates.

## Resume

All model inference must remain sequential. No download or model job is running. An isolated real app is running at 127.0.0.1:8767 under scripts/offline.sb; validation jobs were deleted. Check existing process/ownership before starting another launcher. Complete actual Community-1 CPU/transitive-assets/offline checks after access, then reference scoring/performance/stability, update reports and incomplete issues, and only then consider Goal completion. Do not replace pending evidence with fixtures or repeated-snippet benchmarks.

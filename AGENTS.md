# AGENTS.md

LocalScribe is a personal, offline-first web application for transcribing imported English and Polish recordings on Apple Silicon. It uses MLX Whisper for ASR and CPU Community-1 for speaker diarization. The UI is English; transcripts retain the source language.

## Language

- Talk with Marcin in **Polish**.
- Write code, comments, documentation, commits, and GitHub issues/PRs in **English**.
- Explain non-obvious frontend choices; Marcin is more familiar with Python than JavaScript.

## Start here

- `README.md`: supported setup, start commands, storage, and known limitations.
- `docs/specs/mvp.md`: accepted scope, requirements FR-01 through FR-13, architecture, and quality gates. Some sections describe the original plan; consult current code and progress for implementation details.
- `docs/implementation-progress.md`: checkpoint, remaining evidence, and deferred work. Machine/process statements are historical evidence, not proof of what is running now.
- `docs/tickets/README.md` and `docs/tickets/LS-*.md`: planning baseline and links to live GitHub issues. Read the issue and its comments before work.
- `docs/development.md` and `docs/setup.md`: development and native Mac setup.
- `docs/validation/`: recorded checks and limitations. Do not convert earlier evidence into a claim that you reran it.
- Read relevant `CONTEXT.md` / `CONTEXT-MAP.md` and ADRs if present, as described in `docs/agents/domain.md`. Do not create empty domain documents just for setup.

## Code map

- `backend/src/localscribe/api.py`, `security.py`, `contracts.py`: HTTP boundary, local-request protection, and data contracts.
- `launcher.py`, `worker.py`, `jobs.py`, `storage.py`, `migration.py`: single-instance ownership, job lifecycle, SQLite, and recovery.
- `media.py`, `pipeline.py`, `alignment.py`, `engines/`: media conversion, sequential inference, and deterministic speaker assignment.
- `models.py`, `config.py`, `model-lock.json`: explicit model provisioning, configuration, and pinned model revisions.
- `exports.py`, `local_files.py`, `restore.py`: exports, readable per-job copies, and explicit restoration.
- `frontend/src/`: React/TypeScript UI, API client, transcript editor, and history/listening views.
- `tests/test_*.py`: model-free backend tests. `tests/browser-*.cjs` and `tests/browser_server.py`: browser checks and their fixture server.
- `scripts/`: explicit benchmark, reference-scoring, and validation tools; inspect their requirements before running them.

## Commands and checks

Target runtime: native arm64 macOS, Python **3.11**, Node.js **22.12+**, `uv`, FFmpeg/FFprobe. Do not install the MLX model extra on Linux just to edit docs or run core tests.

From the repository root:

```sh
# Core development only, without model adapters:
uv sync --frozen
(cd frontend && npm ci)
make check
make build
```

`make check` runs pytest, Ruff (`backend tests`), and frontend TypeScript checks. `make build` also builds production assets. For targeted backend work use `uv run --frozen --no-sync pytest tests/test_<area>.py`, then run the full relevant checks before delivery.

On the target Mac, `make setup` also installs model dependencies; `make models PROFILE=...` explicitly downloads assets; `make doctor` checks readiness; `make start` serves the built UI and opens the browser. Follow `docs/setup.md` for model access and offline validation. Do not run heavyweight downloads/inference or start a competing app for an unrelated change. Check active jobs and port ownership before a requested runtime test.

For code changes, add a failing regression/behavior test before the fix where practical, run it to green, and review the diff. Run the relevant browser checks for UI changes; inspect each script's server/fixture prerequisites rather than treating them as one generic test command. For documentation/agent-setup-only changes, validate paths, metadata, symlinks, source parity, and `git diff --check`; report that application tests were not run.

## Invariants

- Keep inference local and sequential. One supervised worker claims one persistent FIFO job at a time; heavy work stays outside the HTTP event loop.
- Preserve attempt ownership, cancel-versus-publish safety, restart recovery, and stale-edit conflict detection. Do not hold SQLite transactions through inference.
- Bind to loopback only. Preserve Host/Origin validation and the per-session mutation token; do not add broad CORS or LAN exposure.
- Never upload private audio, transcripts, embeddings, or logs containing them to external services. No runtime downloads, analytics, remote assets, or cloud inference.
- `output/` contains private history, database, recordings, and exports. Never force-add it, delete it as cleanup, or reset the database to make a test pass. Models stay outside the checkout. Use isolated temporary stores for tests.
- Preserve originals until explicit job deletion; shared model assets and the legacy migration backup are not job-owned files.
- Speaker names are local to a recording, not cross-recording voice identities. Failed diarization keeps successful ASR text with an explicit warning; missing attribution stays unknown.
- Model access authorization and gated license acceptance belong to Marcin. Never put credentials in source, command arguments, browser state, issue comments, or reports.
- Fixtures prove software behavior, not recognition accuracy. Real ASR/diarization, network-disabled operation, WER, speaker accuracy, and performance need separate measured evidence on supported hardware.
- Do not declare the MVP release-ready, weaken quality thresholds, or reopen deferred corpus/model searches without a new decision. Consult the current progress and release evidence first.

## Workflow and handoff

- Work in an isolated worktree on the requested branch; never commit straight to `main`. Do not overwrite unrelated or uncommitted work.
- Use small, descriptive English commits; reference an issue when one exists. Push only within the requested scope; no force-push, merge, issue closure, release, or deployment unless authorized.
- GitHub Issues on `MarcinGruchala/local-scribe` track live work; local tickets preserve the baseline. See `docs/agents/issue-tracker.md`. Never redirect a copied skill to the source project's tracker.
- Keep documentation proportional. Record meaningful scope/architecture departures rather than silently changing the accepted specification.
- Before handoff, record workspace, branch/commit, dirty state, commands actually run and their results, blockers, and next step. Use `docs/implementation-progress.md` for implementation checkpoints; small documentation-only changes can use the commit and final report.
- Verify remote writes by reading the exact branch/commit/issue back. Do not call CI green without exact-head checks.

## Agent skills

- The shared, versioned skills live in `.agents/skills/<name>/SKILL.md` (Codex).
- `.claude/skills` points to `../.agents/skills` (Claude Code). Edit the canonical files, never a second copy.
- `CLAUDE.md` imports this file so both agents share the project rules.
- See `docs/agents/skills.md` for the catalog, source revision, discovery checks, and compatibility notes. Read the relevant skill before use. Skills do not grant permissions or override the task's scope, privacy rules, or harness restrictions.

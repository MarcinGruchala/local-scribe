# LS-002 — Create the local application scaffold

Planning status at publication: open  
GitHub issue: [#2](https://github.com/MarcinGruchala/local-scribe/issues/2) — live status tracker  
Dependencies: none; incorporate LS-001's version findings before final model locks  
Requirements: FR-01, FR-13; specification sections 7 and 8

## Outcome

One command starts a loopback-only backend that serves the built frontend and exposes local health diagnostics. The repository has a reproducible development setup.

## Work

- Create the Python package, FastAPI entrypoint, React/TypeScript/Vite frontend, and a minimal launcher in the proposed structure.
- Add dependency lockfiles and scripts for development, frontend build, and startup. Treat Python 3.11 as the initial baseline; record any compatibility-driven adjustment.
- Establish the configurable data root, SQLite migrations, WAL/foreign-key settings, and a single-instance lock. Do not create model files or private recordings inside the repository.
- Serve frontend assets from the backend origin. Bind to `127.0.0.1`, validate Host/Origin, restrict CORS, and protect mutation routes with a local session token.
- Define typed job/options/transcript contracts and structured English errors. Separate model adapters so ordinary startup and tests do not load weights.
- Add appropriate ignores and a concise development guide. The existing Polish README can retain its convention and link to English technical documentation.

## Acceptance criteria

- [ ] A clean local development environment can build the frontend and start the backend using documented commands.
- [ ] The root page and `GET /api/health` work from the same local origin.
- [ ] Runtime binding is loopback-only; unexpected hosts/origins and missing mutation tokens are rejected.
- [ ] Startup initializes and migrates the data store; a second launcher cannot own the same store.
- [ ] Startup without model files reports missing readiness rather than downloading assets or failing module import.
- [ ] Fast checks and the frontend build run without model credentials or downloads.

## Verification

Use a lightweight API smoke test for health, origin/session protection, and migration/lock behavior. Build the frontend. Use temporary data directories for tests; leave the user's normal data root untouched.

## Completion record

2026-10-16: Completed. Locked Python/React/Vite application builds and serves same-origin UI/API; loopback host/origin/session protection, migrations, duplicate-owner lock and missing-model startup are tested. Separate clean core/model environments installed offline from cached lock. See tests/test_scaffold.py and docs/validation/browser-smoke.md.

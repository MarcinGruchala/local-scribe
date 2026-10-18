# Local development

LocalScribe targets native arm64 macOS and Python 3.11. It serves its built React/TypeScript frontend and FastAPI API from one loopback origin. Model adapters remain outside ordinary startup and fast checks.

Install `uv`, Node.js 22 or newer, and FFmpeg/FFprobe. From the repository root:

```sh
make setup
make build
make check
make start
```

The launcher binds only `127.0.0.1:8765` and opens that URL in the default browser. Use `uv run localscribe --no-browser` to suppress browser opening. A second launcher using the same data root exits with a clear error. Stop the application with Ctrl+C.

The default private store is the project’s Git-ignored `output/` directory. Each completed job owns four generated transcript files, refreshed after saved edits and repaired at startup. Existing history from the previous home-directory default is copied on first default launch; the original store is retained as a backup. Override it with `LOCALSCRIBE_DATA_ROOT` or `--data-root`. Set `LOCALSCRIBE_MODEL_ROOT` or `--model-root` for the separate local model cache. Set `LOCALSCRIBE_PORT` or `--port` to select another local port. Keep recordings, transcripts, credentials, model weights, and SQLite files outside Git.

`make setup` installs pinned project dependencies; it does not accept gated conditions or download model weights. Explicit model provisioning and validation are documented separately. Startup reports missing models instead of downloading them. `make test` and the frontend checks require no model access or credentials.

The backend initializes SQLite in WAL mode with foreign keys enabled and records explicit migrations. The launcher's file lock has process lifetime, so it is released after normal exit or a crash. Development HTTP requests must use the configured `localhost` or `127.0.0.1` origin. Obtain a session token with `GET /api/session` and send it as `X-LocalScribe-Token` on mutations. No broad CORS rule is enabled.

After editing frontend files, run `make build` and reload the application. `npm run dev` in `frontend/` can inspect isolated frontend work, but the supported full workflow uses the backend's same-origin built assets.

## Grouping/history browser regression

`tests/run_grouping_browser.py` starts a fixture-only backend with 400 synthetic source segments, runs actual Chromium, stops/restarts the HTTP process against the same isolated store, then verifies persisted Undo/Redo and explicit recording deletion. No inference worker, private recording, model weights or downloads are involved. It refuses an occupied fixture port and leaves its synthetic artifacts for inspection.

The browser scripts use Playwright, supplied separately from production dependencies (as with the other `tests/browser-*.cjs` checks). For an isolated test-tool installation:

```sh
# Core only on Linux; do not install the MLX extra here.
uv sync --frozen
(cd frontend && npm ci)
make build
: "${TMPDIR:?Set TMPDIR to your scratch directory}"
npm install --prefix "$TMPDIR/localscribe-browser-tools" playwright
"$TMPDIR/localscribe-browser-tools/node_modules/.bin/playwright" install chromium
NODE_PATH="$TMPDIR/localscribe-browser-tools/node_modules" \
  uv run --frozen --no-sync python tests/run_grouping_browser.py
```

Use an already installed Playwright/Chromium instead when available; `BROWSER_EXECUTABLE` selects an explicit Chromium binary, and `NODE_PATH` selects the test-tool package directory. Native browser libraries must already be installed. `LOCALSCRIBE_GROUPING_TEST_PORT` overrides the fixture port (8770); `LOCALSCRIBE_GROUPING_TEST_ROOT` selects a **fresh, dedicated synthetic test directory** outside the checkout. Do not point it at private app output. The default makes a new directory beneath `TMPDIR` on each run. If a tool host injects another interpreter's site-packages through `PYTHONPATH`/`PYTHONHOME`, unset those for the Python 3.11 project commands.

The optional `UI_CONTRACT_FIXTURE=1` mode runs only early UI contract tests with explicitly stubbed HTTP responses; it is not backend or restart acceptance. Normal delivery uses the default real-backend mode. Results and screenshots stay in the printed test directory, not Git. Fixture/browser success establishes software behavior, not ASR quality, Apple Silicon performance or real-model/offline validation.

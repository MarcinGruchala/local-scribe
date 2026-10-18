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

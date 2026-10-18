# Setup and offline startup

LocalScribe runs on native arm64 macOS with Python 3.11. It imports existing recordings and runs sequential local transcription and speaker diarization. No LM Studio, Ollama, remote inference service or cloud transcription account is required. Hugging Face account authorization is a one-time prerequisite for downloading the gated speaker model.

## Install the locked application

Install native arm64 Python 3.11, `uv`, Node.js 22.12 or newer with npm, and FFmpeg/FFprobe through your preferred package manager. The pinned Vite dependency requires Node `^20.19.0 || >=22.12.0`; this guide uses the newer supported branch. Use an arm64 terminal and tools rather than a Rosetta environment.

Allow approximately 15 GB of free space for dependencies, model profiles and cache duplication. This is a planning allowance rather than a measured installation size; budget recordings and backups separately. From the repository root:

```sh
make setup
make build
```

`make setup` installs the Python packages from `uv.lock` and frontend dependencies from `frontend/package-lock.json`. It includes the model runtime dependencies, but does not accept model conditions or download model weights. `make build` bundles all frontend assets locally. Initial dependency installation and explicit model provisioning require network access; ordinary startup does not install or synchronize packages.

## Authorize the speaker-model download personally

Open the [Community-1 model page](https://huggingface.co/pyannote/speaker-diarization-community-1), sign into the Hugging Face account you intend to use, and review and accept its conditions yourself. LocalScribe cannot accept those conditions on your behalf.

The installed Hugging Face CLI supports browser/device authorization without manually creating an access token:

```sh
.venv/bin/hf auth login --no-add-to-git-credential
```

Choose browser login if the interactive CLI asks how to authenticate, then personally complete the browser authorization it presents. The CLI stores its credentials outside this repository. Git credential integration is not needed to download snapshots. If this account is already authenticated locally, another login is unnecessary.

An existing narrowly scoped download credential supplied through the external Hugging Face credential store or `HF_TOKEN` is an alternative, not a requirement. Never paste a credential into LocalScribe, a command argument, an issue, a transcript, or a source file. Do not share authentication output or private credential files. If you used a temporary `HF_TOKEN` environment variable, unset it after provisioning. A successful login does not itself grant gated-model access: the same account must have personally accepted the model conditions.

## Provision immutable snapshots explicitly

```sh
make models PROFILE=fast
make models PROFILE=diarization
make doctor
```

Each download uses the immutable revision in `model-lock.json`; weights remain outside Git. The model cache contains per-file SHA-256 manifests, and readiness verifies cached assets rather than silently downloading replacements. The optional Quality profile is provisioned with `make models PROFILE=quality` and remains disabled until a successful explicit compatibility spike matches its revision. Compatibility does not establish representative recognition quality.

The default model cache is `~/Library/Caches/LocalScribe/models/`. Set `LOCALSCRIBE_MODEL_ROOT` before provisioning, doctor and startup if you need another cache. Keep it outside the checkout. Never remove an asset simply to make a readiness warning disappear: rerun its explicit provisioning command to repair the cached snapshot, then run doctor.

`make doctor` checks native architecture, required package versions, FFmpeg/FFprobe, local storage writability/capacity and model integrity. It does not print credential values or transcript content. A nonzero exit means a required prerequisite is missing. To intentionally use transcription without speaker turns while the speaker model is unavailable, use:

```sh
uv run --frozen --no-sync python -m localscribe.models doctor --asr-only
```

Then explicitly turn off speaker turns in the import form. This mode is not evidence that the full transcription-plus-diarization release gate passed.

## Start and retain work

```sh
make start
```

The launcher binds only `127.0.0.1`, starts one supervised worker, opens the built local frontend, and holds a single-owner lock for its data store. The default port is 8765. If it is occupied, use a free port, for example `LOCALSCRIBE_PORT=8768 make start`. `make dev` starts without opening a browser. Stop with Ctrl-C so the worker can stop its current child cleanly.

The default data store is the project’s ignored `output/` directory; override it with `LOCALSCRIBE_DATA_ROOT` (an ignored `output/` subdirectory or a location outside the checkout). Originals, normalized audio, attempts, transcripts and edits persist there until explicit job deletion. History lists saved recordings. Each completed job has readable `transcript.txt`, `.srt`, `.vtt` and `.json` files in `output/jobs/<job-id>/`; explicit saved edits refresh all four. The UI displays copyable folder paths and offers retry if file generation fails. Missing, modified or outdated copies are repaired at startup from the canonical transcript; edit in the application instead of modifying these generated copies.

The first default startup copies a previous `~/Library/Application Support/LocalScribe/` store if `output/` has no database. It requires the previous instance to be stopped, uses a consistent SQLite backup, resumes interrupted installation, and preserves the old directory as a backup. Validation artifacts remain in the old directory. Job deletion affects the new active store only; old backups retain their own copies until you remove them explicitly. Shared model snapshots are separate and survive job deletion. Back up the entire data directory while the application is stopped. Restart preserves completed and queued work; interrupted processing becomes failed with an explicit retry action rather than silently resuming a checkpoint.

The local browser receives only a per-session request token generated by LocalScribe. It never receives a Hugging Face credential. The worker removes Hugging Face token environment variables, loads complete local snapshots with offline flags, and disables telemetry before inference imports. These protections do not replace an operating-system network-disabled validation run.

## Verify the complete cached workflow offline

After explicit provisioning and doctor succeed, stop any other model job and launch an isolated validation store using the checked-in macOS network policy. Substitute private absolute directories outside the checkout:

```sh
env -u HF_TOKEN -u HUGGING_FACE_HUB_TOKEN -u HUGGINGFACE_TOKEN \
  /usr/bin/sandbox-exec -f scripts/offline.sb \
  .venv/bin/localscribe --no-browser \
  --data-root /absolute/private-offline-validation \
  --model-root /absolute/local-model-cache --port 8767
```

Open `http://127.0.0.1:8767` in a local browser. This policy denies external networking for the application and its descendants while allowing loopback. It is a macOS validation mechanism, not a native installer. If the policy cannot run on another system, record the limitation and use an equivalent verified network-isolation mechanism; offline environment variables alone do not prove isolation.

With speaker turns enabled, import an approved English sample, wait for a completed result without a diarization-failure warning, and inspect real speaker labels/turns. Verify playback, timestamp seeking, saved text and speaker-name edits, all four exports and explicit deletion. Repeat for Polish. The browser verification scripts and sanitized evidence are described in [browser validation](validation/browser-smoke.md).

Successful snapshot download or a green health panel does not prove every transitive runtime asset is cached. A complete real transcription-plus-diarization job under network denial establishes the functional offline gate. Corrected two-speaker references, accuracy scoring, challenge recordings, representative performance and sustained stability remain separate requirements in the [accepted specification](specs/mvp.md) and [release report](validation/mvp-release.md).

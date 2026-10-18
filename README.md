# LocalScribe

A local web application for transcribing imported English and Polish audio/video files on Apple Silicon. Transcription uses MLX Whisper; speaker diarization uses Community-1 on the CPU. Inference runs sequentially. Recordings and results remain on your Mac.

**Release status:** MVP accepted for personal use by Marcin on 2026-10-18 after his practical tests and improvements. Functional workflows and real cached offline ASR plus diarization have recorded evidence. Known recognition failures and unfinished quantitative benchmarks are accepted limitations of this iteration, not claimed passes. See [closeout decision and release evidence](docs/validation/mvp-release.md) and [progress](docs/implementation-progress.md).

## AI development setup

[AGENTS.md](AGENTS.md) holds the shared project instructions. Claude Code imports it through `CLAUDE.md`. Project skills live in `.agents/skills/`; `.claude/skills` points to that same directory. No global skill installation is required. See the [skill catalog and compatibility notes](docs/agents/skills.md).

## One-time setup

Requirements: native arm64 macOS, Python 3.11, `uv`, Node.js 22.12 or newer with npm, FFmpeg and FFprobe, and enough storage for models and recordings (allow approximately 15 GB for setup). Install native prerequisites through your preferred package manager.

```sh
make setup
make build
make models PROFILE=fast
# Personally accept the Community-1 access conditions on Hugging Face first.
.venv/bin/hf auth login --no-add-to-git-credential
make models PROFILE=diarization
make doctor
```

Review the [Community-1 conditions](https://huggingface.co/pyannote/speaker-diarization-community-1) yourself. LocalScribe never accepts them for you. The installed Hugging Face CLI supports browser/device login: run `.venv/bin/hf auth login --no-add-to-git-credential` in your terminal, choose browser login if prompted, and personally authorize it in your browser. This stores the credential outside the repository; you do not need to create a manual access token. An existing narrowly scoped download token in an external credential store or `HF_TOKEN` remains an alternative. Credentials never belong in the LocalScribe UI, Git, issue comments, or command arguments. If you used `HF_TOKEN`, unset it after setup. Downloads happen only through `make models`; startup never downloads weights. See the [complete setup and offline verification guide](docs/setup.md).

`model-lock.json` records exact model revisions. Local manifests record SHA-256 hashes for each asset. The Fast profile is the accepted personal-use MVP default, with the recorded reference-quality limitations; the Quality profile requires an explicit compatibility spike before it is enabled; representative quality remains unverified for both profiles. See [model spike](docs/research/model-spike.md).

## Start

```sh
make start
```

One launcher owns the store, starts one supervised worker, serves the built frontend on `http://127.0.0.1:8765`, and opens your browser. Stop it with Ctrl-C. If the default port is occupied, start with `LOCALSCRIBE_PORT=8768 make start` (or another free port). A second launcher cannot own the same store. `make dev` starts without opening a browser. Configuration:

- `LOCALSCRIBE_DATA_ROOT`: default `output/` in this project (ignored by Git).
- `LOCALSCRIBE_MODEL_ROOT`: default `~/Library/Caches/LocalScribe/models/`.
- `LOCALSCRIBE_PORT`: default `8765`; binding remains loopback-only.

Open **Transcript history** to revisit saved transcripts. Search completed recordings by file name or filter by the transcription language setting, including older recordings beyond the first page. Choose **Listen & review** on a recording to open its saved transcript and audio in the recording studio. The recording URL survives reloads; use **Transcript history** to return to the archive. Each completed recording automatically has `transcript.txt`, `transcript.srt`, `transcript.vtt` and `transcript.json` under `output/jobs/<job-id>/`; saved text and speaker-name edits update these copies. The UI shows a copyable folder path and reports copy failures separately from saved edits. Retry file generation or restart to repair missing/modified copies. Edit through LocalScribe: manually changed export copies are regenerated from the saved transcript.

`output/` contains private media, the database and exports; never force-add it to Git. Custom data roots can use ignored `output/` or a directory outside the checkout; model roots must stay outside the checkout. Back up the entire data directory while the app is stopped. On first default startup, an existing previous default store in `~/Library/Application Support/LocalScribe/` is copied into `output/` if no destination database exists. Stop the old instance first. The old store is retained as a backup, including its media; deletion in the new store does not delete that backup. Validation artifacts remain in their previous directory. Shared model assets survive job deletion. Upgrades preserve the SQLite store; do not remove it to upgrade.

## Use and recovery

Import one WAV, MP3, M4A, FLAC, OGG, MP4, or MOV at a time (subject to local FFmpeg decoding), up to 2 GiB and 2 hours. Select automatic, English, or Polish transcription; diarization is enabled by default with optional exact speaker count 1–10. Additional jobs enter a persistent FIFO queue.

Open a completed recording to play the normalized WAV, seek by timestamp, edit segment text, and rename speakers within that recording. Explicitly save before exporting TXT, SRT, VTT, or JSON; exports use the last saved revision. Concurrent stale edits are rejected and your draft remains visible. Names do not identify voices across recordings. Overlapping speech and unknown labels are explicit.

A completed recording opens in a dark recording studio: the transcript in the centre (speaker, start time, editable text and end time per segment), a details panel on the right, and a player dock with a speaker timeline at the bottom. Scrub the audio position, skip back or forward five seconds, and adjust playback speed from 0.5× to 2×. The transcript highlights the current segment and optionally scrolls with the audio; turn off **Follow audio** to browse freely. Click a timestamp, or a block on the speaker timeline, to seek; zoom the timeline for long recordings. Use **Find in transcript** to highlight matching segments. Rename speakers in the details panel, where each speaker also shows turns, talk time and a preview button. Keyboard shortcuts outside text fields: Space plays or pauses, ←/→ skip five seconds; ⌘S (Ctrl+S) saves. Edit words and speaker names, then **Save changes** to update the transcript and local exports.

Cancellation stops the active child and prevents late publication. Retry failed/cancelled jobs to start a new attempt with the same settings. Restart preserves completed and queued jobs; interrupted work fails with a retry action. There is no checkpoint resume. If speaker processing fails after successful ASR, text is retained with a warning and unavailable speaker labels.

Original files stay until you confirm deletion in the UI. Cancel queued/active work and wait for it to stop before deleting. Deletion removes all owned media/results/edits/attempts. A filesystem failure leaves a visible retryable deletion record; restart reconciles it. Repeated deletion after success returns 404.

Whisper may hallucinate or misrecognize names, silence, music, language switches, and overlapping speech. Review important transcripts. Reference quality measurements have not yet established the accepted thresholds.

## Checks and evidence

```sh
make check
make build
# Explicit real inference; output and normalized media must stay outside Git.
uv run --frozen --no-sync localscribe-spike /absolute/sample.wav \
  --output /absolute/private-results/spike.json --language pl --diarization
```

Fast tests require no models, credentials, or network. See [development](docs/development.md), [accepted specification](docs/specs/mvp.md), and [backlog](docs/tickets/README.md). Real reference scoring and network-disabled release gates are documented separately; offline environment flags alone do not prove them passed.

Recognition can generate spurious text on instrumental music. If enabled diarization detects no speaker turns while text is present, LocalScribe preserves the text and displays a review warning. See the measured limitations in [release evidence](docs/validation/mvp-release.md) and [practical challenges](docs/validation/challenges.md).

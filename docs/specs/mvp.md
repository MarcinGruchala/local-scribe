# LocalScribe — first iteration specification

Status: accepted planning baseline; user confirmed the two plan decisions on 2026-10-16. Model compatibility and quality remain subject to the spike and release evidence.  
Date: 2026-10-16.  
Owner: Marcin.  
Target: personal use on a MacBook Pro with Apple M5 Pro and 64 GB unified memory, as shown in the supplied screenshot. No hardware benchmark was run.

## 1. Outcome

Marcin can import a local recording, obtain a transcript in English or Polish, see when each person spoke, correct the result, and export it. After initial installation and model downloads, the application processes recordings without an internet connection. Audio, transcripts, and speaker embeddings stay on the Mac.

The first iteration is file-based and asynchronous. It provides a local web interface and a local backend. It does not require a cloud account for transcription. One-time access to the proposed diarization model does require a Hugging Face account and acceptance of its access conditions.

## 2. Accepted decisions and technical defaults

Marcin accepted the plan without changes on 2026-10-16. The two explicit decisions are recorded below. Technical defaults remain subject to the documented model validation gates.

| Decision | Proposed default | Reason |
| --- | --- | --- |
| Input workflow | Import existing audio and video files (confirmed) | User selected this workflow. |
| ASR engine | `mlx-whisper` on Apple Silicon | Uses an Apple-focused runtime; avoids a CUDA dependency. |
| ASR model | `mlx-community/whisper-large-v3-turbo` | Starting profile for bilingual transcription; must pass the local quality gate. |
| Quality candidate | `mlx-community/whisper-large-v3-mlx` | Compare with turbo before locking the model profile. |
| Speaker diarization | `pyannote/speaker-diarization-community-1`, local CPU baseline | A separate local pipeline produces speaker turns. MPS is an experiment, not an MVP promise. |
| LM Studio / Ollama | No runtime dependency (separate engine accepted) | User is open to a separate engine. Current LM Studio documentation does not establish a supported ASR endpoint; see the research note. |
| Interface | English UI for the first iteration | One small interface; transcript text retains the source language. |
| Storage | Local SQLite and files; retain until explicit deletion | A reload or application restart must not lose completed work. |
| Diarization failure (accepted, plan 2.2) | Keep the text with a warning | Show a degraded result with unavailable speaker labels; do not discard successful ASR. |
| Original media retention (accepted, plan 4.1) | Keep originals until job deletion | Conversion never removes the imported source; explicit deletion removes source and derived data. |
| Delivery | Source repository, setup instructions, one start command | A signed native installer is outside the first iteration. |

Model selection is provisional until the hardware and quality spike passes. The application must record exact model revisions and dependency versions. See [model research](../research/local-asr-models.md) and the [interactive plan](../plans/mvp.packed.html).

Accepted response: `speaker_failure=keep-text`, `source_retention=keep`. No schema edits, struck claims, or additional comments accompanied the response.

## 3. Scope and limits

### Included

- One local user and one active job; additional jobs enter a persistent FIFO queue.
- Import WAV, MP3, M4A, FLAC, OGG, MP4, and MOV when the installed FFmpeg build can decode their audio.
- Select `Auto`, `English`, or `Polish`; select `Fast` or `Quality` only if both profiles pass the spike.
- Diarization enabled by default; allow transcription without it when the user selects that mode.
- Optional exact speaker count, from 1 through 10; otherwise automatic count. Counts are hints to the model, not guarantees.
- Local job history, stage status, cancel, retry, and restart recovery.
- Transcript segments with start/end times, speaker labels, playback, text edits, and speaker display-name edits.
- TXT, SRT, VTT, and versioned JSON exports.
- Readiness diagnostics for FFmpeg, models, permissions, and available storage.

### Excluded

Live transcription, microphone capture, system audio capture, meeting bot integrations, remote URLs, cloud inference, summaries, translation, speaker identification across recordings, collaborative use, and a native installer. Multi-channel recordings are mixed to mono for inference. Channel separation is a later feature. Speaker detection does not identify real people.

### Proposed operating envelope

Import one file per action, at most 2 GiB and 2 hours per file. Stream uploads and decoded audio to disk. Never read the complete upload into backend memory. Validate both byte count and decoded duration. Reject over-limit and undecodable files with an actionable error, and remove incomplete imports. These are product limits, not claims about model capacity.

## 4. User workflow

1. Start LocalScribe. The browser opens the local application. A readiness panel identifies missing dependencies or models before a job starts.
2. Drop a recording or select it from the file picker. Set language, quality profile, diarization, and optional speaker count. The file stays in the local application store.
3. Submit the recording. The application validates it, places the job in the queue, and shows its current stage. The user can leave the page and return to the same job.
4. During inference, show elapsed time and the stage name. Show percentages only where the engine supplies measurable progress. Do not invent an ETA.
5. Open the result. Each segment shows a timestamp, a speaker label, and text. Selecting its timestamp seeks the audio player. The selected segment follows playback.
6. Correct segment text and rename speakers. Save with explicit success/failure feedback. Changes survive a reload and appear in exports.
7. Export or delete the job. Deletion requires an in-app confirmation because it removes locally stored work.

The first version does not edit timestamps, split/merge segments, or manually reassign speaker IDs. A user can rename `Speaker 1` to `Marcin`; that name applies only within this recording.

## 5. Functional requirements

| ID | Requirement and acceptance evidence |
| --- | --- |
| FR-01 | Only the loopback interface serves the application. The normal workflow works in a current local browser without a hosted service. |
| FR-02 | Supported valid media imports successfully; corrupt, empty, over-limit, and audio-free files fail cleanly without residual temporary files. |
| FR-03 | An English sample produces English text; a Polish sample produces Polish text with diacritics. Forced language never requests translation. |
| FR-04 | Diarization produces stable anonymous speaker IDs within a job. Speaker count can be automatic or a valid exact count. |
| FR-05 | Every transcript segment has finite start/end seconds, `0 <= start < end <= duration`, and text. Unknown speaker attribution is explicit. |
| FR-06 | Completed segments can be read while playing the normalized recording. Seeking works in supported browsers for each input format. |
| FR-07 | Text and speaker-name edits persist and update every export. An edit failure preserves the previous saved result. |
| FR-08 | TXT is readable; SRT/VTT have valid timestamps and speaker prefixes; JSON preserves IDs, times, edits, provenance, warnings, and speaker turns. |
| FR-09 | A refresh preserves job status. A restart preserves completed results and queued jobs; interrupted jobs become failed with a retry action. |
| FR-10 | Cancel stops the active child process and prevents late completion from publishing a result. A retry creates a new attempt with immutable model settings. |
| FR-11 | If requested diarization fails after ASR, show `Completed with warnings`, preserve the text, and state that speaker labels are unavailable. Never report a successful diarization result. |
| FR-12 | Delete removes job metadata, source media, playback media, derived audio, transcripts, and attempt files. Shared model downloads remain. |
| FR-13 | After setup, a network-disabled end-to-end run succeeds. No runtime downloads, telemetry, remote assets, or remote inference are required. |

## 6. Inference pipeline

```text
Local upload
  -> byte/type checks and FFprobe metadata
  -> FFmpeg: 16 kHz mono PCM WAV for inference and browser playback
  -> MLX Whisper: original-language text and word timestamps
  -> pyannote Community-1: speaker turns on the same normalized audio
  -> deterministic word-to-speaker assignment and segment assembly
  -> validated, atomically published transcript and provenance
```

Run the model stages sequentially. Release ASR model memory before diarization when possible. Do not run independent GPU jobs concurrently. FFmpeg and model inference run in a child process, outside the HTTP event loop. Never use user input as a shell command.

### Language and timestamps

Use Whisper's transcription task, not its translation task. `Auto` uses model language detection; explicit `en` and `pl` override it. Mixed-language recordings are a benchmark case: detection and a forced language do not guarantee correct recognition of switches. Word timestamps are an MVP alignment method; do not add WhisperX and separate language aligners by default.

### Speaker assignment

Use Community-1 exclusive turns for a single label per word, while retaining regular turns to detect overlap. Assign each word to the turn with the greatest positive time overlap. Break ties by earliest turn start, then stable speaker ID. A word with no positive overlap gets a null speaker ID; do not infer identity from text. If word timestamps are missing, use segment overlap and attach an alignment warning.

Create display segments at speaker changes and model segment boundaries. Do not split word text by character offsets. Keep stable anonymous speaker IDs in order of first occurrence; user names are a separate mapping. Mark a display segment as overlapping speech when any of its words intersects regular turns from two or more speakers. Save both forms of turns in JSON. The first version does not claim separate reliable transcripts for simultaneous speech.

Silent or non-speech input can produce an empty transcript with a notice. Include silence and background music in the quality gate to detect hallucinated text. Model confidence values, if exposed, are diagnostic signals rather than calibrated certainty.

## 7. Architecture

Proposed stack: Python 3.11 managed with `uv`; FastAPI; SQLite; FFmpeg/FFprobe; MLX Whisper; PyTorch/pyannote; React with TypeScript and Vite. Confirm a mutually compatible version set in the spike, then commit exact Python and frontend lockfiles. Do not treat today's latest releases as a tested combination.

The local launcher runs one FastAPI server and one supervised worker. The server serves a prebuilt frontend from the same origin and handles only file I/O, validation, metadata, edits, and polling. The worker claims one queued SQLite job at a time and starts a fresh inference child for its attempt. This permits cancellation and limits persistent model-memory growth. No Redis, Celery, Docker, or separate database server is needed.

The worker owns job transitions. A transaction claims a queued job, increments its attempt number, and records its owner. Only the current attempt can publish results. Atomic publication requires the job to remain active and uncancelled. Cancel and publish compete in one transaction: if cancellation wins, late output is discarded; if completion wins, cancel returns the terminal status. Use a process-group termination policy with a short grace period and forced stop when necessary. The launcher holds a single-instance lock for the data store. On restart it stops any surviving child identified by that launcher before it marks active attempts interrupted.

Use SQLite WAL mode, foreign keys, explicit migrations, and a short transaction for every transition. Never hold a database transaction through inference. Stage result files in an attempt directory; atomically rename a validated result before committing its published reference. On restart reconcile orphaned files and references. Poll active status approximately every second; stop polling in terminal states.

### Job lifecycle

```text
queued -> preparing -> transcribing -> diarizing -> assembling -> completed
                                  \--------------> assembling
any active state -> cancelling -> cancelled
any active state -> failed
failed / cancelled -> queued (new attempt, explicit retry)
```

`diarizing` is skipped when disabled. Its failure can lead to `assembling` with an explicit warning and null speaker labels. Upload progress is a browser state; a job enters `queued` only after a complete validated import. At startup, jobs left active by an earlier session become `failed` with code `interrupted`; queued work remains queued. Do not promise checkpoint resume. Successful retry replaces the published result only after full validation. Warn that retry discards text/name edits when replacing an existing result.

### Proposed module boundaries

```text
backend/src/localscribe/
  api.py                 # HTTP routes and request validation
  launcher.py            # server, worker, lock, shutdown
  jobs.py                # transitions, attempts, cancellation
  storage.py             # SQLite and file ownership
  media.py               # FFprobe/FFmpeg wrapper
  pipeline.py            # stage orchestration
  engines/asr_mlx.py     # ASR adapter
  engines/diarization.py # pyannote adapter
  alignment.py           # deterministic speaker assignment
  exports.py             # TXT, SRT, VTT, JSON
  models.py              # local asset readiness and manifests
frontend/src/
  App.tsx
  api.ts
  components/            # import, history, readiness, transcript
tests/                   # contract, lifecycle, alignment, exports
scripts/                 # setup, model setup, doctor, start, benchmark
```

These are proposed paths, not files already present. Keep adapters small and replaceable. A fallback engine is a contingency decision after a failed spike, not a second mandatory implementation.

### API contract sketch

| Endpoint | Contract |
| --- | --- |
| `GET /api/health` | Readiness, missing assets, engine/device versions, active job; no tokens or transcript content. |
| `POST /api/jobs` | Multipart file plus validated options; return `201` with job ID after durable import. |
| `GET /api/jobs` | Paginated history, newest first. |
| `GET /api/jobs/{id}` | Status, stage, attempt, elapsed time, options, warnings, structured failure. |
| `POST /api/jobs/{id}/cancel` | Idempotent request; return current status. |
| `POST /api/jobs/{id}/retry` | Allowed for failed/cancelled jobs; enqueue one new attempt. |
| `GET /api/jobs/{id}/media` | Range-capable local WAV playback; no arbitrary path parameter. |
| `GET /api/jobs/{id}/transcript` | Published transcript and its edit revision. |
| `PATCH /api/jobs/{id}/transcript` | Text/name changes plus expected revision; `409` on stale edits. |
| `GET /api/jobs/{id}/export?format=...` | Generate from the last saved edit revision. |
| `DELETE /api/jobs/{id}` | Delete terminal jobs; `409` while active or queued. |

Use `413` for byte/duration limits, `415` for unsupported media, `422` for invalid options or undecodable input, `404` for unknown IDs, and `409` for state/revision conflicts. A request when required assets are absent returns `409 model_not_ready`. Errors contain stable codes and readable English messages. An upload failure never creates a queued job.

### Data contract sketch

```typescript
type Segment = {
  id: string;
  start: number; // seconds from normalized audio start
  end: number;
  speakerId: string | null;
  text: string; // original model text
  editedText: string | null;
  overlap: boolean;
};
type Speaker = { id: string; displayName: string };
type Transcript = {
  schemaVersion: 1;
  jobId: string;
  revision: number;
  language: string | null;
  segments: Segment[];
  speakers: Speaker[];
  warnings: { code: string; message: string }[];
  provenance: Record<string, unknown>; // validated engine/model manifest
};
```

The full JSON also stores words, regular/exclusive speaker turns, duration, requested/detected language, stage timings, model repository IDs and immutable revisions, package versions, device, and options. Speaker IDs and segment IDs are local to one job. SQLite stores jobs, attempts, options, warnings, and transcript edit revision. Keep an immutable inference result separate from user edits.

## 8. Storage, privacy, and setup

Default data root: the project’s Git-ignored `output/` directory (user decision on 2026-10-17, superseding the original home-directory default). Allow an explicit override. Store the database, media, and attempt files there. History must reopen saved transcripts. Automatically maintain TXT/SRT/VTT/JSON files for the latest saved revision in `output/jobs/<job-id>/`, show the local folder path, and report/retry copy failures without losing canonical edits. Preserve the previous default store as a backup during first-launch migration. Keep models in a separate configurable cache with a revision manifest. Private recordings, caches, database files, tokens, and generated transcripts must never enter Git. A future implementation must extend `.gitignore` accordingly.

Bind the server to `127.0.0.1` by default. Validate Host and Origin, disable broad CORS, and use a per-session local request token for mutations to prevent other websites from issuing local actions. The launcher supplies the token to its own frontend; it is separate from the Hugging Face token. Avoid filename-derived filesystem paths. Display names can retain the original filename, but storage paths use generated IDs. Serve only media owned by a known job.

Use no analytics, external fonts, remote JavaScript, or transcript content in logs. Application-level telemetry must be disabled; turn off pyannote metrics before loading its pipeline. Provision model assets only through an explicit setup step. Runtime model loading uses complete local snapshots with offline flags. If anything is missing, fail before inference rather than downloading silently.

The one-time setup sequence is: verify native arm64 tools, install pinned dependencies, obtain model access, download pinned snapshots and their transitive assets, build the UI, run `doctor`, and start. Account login, acceptance of gated access conditions, and acquisition of representative private samples remain user actions; an agent must not claim to have completed them. Keep the Hugging Face token in an environment variable or the user's external credential store, never in source, job records, browser state, or logs.

No setup, model download, or application installation is part of this specification-writing task. Proposed commands such as `make setup`, `make doctor`, and `make start` are acceptance targets for implementation, not commands available today.

## 9. Hardware and quality gate

The first implementation task is a small executable spike, before UI development. It must test native arm64 Python, MLX GPU inference, CPU pyannote, timestamp output, exact model snapshots, all downloads needed for offline operation, and telemetry settings. If it fails, revise the model/engine decision before continuing. `whisper.cpp` with Metal is the first ASR fallback to evaluate; keep the same transcript adapter contract.

Use at least one 5–10 minute English sample and one Polish sample with corrected references and two speakers. Include a short mixed-language case, three-speaker case, silence/music case, and overlapping speech. Samples must have permission for local use and stay outside Git. Add a small synthetic or redistributable fixture for automated plumbing tests; it does not establish real transcription quality.

Compare turbo and large-v3 with identical inputs and options. Record ASR, diarization, and total wall-clock times, real-time factor (`processing seconds / audio seconds`), peak process memory and system memory pressure, WER per language, speaker-attribution error, and observed failures. Record package/model revisions and cold/warm runs. Measure diarization separately; an Apple GPU does not establish its speed.

Proposed acceptance targets for clean reference speech: WER at most 15% separately for English and Polish; at least 90% correct speaker-attributed reference speech duration on a hand-labelled two-speaker sample, with permutation-invariant label mapping, a 250 ms boundary collar, and overlap excluded. Report overlap errors separately. Target total real-time factor at most 1.0 on a representative 30-minute file and no sustained memory pressure. These are decision thresholds, not measured claims or promises for noisy recordings.

If turbo misses quality and large-v3 passes, choose large-v3 as the default. If neither passes, document the failure and revise the scope or engine; do not call the model accepted. If only speed misses the target, preserve quality and present the measured runtime for review. When representative references are unavailable, label quality unverified; the UI can proceed against adapters, but the release cannot claim a passed quality gate.

## 10. Verification and definition of done

Test deterministic alignment with speaker changes, ties, gaps, unknown speakers, overlap, and missing word timestamps. Test valid SRT/VTT output, edited exports, state transitions, cancellation/publish races, stale edits, restart recovery, cleanup, and upload limits. Keep model tests separate from fast CI tests so ordinary checks do not download weights or require credentials.

A browser smoke test imports a redistributable fixture, observes stage status through a refresh, plays a timestamp, saves text/name edits, exports, and deletes the job. Run at least one actual English and one Polish model job on the target machine with diarization enabled. Run again with network access disabled and all assets cached. Capture results in a local benchmark report without private transcript text. A mock adapter proves the UI contract only.

The first iteration is done when FR-01 through FR-13 pass, the model quality gate has a recorded result, the setup and start instructions work from a clean environment, both dependency lockfiles exist, and no model download or credentials are required during normal offline use. Explicitly report any failed target or manual step still outstanding.

## 11. Delivery sequence and implementation tickets

The [implementation backlog](../tickets/README.md) maps these work slices to 12 [GitHub Issues labelled MVP](https://github.com/MarcinGruchala/local-scribe/issues?q=is%3Aissue%20label%3AMVP). GitHub tracks live issue status; local ticket files preserve the planning baseline and issue links.

1. Hardware/model spike and a reproducible model manifest; settle gated setup and profile selection.
2. Repository scaffold, dependency locks, setup/doctor/start commands, local store and migrations.
3. Durable import, job state machine, worker supervision, cancellation, retry, and recovery.
4. ASR/diarization adapters, alignment, warnings, provenance, and atomic result publication.
5. Local UI: readiness, import, history, status, playback, transcript edits, and deletion.
6. Exports, full offline verification, local quality/performance report, and user documentation.

Each ticket cites the relevant FR IDs, lists prerequisites, includes acceptance evidence, and leaves a runnable increment. Coding can run autonomously through the dependency order after implementation starts. Missing model access or reference recordings block the dependent evidence, not unrelated work against adapters. Failed hardware compatibility, unresolved quality thresholds, or a scope change require a recorded decision. Never claim a release gate passed with mock inference.

## 12. Technical sources

- [Model selection and primary-source evidence](../research/local-asr-models.md).
- [FastAPI uploads](https://fastapi.tiangolo.com/tutorial/request-files/): `UploadFile` uses a spooled file; the application must still enforce its own limits.
- [FastAPI background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/): heavyweight computation warrants separate process handling. The single local supervised worker is this project's design choice.
- [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/): local static frontend serving.
- [Vite static deployment](https://vite.dev/guide/static-deploy.html): production build output for same-origin local hosting.

Limits, interfaces, quality thresholds, and delivery choices form the accepted planning baseline. Model selection and measured quality remain provisional until validation. External documentation supports tool capabilities; it does not validate this application or its performance on this Mac.

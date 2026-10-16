# Durable job and media validation

Date: 2026-10-16. Scope: deterministic lifecycle and actual FFmpeg media plumbing, without model downloads, credentials, or private recordings.

## Reproduction

From the repository root after installing the locked development environment:

```sh
.venv/bin/python -m pytest -q tests/test_jobs.py tests/test_media.py tests/test_worker.py
.venv/bin/ruff check backend/src/localscribe/jobs.py backend/src/localscribe/media.py backend/src/localscribe/worker.py tests/test_jobs.py tests/test_media.py tests/test_worker.py
```

The scoped suite passed **39 tests**. The integrated suite at this checkpoint passed **108 tests**. Tests generate their own short PCM audio, video, and child-process fixtures in temporary directories. FFmpeg-dependent tests explicitly skip if the native tools are unavailable; the recorded run used actual installed FFmpeg and FFprobe and had no skips.

## Media evidence

- WAV, MP3, M4A, FLAC, OGG, MP4, and MOV audio fixtures import into durable queued jobs.
- Real FFmpeg normalization produces mono, 16 kHz PCM WAV with the expected duration. The original source bytes remain unchanged.
- Upload copying requests bounded chunks. Generated storage IDs prevent path traversal through display filenames.
- Empty, corrupt, unsupported, audio-free, over-byte-limit, over-duration, and insufficient-storage inputs return structured failures and leave no queued records or temporary import files.
- Import performs a complete FFmpeg audio decode to a null sink with strict corruption handling before queue publication. The decoded duration is recorded and independently enforces the duration limit even when container metadata understates it. Truncated WAV with an otherwise discoverable audio stream is rejected. A bounded decode stops just beyond the configured limit, and FFmpeg/FFprobe accept only local file/pipe input protocols.
- Boundary tests use configurable small limits and do not create multi-gigabyte media. A disk check retains a safety allowance and accounts for the derived PCM audio before queue publication.

Import request parsing/readiness rejection and normalized WAV HTTP range behavior are covered separately at the API boundary. These media tests do not establish transcription quality.

## Queue and process ownership

SQLite transactions claim the oldest queued job only when no attempt is active. Attempt options are copied into the attempts table when claimed. A transaction ends before starting FFmpeg or inference.

Status/history polling reads small warning metadata from SQLite without opening complete transcript files. Migration 3 backfills older results once. A transient SQLite claim failure waits briefly and retries; persistent failure to save an attempt failure stops the worker after terminating its child, leaving the active record for startup recovery. The worker exposes its actual thread liveness for diagnostics.

The launcher holds its store-level single-instance lock; the worker additionally owns `worker.lock` with an exclusive nonblocking `flock`. Every attempt uses a fresh process session. A small child gate waits for durable PID/create-time registration before it execs the pipeline. It receives the original parent PID and creation time explicitly, checks that identity before starting inference, and rejects adoption by another parent even if a permission file exists.

Recovery verifies a recorded PID, process creation time, the complete expected command, and the exact attempt request path before signaling a surviving group. It recognizes both the registration gate and final pipeline command. On macOS, the known Python launcher can rewrite its first argument to the current interpreter's `Python.app` executable; only that specific executable substitution is accepted, and all remaining arguments must match exactly. A reused PID or changed command does not authorize termination.

Cancellation sends SIGTERM to the child's process group, allows a short grace period, then sends SIGKILL to the group. The leader remains unreaped until that forced stop, preventing its PID from being reused during group termination. The deterministic suite includes an uncooperative child and grandchild that ignore SIGTERM. No process enumeration is required, because macOS sandbox restrictions can prohibit it.

## Persistence and race evidence

| Scenario | Verified outcome |
| --- | --- |
| Two simultaneous queue claims | Exactly one active attempt; FIFO ordering |
| Paused child inference | Database reads and a new import remain responsive |
| Active or queued cancellation | Safe repeated cancel; late output cannot publish |
| Cancel versus publish | The first SQLite write transaction determines the result; no cancelled attempt becomes completed |
| Retry | Only failed/cancelled jobs can enqueue; duplicate retry is rejected; next claim increments the attempt |
| Shutdown | Active child stops with a retryable interruption; queued work and sources remain |
| Restart | Completed results and queue survive; interrupted active attempts fail visibly |
| Failed atomic rename | Job is not reported completed and has no published transcript |
| Orphan import/publication | Startup removes unreferenced owned artifacts |
| Missing committed result | Recovery reports a failed, retryable job instead of a broken completion |
| Text and speaker edits | Revisions persist across new store instances; stale or invalid changes preserve the previous revision |
| Immutable model result | User edits do not alter original result bytes, model text, or provenance |
| Delete versus retry | Exactly one transition wins; an enqueued job cannot lose its source |
| Partial deletion failure | `deletion_failed` remains visible and blocks retry; startup retries cleanup |

## Deletion contract

Only completed, failed, cancelled, or already-deleting jobs can be deleted. Queued/active jobs return `409 invalid_state` with a cancel-first instruction. A durable `deleting` state prevents retry while filesystem removal is in progress. A removal failure returns `409 deletion_failed`, retains metadata, and can be retried explicitly or reconciled on restart. Successful deletion removes the owned directory and cascades attempt/edit metadata; shared models and other jobs remain. A later request for the removed ID, including another DELETE, returns `404 job_not_found`.

## Release boundary

These checks establish media handling, process lifecycle, and deterministic persistence behavior. They do not establish real ASR/diarization accuracy, speaker count accuracy, model performance, cached-model network isolation, or browser usability. Those require the separate model, browser, and offline release gates in the accepted MVP specification.

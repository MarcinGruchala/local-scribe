# LS-003 — Import and retain local media

Planning status at publication: open  
GitHub issue: [#3](https://github.com/MarcinGruchala/local-scribe/issues/3) — live status tracker  
Dependencies: LS-002  
Requirements: FR-02, FR-12; specification sections 3, 6, 7, and 8

## Outcome

A supported local recording becomes a durable queued job. The original file remains available until explicit deletion, including after audio conversion.

## Work

- Implement streamed multipart import and validate job options, allowed formats, actual audio streams, byte count, and decoded duration with FFprobe.
- Enforce 2 GiB and 2-hour limits. Store files beneath generated job IDs; treat the original filename only as display metadata.
- Preserve original media. Add the FFmpeg wrapper for 16 kHz mono PCM WAV and consistent timeline handling; LS-004 invokes conversion in a child process.
- Publish the queued database record only after a complete validated import. Clean failed uploads and reconcile abandoned import files after restart.
- Reserve and check sufficient disk space, including the derived WAV. Use argument arrays rather than a shell command.
- Implement `POST /api/jobs`, paginated `GET /api/jobs`, and `GET /api/jobs/{id}` with the documented status/error contracts. A temporary unavailable-worker state is acceptable until LS-004.

## Acceptance criteria

- [ ] Valid supported audio and audio-bearing video create durable jobs with immutable options.
- [ ] Original bytes remain intact after normalization; generated audio has the expected rate/channels and duration.
- [ ] Empty, corrupt, unsupported, audio-free, over-byte-limit, and over-duration inputs fail with the specified status/code.
- [ ] Invalid options and missing required model readiness do not create queued jobs.
- [ ] Failed imports leave no owned partial files or queued records.
- [ ] Filenames cannot escape the data root; large uploads do not require holding the complete file in RAM.

## Verification

Use small redistributable/generated fixtures with and without audio. Test boundaries by configurable limits rather than generating multi-gigabyte fixtures. Verify normalized metadata with real FFprobe. Stub readiness in fast import tests and separately check missing-model rejection.

## Completion record

2026-10-16: Completed. Real FFmpeg tests cover all seven supported formats, retained bytes, mono 16 kHz normalization, complete decoded-duration validation, corrupt/truncated/audio-free/size/duration/storage failures, bounded copying and cleanup. Readiness and option failures enqueue nothing. See tests/test_media.py and tests/test_api.py.

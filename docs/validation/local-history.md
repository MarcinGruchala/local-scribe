# Local history and disk files — 2026-10-17

The user requested discoverable history and transcript files inside an ignored project folder. The default store is now `output/`; model assets remain outside the checkout. Existing History reopens canonical saved transcripts. Each completed job owns `transcript.txt`, `.srt`, `.vtt` and `.json`, updated from the latest explicitly saved revision. Copy errors are separate from canonical save success. Startup validates hashes/revisions and repairs outdated, missing or modified copies; authenticated regeneration is also available.

The launcher copies an existing previous default SQLite store and owned media into an empty default destination, under both source/destination ownership locks. SQLite backup includes WAL changes. An installation journal and database-last publication allow restart after interruption. The original store remains a backup, including its media; deleting a migrated job does not remove that backup. Unrelated validation files are not migrated. The actual existing default store was empty; production startup successfully migrated it and reported the new absolute output path. Populated history, saved edits and media migration were verified in deterministic tests.

Verification: 208 model-free tests pass, including 19 disk-copy tests and 18 legacy-store migration tests. Ruff, TypeScript and frontend production build pass. Actual Chromium 156.0.8078.4 runs `tests/browser-local-files.cjs` against the explicit synthetic harness on loopback 8766. All nine checks pass:

1. Completion creates four files identical to HTTP exports.
2. Saved text/name edits update all four file contents.
3. Folder/file clipboard controls copy the actual absolute paths.
4. Reload and History preserve the selected saved transcript.
5. Pending status polling stops after files become ready.
6. A simulated copy error displays separate feedback without losing saved edits.
7. Authenticated regeneration repairs an actually missing file.
8. Layout fits 1024, 760 and 390 pixels; screenshots were inspected.
9. Explicit deletion removes the owned folder and history entry.

The browser reported zero external requests and zero page errors. Its own fixture jobs were deleted. Raw browser JSON/screenshots remain outside Git. Fixtures establish application behavior only, not transcription quality. `git check-ignore` confirms the output files are excluded; private audio/transcripts are not committed. The earlier private long-run exports are available under ignored `output/validation/long-recording/`; these benchmark artifacts are not fabricated application history entries.

Actual cached-model EN and PL application/browser repeats also pass on the default `output/` store under OS external-network denial and empty `HF_HOME`. Each run has ten checks: actual GPU ASR + CPU diarization, automatic four-file copies identical to HTTP exports, playback/seek, saved name/text edits and reload, four downloads identical to the refreshed disk files, and owned-folder deletion. EN: child total 6.322 s, ASR 1.003 s, diarization 3.856 s; PL: total 5.184 s, ASR 1.025 s, diarization 2.844 s. Both have zero external-origin requests/page errors. These remain short functional samples, not representative accuracy evidence. Raw JSON/screenshots are retained under ignored `output/validation/local-history/`. Migration recovery tests additionally cover actual SIGKILL before staging creation and after private file copying, schema-1 stores, restarted source locks, and latest-revision export repair after moving the store.

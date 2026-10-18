# Restore existing inference into transcript history

## Cause and correction

The user's earlier long recording was transcribed by the benchmark runner before application history was used. Its four exports existed under ignored `output/validation/long-recording/`, but the active SQLite store contained no corresponding completed job. The new history view correctly lists completed database entries; it cannot discover standalone benchmark exports automatically.

A maintenance command restores an existing validated inference export with its original and normalized playback media. It requires the app to be stopped and takes the same launcher lock. It copies sources, preserves immutable model text/words/turns/timing and existing edits, records restoration provenance (`inferenceRerun: false`), publishes a completed history entry directly, and generates the four normal local files. Nothing enters the inference queue. Repeating the same restoration preserves the entry and any subsequent edits. Original benchmark artifacts remain intact; deleting the restored job only removes its active-store copies.

```sh
# Stop the application first. Use matching existing source/audio/result files.
.venv/bin/python -m localscribe.restore \
  --transcript /absolute/private/transcript.json \
  --source /absolute/private/original.m4a \
  --normalized /absolute/private/normalized.wav
LOCALSCRIBE_PORT=8768 make start
```

The destination defaults to ignored project `output/`; `--data-root` can select an allowed alternative. This is recovery of previously computed output, not a new transcription or a quality claim. An invalid/mismatching normalized duration or format is rejected before creating history. A failed copy cleans unpublished files and leaves source artifacts untouched.

## Actual verification (2026-10-17)

The initial reproduction reported saved long exports present and no matching completed history entry. After restoration, the same database comparison finds the entry, and the API returns the existing 3762.517-second/724-segment result. Original raw text/model segments/words/regular and exclusive turns were compared with the preserved real inference output before restoration. No model ran.

Actual Chromium opens the user's new history/review UI, finds the entry, renders all 724 segments, loads normalized audio, seeks and plays beyond one hour, accepts an editable draft across view switches, and reloads the unchanged saved transcript. There are zero page errors and zero external requests. The read-only verification does not save changes to the private text. Its report is retained in ignored `output/validation/long-recording/browser-restoration.json`.

Three regression tests verify real history/API/playback/export/edit behavior, idempotence after later saved edits, source retention/deletion, duration mismatch and copy-failure cleanup. The full 213-test model-free suite, Ruff and the current frontend TypeScript/build pass. The user's uncommitted history/review frontend changes are preserved.

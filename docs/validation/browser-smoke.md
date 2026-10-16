# Browser workflow validation

Date: 2026-10-16 (Europe/Warsaw).

## Fixture workflow result

Passed in actual headless Chromium 156.0.8078.4, driven by Playwright 1.64.1. The built production frontend and real FastAPI/SQLite/media/worker routes ran at `http://127.0.0.1:8766` with an isolated `/private/tmp/localscribe-browser` data root. Real FFmpeg prepared valid synthetic WAV files. An explicitly test-only child returned deterministic speaker segments; no ASR or diarization weights were loaded. This is application integration evidence, not model-quality evidence.

The successful browser run made 134 requests, observed zero external-origin requests, and recorded zero uncaught page errors. External-origin requests were blocked by a browser routing rule. This does not replace the separate operating-system network-disabled model release gate.

| Workflow | Observed evidence |
| --- | --- |
| Readiness | Same-origin health loaded; missing Quality was absent from profile choices. |
| Import | Native file picker and external-style `DataTransfer` file drop each created a completed job. Language and exact speaker-count selections were submitted. Upload state appeared from real `XMLHttpRequest.upload` events. The first upload was throttled through Chromium network emulation so computable progress could be observed and asserted; subsequent imports ran without throttling. |
| Status and recovery | The selected job and current stage survived a full browser reload. Completed detail polling stopped during a 2.2-second observation window. |
| Playback | Chromium decoded normalized WAV; clicking the second segment timestamp sought to two seconds and selected its segment. Playback advanced the current time. |
| Editing | Segment text and a speaker display name persisted after save and full reload. |
| Exports | TXT, SRT, VTT and JSON were downloaded through four separate browser link actions. Every file contained the saved text/name edits; SRT timestamps, VTT header and JSON schema version were checked. |
| Conflict and failure | A concurrent real API edit produced an actual `409` stale-revision response. The local draft remained visible and the previous saved text remained intact. An injected HTTP `500` save failure likewise preserved draft and saved state. |
| Queue and cancellation | A second file queued behind one active child. Queued and active cancellation reached `cancelled`; retry returned queued work and a cancelled active job completed as attempt 2. |
| Confirmations | Retry confirmation could be dismissed without enqueuing and accepted to retry. Delete confirmation could be dismissed safely and accepted to delete. |
| Deletion | Confirmed deletion made the API return `404` and removed the job-owned directory. |
| Layout | Import and transcript views had no horizontal overflow at 1024, 760 and 390 CSS pixels. Viewport screenshots were visually inspected for readable controls and layout. |
| Local resources | All browser resources stayed on the application's loopback origin. No external fonts, scripts or other assets were requested. |

Browser validation found and fixed explicit accessible names for the option selects and navigation scroll restoration when changing jobs. Upload progress is computed only from measurable upload events; processing stages show elapsed time rather than fabricated percentages. Interrupted deletion states offer a deletion retry action.

Screenshots, downloads, fixture media, SQLite data and raw test results remain outside Git in the temporary test root. No private recording or transcript is included in this report.

## Reproduction

Build the frontend, start the explicit fixture-only harness, and run the separate browser script. Do not run the harness as the normal application or treat its readiness override as production model readiness.

```sh
make build
uv run python tests/browser_server.py
```

In another terminal:

```sh
npm install --prefix /private/tmp/localscribe-browser-runner --save-exact playwright@1.64.1 --ignore-scripts
/private/tmp/localscribe-browser-runner/node_modules/.bin/playwright install chromium
NODE_PATH=/private/tmp/localscribe-browser-runner/node_modules node tests/browser-smoke.cjs
```

The browser script can use an existing matching browser executable through `BROWSER_EXECUTABLE`; the recorded run used the installed Chromium revision 1248. The harness owns port 8766 and never loads model weights or credentials. The browser scripts are separate from fast Python tests and require an explicitly provisioned local browser. Stop the fixture harness with Ctrl+C after verification.

## Limits

Only Chromium was exercised. Safari, Firefox and user-installed browser versions remain unverified. Synthetic transcripts and the injected HTTP failure validate application behavior; they do not establish recognition quality, speaker-attribution accuracy, representative runtime, memory pressure, or cached diarization completeness.

## Real cached-model ASR-only browser result

A separate real browser run used the normal application at `http://127.0.0.1:8767`, the cached Fast model, and the public 11-second JFK FLAC sample supplied for validation. The application process hierarchy ran under the local operating-system offline sandbox profile; the browser allowed only this loopback origin. This run used no readiness override, fake engine, fixture child, or inference-response interception.

The missing diarization model correctly disabled submission with the default speaker option enabled. Explicitly turning speaker turns off enabled import. Forced-English transcription completed using MLX on the GPU. The browser then sought a transcript timestamp, started and paused playback through native keyboard audio controls, saved an edit, reloaded it, downloaded each of TXT/SRT/VTT/JSON independently, and confirmed deletion. The deleted job returned `404`. Nine browser checks passed, with zero observed external-origin requests and zero uncaught page errors. The normal application was left running.

| Measurement | Recorded value |
| --- | --- |
| Browser | Chromium 156.0.8078.4; Playwright 1.64.1 |
| Audio duration | 11.000 s |
| Model | `mlx-community/whisper-large-v3-turbo` |
| Immutable model revision | `a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb` |
| Engine/device | `mlx-whisper` / GPU |
| Preparing stage | 0.041 s |
| ASR stage | 1.064 s |
| Total child pipeline | 2.548 s |
| Browser submit-to-visible-result | 3.332 s |
| Diarization | Explicitly disabled; required cached asset unavailable |

These short-sample timings are functional evidence only. They do not measure a representative 30-minute performance target, WER, speaker-attribution accuracy, cold/warm profile comparison, or memory pressure. Cached English ASR is verified through the application under the offline sandbox; cached English/Polish inference with diarization remains a separate release requirement.

The separate replay script is `tests/browser-real-asr.cjs`. It assumes an already running real server at port 8767, cached models, and the locally supplied public sample at `/private/tmp/localscribe-validation/jfk.flac`. Run it with the same `NODE_PATH` shown above after starting the real application under the documented offline gate. Do not start this run while another model job is active. It creates and explicitly deletes only its validation job. It logs sanitized timings and provenance, never the recognized transcript. The sanitized raw result is outside Git at `/private/tmp/localscribe-real/browser-real-asr-results.json`.

## Focused result-state checks

Five additional checks passed in the same actual Chromium browser against the fixture-only server:

- Missing cached ASR assets displayed actionable setup guidance and disabled import.
- Keyboard activation opened the real file picker and Enter submitted the form. A requested diarization failure completed with warnings, preserved the synthetic text, showed explicit unknown speaker labels, and did not invent overlap or named speakers.
- A separate successful speaker fixture showed stable anonymous labels and the overlapping-speech indicator.
- An intentionally disabled diarization fixture completed with `Text only` labels and no diarization-failure warning; provenance recorded `disabled`.
- An injected deletion failure refreshed the visible persisted-failure state and offered `Retry deletion`. After removing the injected HTTP responses, the confirmed retry deleted the actual disposable fixture job.

The deletion failure in this browser check is an HTTP/UI simulation; filesystem failure and restart reconciliation are covered separately by backend tests. No model-quality claim follows from these fixtures. The focused runner is `tests/browser-states.cjs`, invoked with the same `NODE_PATH`; it requires the running fixture harness. Its sanitized result is outside Git at `/private/tmp/localscribe-browser/browser-state-results.json`.

## Real Polish ASR-only browser result

The same unmocked, OS-offline application workflow also passed all nine checks with the public 12.12-second Polish FLEURS recording and forced `pl`. The actual child pipeline took 2.652 s (preparing 0.042 s; ASR 1.224 s), and submit-to-visible-result took 4.334 s. Normalized playback, timestamp seeking, saved edit/reload, all four independent downloads, and confirmed deletion succeeded. Chromium observed zero external requests and zero page errors. Speaker processing was explicitly disabled; this does not satisfy diarization or representative Polish quality gates.

The replay script accepts `REAL_SAMPLE` and `REAL_LANGUAGE=en|pl` for these explicitly prepared public samples. It writes a sanitized language-specific result outside Git. The Polish raw result is `/private/tmp/localscribe-real/browser-real-asr-pl-results.json`.

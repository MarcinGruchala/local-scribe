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

These short-sample timings are functional evidence only. They do not measure a representative 30-minute performance target, WER, speaker-attribution accuracy, cold/warm profile comparison, or memory pressure. At this stage, cached English ASR was verified through the application under the offline sandbox. The later complete-model section below records the subsequent English/Polish runs with real diarization.

The separate replay script is `tests/browser-real-asr.cjs`. It assumes an already running real server at port 8767, cached models, and the locally supplied public sample at `/private/tmp/localscribe-validation/jfk.flac`. Run it with the same `NODE_PATH` shown above after starting the real application under the documented offline gate. Do not start this run while another model job is active. It creates and explicitly deletes only its validation job. It logs sanitized timings and provenance, never the recognized transcript. The sanitized raw result is outside Git at `/private/tmp/localscribe-real/browser-real-asr-results.json`.

## Focused result-state checks

Seven focused checks passed in the same actual Chromium browser against the fixture-only server:

- Missing cached ASR assets displayed actionable setup guidance and disabled import.
- Replacing a valid file with an empty selection or a multi-file drop cleared the prior file and disabled submission. A drop while an upload request was pending left the original visible filename unchanged.
- Keyboard activation opened the real file picker and Enter submitted the form. A requested diarization failure completed with warnings, preserved the synthetic text, showed explicit unknown speaker labels, and did not invent overlap or named speakers.
- A separate successful speaker fixture showed stable anonymous labels and the overlapping-speech indicator.
- An intentionally disabled diarization fixture completed with `Text only` labels and no diarization-failure warning; provenance recorded `disabled`.
- An injected deletion failure refreshed the visible persisted-failure state and offered `Retry deletion`. After removing the injected HTTP responses, the confirmed retry deleted the actual disposable fixture job.

The deletion failure in this browser check is an HTTP/UI simulation; filesystem failure and restart reconciliation are covered separately by backend tests. No model-quality claim follows from these fixtures. The focused runner is `tests/browser-states.cjs`, invoked with the same `NODE_PATH`; it requires the running fixture harness. Its sanitized result is outside Git at `/private/tmp/localscribe-browser/browser-state-results.json`.

## Real Polish ASR-only browser result

The same unmocked, OS-offline application workflow also passed all nine checks with the public 12.12-second Polish FLEURS recording and forced `pl`. The actual child pipeline took 2.652 s (preparing 0.042 s; ASR 1.224 s), and submit-to-visible-result took 4.334 s. Normalized playback, timestamp seeking, saved edit/reload, all four independent downloads, and confirmed deletion succeeded. Chromium observed zero external requests and zero page errors. Speaker processing was explicitly disabled; this does not satisfy diarization or representative Polish quality gates.

The replay script accepts `REAL_SAMPLE` and `REAL_LANGUAGE=en|pl` for these explicitly prepared public samples. It writes a sanitized language-specific result outside Git. The Polish raw result is `/private/tmp/localscribe-real/browser-real-asr-pl-results.json`.


## Unsaved navigation and history regression

Eleven focused actual-Chromium checks passed after adding the internal navigation guard. Declining the discard confirmation preserved the same current hash and unsaved text for browser Back, New recording, the home link, another history selection, and a direct fragment change. Accepting it navigated and retained the last saved server result. A successful save cleared the guard before navigation; no discard dialog appeared. The native `beforeunload` confirmation still protected refresh, and dismissing it retained the draft.

Deleting a dirty disposable fixture used the in-app deletion confirmation, explicitly named the recording, and navigated after success without a second discard prompt. The confirmation's filename is rendered as escaped React text. An injected stopped-worker health response displayed the restart guidance.

The history regression seeded 51 terminal jobs and one active deterministic child. Loading older history increased the visible count from 50 to 64 in the final run (two requested pages); repeated active-job polling preserved those loaded rows. Refresh now re-fetches the requested number of 50-row pages, and a stale shorter request cannot replace a longer loaded history. The fixture setup removes only its earlier terminal pagination fixtures before reseeding.

Reproduce after the full fixture browser smoke has created completed picker/drop fixtures:

```sh
uv run python tests/browser_server.py --seed-pagination
NODE_PATH=/private/tmp/localscribe-browser-runner/node_modules node tests/browser-navigation.cjs
NODE_PATH=/private/tmp/localscribe-browser-runner/node_modules node tests/browser-states.cjs
```

These runners use only the fixture server and never invoke a model. The navigation runner cancels its active fixture child on exit. Its sanitized result is outside Git at `/private/tmp/localscribe-browser/browser-navigation-results.json`. The normal application and its model cache are untouched.

After the final model-pinning/provenance fix, all nine real Polish browser checks passed again under the OS offline policy. The recording and transcript preserved the imported Fast repository/revision, runtime package versions and FFmpeg provenance were present, and saved edits/export/deletion remained valid. This repeat recorded child total 2.387 s (ASR 1.053 s) and browser submit-to-result 3.327 s. It confirms the final contract, not a new quality/performance gate.


## Complete cached ASR and diarization browser validation

After the user personally accepted the Community-1 conditions and authorized the local Hugging Face CLI, explicit provisioning prepared the pinned speaker snapshot. Three complete real browser runs then passed sequentially against the normal application at `http://127.0.0.1:8767`. The application and all inference descendants ran under `scripts/offline.sb`, with external networking denied, an isolated `/private/tmp/localscribe-full-offline` data root and an empty `HF_HOME` at `/private/tmp/localscribe-no-hf-home`. The browser allowed only the application loopback origin. No fixture child, readiness override, remote inference, inference-response interception, or cached global Hugging Face account store was used for these runs.

Each run passed nine actual-Chromium checks: complete readiness and default speaker-enabled import; real MLX GPU ASR plus Community-1 CPU diarization; normalized playback and timestamp seeking; persistent text and speaker-name edits through reload; independent TXT, SRT, VTT and JSON downloads; and named-confirmation deletion of only that run's new recording. Anonymous speaker IDs remained stable through editing/reload, and JSON retained unchanged regular and exclusive speaker turns. Both immutable model references matched job settings, requested provenance and actual engine provenance. Every run observed zero external browser requests and zero uncaught page errors.

| Input | Requested/detected language | Duration | ASR stage | Diarization stage | Total child pipeline | Browser submit-to-result | Speakers; regular/exclusive turns | Warnings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Public FLEURS English | en / en | 10.560 s | 1.445 s | 3.107 s | 6.201 s | 8.524 s | 1; 3 / 3 | None |
| Public FLEURS Polish | pl / pl | 12.120 s | 1.215 s | 3.906 s | 6.768 s | 8.523 s | 1; 2 / 2 | None |
| Constructed recurring voices A-B-A-B | auto / pl; exact-count hint 2 | 45.360 s | 2.396 s | 19.347 s | 23.214 s | 25.575 s | 2; 12 / 12 | `alignment_fallback` |

The ASR engine was `mlx-whisper` on GPU, with `mlx-community/whisper-large-v3-turbo` revision `a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb`. Diarization used `pyannote.audio` on CPU, with `pyannote/speaker-diarization-community-1` revision `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee`. Browser: Chromium 156.0.8078.4, driven by Playwright 1.64.1.

The individual English and Polish samples each contain one voice. The constructed case concatenates the same public Polish and English voice samples in A-B-A-B order; it returned two stable anonymous IDs and five display segments. It is not a natural conversation or an independent reference-quality dataset. Its alignment warning remains part of the result; successful speaker-model execution must not hide fallback alignment. See [public sample provenance](public-samples.md).

These results establish the complete functional cached-model browser workflow under external-network denial, including real speaker processing for both languages. They do not establish WER thresholds, 90% speaker-attributed reference duration, reliable overlap transcription, representative 30-minute runtime, sustained memory pressure or 60-minute stability. The stage times include normal fresh inference children with previously exercised filesystem/runtime caches; no cold-start or representative performance claim follows. Peak memory was not measured by these browser runners.

Sanitized raw results remain outside Git:

- `/private/tmp/localscribe-full-offline/browser-full-en-results.json`
- `/private/tmp/localscribe-full-offline/browser-full-pl-results.json`
- `/private/tmp/localscribe-full-offline/browser-full-abab-results.json`

The reusable runner is `tests/browser-real-diarization.cjs`. Start the normal application under the offline policy with complete cached models, then run one language at a time while no other model job is active:

```sh
NODE_PATH=/private/tmp/localscribe-browser-runner/node_modules \
  REAL_LANGUAGE=en REAL_CASE=en \
  REAL_SAMPLE=/absolute/approved-english.wav \
  REAL_OUTPUT_ROOT=/absolute/private-validation-results \
  node tests/browser-real-diarization.cjs

NODE_PATH=/private/tmp/localscribe-browser-runner/node_modules \
  REAL_LANGUAGE=pl REAL_CASE=pl \
  REAL_SAMPLE=/absolute/approved-polish.wav \
  REAL_OUTPUT_ROOT=/absolute/private-validation-results \
  node tests/browser-real-diarization.cjs
```

`REAL_BASE` overrides the loopback origin; `REAL_SPEAKER_COUNT` optionally supplies a valid count hint. `REAL_LANGUAGE=auto` is supported for a separately approved mixed-language case. The script never logs recognized text, refuses report output inside the checkout, and deletes only the validation job it created. The historical ASR-only runner deliberately tests missing-diarization readiness and remains separate from this complete-model runner. The normal validation application was left running after these checks.

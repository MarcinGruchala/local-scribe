# Transcript cleanup validation — 2026-10-19

Executed on Marcin's native arm64 Mac with 64 GiB unified memory. This continuation is stacked on PR #20 at `f7d3cf9dc845695d92df3e7ba21d569fc9ba6451`; that PR was not merged. Its earlier reported tests were treated as historical until rerun here. Live scope: #17, #18 and #19, preserving #15/#16 behavior.

## Software evidence

- `make check`: final **290 passed**, Ruff and TypeScript PASS; one pre-existing Starlette/httpx deprecation warning. `make build` and `git diff --check`: PASS.
- Grouping Chromium runner: **16 checks** pass, including real HTTP/browser restart, 400 synthetic source segments, batch preview/apply, barriers/manual splits, conflict/draft retention, exact persisted Undo/Redo, exports and recording-owned deletion.
- Proofreading Chromium runner: **8 checks** pass, covering grouping -> selected saved block -> glossary/diff -> individual rejection/selected acceptance -> exact Undo/Redo -> HTTP/browser restart; whole-recording cancellation, malformed/unknown IDs, visible drafts/stale results, and 1440/760/390 px layouts. No page errors or external browser requests observed. Only the model adapter is synthetic; HTTP, worker, SQLite and exports are real.
- Regression coverage includes protected numbers/names/typographic negation, duplicate/context IDs, invalid/oversized/redirect/auth responses, ignored proxies, incomplete/reasoning responses, interrupted tasks, unavailable models, exact old values, deletion, export copies, a non-starving idle store, transient SQLite failure and an inherited ASR lock surviving a launcher `os._exit`.
- Independent Standards and Spec reviews found five concrete issues: typographic negation, obsolete block scope, malformed nested JSON, SQLite worker failure and ASR lock lifetime. All were fixed with regressions and re-reviewed without remaining findings in those changes. Real testing also corrected the terminal stale status and confirmation/recovery messages.

An intermediate full run while a model was loading failed two existing timing-sensitive benchmark tests (`test_interruption_stops_own_child_and_preserves_sanitized_failure`, `test_timeout_never_becomes_completed_when_child_handles_term_successfully`). The final full idle run passed. PR #20 already documented this sensitivity; benchmark production behavior and its timing assumptions were not changed to hide it. No repository CI workflow exists; these are local results, not a CI-green claim.

Reproduce fixture checks after provisioning dependencies/browser, without loading a model:

```sh
uv sync --frozen
(cd frontend && npm ci)
make check
make build
NODE_PATH=/absolute/existing-playwright/node_modules uv run --frozen --no-sync python tests/run_grouping_browser.py
NODE_PATH=/absolute/existing-playwright/node_modules uv run --frozen --no-sync python tests/run_proofreading_browser.py
```

The browser runners choose fresh private synthetic roots and ports 8770/8771; override `LOCALSCRIBE_GROUPING_TEST_PORT` if occupied. They require an existing matching Chromium/Playwright installation. Recorded browser: Chromium 156.0.8078.4, Playwright 1.64.1. Python 3.11.6; Node 26.8.1. No model downloads were performed.

## Actual model and offline evidence

| Setting | Observed value |
| --- | --- |
| LM Studio | 0.4.26+4 |
| Model key | `qwen/qwen3.8-27b` |
| Concrete artifact | `lmstudio-community/Qwen3.8-27B-MLX-4bit` |
| Format / quantization | MLX Safetensors, affine 4-bit, group size 64 |
| Artifact size | 16,081,678,492 bytes reported by local model discovery |
| Runtime | `mlx-llm-mac-arm64-apple-metal-nax-advsimd@1.13.1` |
| Instance / context / parallel | `localscribe-proofreading` / 8192 / 1 |
| API | `/api/v1/models` discovery, `/v1/chat/completions` constrained JSON |
| Prompt / generation | `conservative-v1`, temperature 0, max output 2400, `reasoning_effort=none`, `enable_thinking=false` |
| Exact local artifact identity | SHA-256 of sorted 13-file SHA-256 manifest: `4268b6795c687046cb7d6254d841197df63ac4a29670469d58f4eb5e2513df55` |

The local download did not establish a trustworthy upstream immutable revision; exact file hashes are retained privately instead of inventing a revision. Model paths and instance identifiers are configurable, never defaults embedded in application code.

The initial actual probe verified constrained JSON and zero reasoning tokens together. The final checked-in spike procedure tested **40 synthetic EN/PL/mixed passages** in **21.16 s**, returning **five spelling corrections**, reviewed against the known source set. There were zero critical unsupported factual changes, number/name/negation changes, additions, omissions or invalid target IDs in this fixed set. All five response batches reported zero reasoning tokens. This does not guarantee safety on unseen text or establish ASR accuracy. Earlier five-target batches produced four corrections; changed chunk context can change model output. Nothing is auto-accepted.

Two original recordings were copied privately; new five-minute clips were extracted at source offset 120 s. The EN excerpt contains 58 saved source segments (256.6 segment-seconds of speech), PL 98 (242.9 segment-seconds). Source identifiers, offsets, exact checksums, raw model output and screenshots remain only in the private validation root. Natural excerpt whole-recording previews under external-network denial completed in **13.15 s / 8 chunks EN** and **23.25 s / 13 chunks PL**. The final conservative prompt proposed no EN change and one unchanged PL phrase flagged for listening. An earlier overbroad grammatical proposal prompted a tighter prompt and validator before final acceptance.

Actual Chromium then exercised both languages with deliberate, locally introduced spelling errors in the copied excerpts, clearly separated from natural ASR quality evidence. The loaded model repaired exactly those errors; selected acceptance, reload, Undo/Redo, TXT/SRT/VTT/JSON exports and audio seeking passed. Source text, segment IDs, speaker attribution and timestamps were compared before/after. The controls do not shift words between segments or retime subtitles.

Actual lifecycle checks:

- Cancellation during a model request reached `cancelled` in 1.08 s, with no suggestions and LM Studio reporting idle before the next heavy task.
- A manual save during inference ended the preview as `stale` in 0.90 s with no published suggestions; saved text survived.
- Killing only the validation launcher during an actual request left the durable completion barrier. Restart marked the task `interrupted`, published no suggestions, and blocked further heavy work until the configured instance was explicitly unloaded and observed absent. Unrelated sessions were never unloaded.
- With that model absent, starting proofreading returned actionable `409 proofreading_not_ready`; model-free grouping remained available.
- Accepted EN/PL text survived actual application restart. Fixture tests additionally cover malformed/duplicate/stale/schema/auth/redirect/proxy/transport/file-copy failures. Not every malformed response was induced in the actual model.

LM Studio reported 14.98 GiB at model load. During the real cancel/stale loop, the largest sampled model-descendant RSS was 11,579,686,912 bytes. This is a sampled resident-process observation, **not** a complete unified-memory/GPU peak or a long-recording benchmark. No out-of-memory event was observed. External applications and manually initiated LM Studio predictions remain outside the scheduler's control.

LocalScribe and the LM Studio parent/descendants ran under macOS external-network-denial policies with loopback available. Electron initially failed Unix IPC/nested sandbox initialization. The successful isolated service used `scripts/offline-lmstudio.sb` and the local executable's `--run-as-service --no-sandbox`; the outer network-denial policy still applied. A separate socket probe under the same policy got `PermissionError` for an external IP and HTTP 200 for local model discovery. The recorded model parent was verified already running before `lms load`, avoiding an unsandboxed auto-start substitution. Browser routing separately observed zero external requests. These checks do not audit all LM Studio logging/storage or prove its general security.

After unloading LM, fresh cached local ASR compared two **22-second** audio windows around selected EN/PL phrases (Fast EN 1.15 s, Quality PL 2.34 s). It corroborated the source wording and recurring uncertain PL terminology; it did not justify guessing a replacement. No full recording was retranscribed or diarized. This machine comparison is not an independent human acoustic reference audit; WER, speaker accuracy and quantitative correction accuracy were not measured. Manual reference listening remains the quality limitation, with uncertain text deliberately left for the owner.

Reproduce the public synthetic model check using the verified loaded artifact and private output root:

```sh
LOCALSCRIBE_LM_MODEL=localscribe-proofreading \
  /usr/bin/sandbox-exec -f scripts/offline.sb \
  .venv/bin/python scripts/proofreading_spike.py --output-root /absolute/private-cleanup-validation
```

Manually review `proofreading-spike.json` locally. For private audio, first copy into an isolated store and record source hashes/offsets outside Git. Use the normal app with `--data-root` and a free test port. See setup for the separate LM Studio isolation procedure; sandboxing only the CLI does not sandbox an already-running server.

## Preservation and handoff

Original history remained served by the unchanged main checkout on port 8765. The feature used a different worktree and isolated store on port 8772. An isolated backup copy was migrated to verify existing job records, options, metadata, revisions and saved edits stayed exact. The personal store itself was never migrated, reset, deleted, or opened by the feature worker. Final integrity comparison: **34 original files checked, zero changed**, including database, original media, canonical transcripts and exports. Main checkout remained clean at `4e4b387`.

Private artifacts are under `/private/tmp/localscribe-cleanup-validation-20261019`, outside Git. This includes the source/integrity manifests, store copies, five-minute clips, short ASR windows, model manifest, natural/controlled previews, lifecycle results and screenshots. Temporary storage is not a durable backup; preserve it locally if needed. Do not publish any private contents.

Current JSON exports retain original ASR provenance plus accepted proofreading-batch provenance in the existing open provenance object; original exports remain unchanged. Undo/Redo restores the exact provenance snapshot along with text. No acceptance of the deferred ASR release thresholds, merge, issue closure, release or deployment is implied. The remaining quality limitation is independent reference listening; implementation and review have no known blocking software defect at handoff.

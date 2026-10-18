# Transcript grouping and persistent history validation

Scope: #15 (shared saved-operation history) and #16 (deterministic whole-transcript grouping). Base `4e4b387`; backend integration `858efda`; final UI/test/documentation changes are identified by the containing commit/PR. This is not acceptance of #17–#19, a new ASR quality claim, a Mac installation test or authorization to merge/deploy.

## Executed environment and commands

Linux assistant host, CPython 3.11.15 (project core environment), Node 24.21.0, npm 11.19.0. Core dependencies installed with `uv sync --frozen`; frontend installed with `npm ci` (zero reported dependency vulnerabilities). No model extras or weights installed. Tool paths in this environment: `/opt/data/tools/uv-0.12.3-linux-x64/uv`, existing Playwright package via `NODE_PATH=/opt/data/dev/github/MarcinGruchala/na-jednej-fali/node_modules`, Chromium via `BROWSER_EXECUTABLE=/opt/data/tools/chromium-1208/chrome-linux64/chrome`. The other project's files were not modified.

```sh
export PATH=/opt/data/tools/uv-0.12.3-linux-x64:$PATH
unset PYTHONPATH PYTHONHOME
make check
make build
git diff --check

export NODE_PATH=/opt/data/dev/github/MarcinGruchala/na-jednej-fali/node_modules
export BROWSER_EXECUTABLE=/opt/data/tools/chromium-1208/chrome-linux64/chrome
unset UI_CONTRACT_FIXTURE LOCALSCRIBE_GROUPING_TEST_ROOT
.venv/bin/python tests/run_grouping_browser.py
```

The final integrated core run at this checkpoint: **233 tests passed**, Ruff passed, TypeScript passed, production build passed, whitespace check passed. One dependency deprecation warning remains (`starlette.testclient` using `httpx`). The new feature tests cover grouping/history/HTTP/export behavior; no accuracy metrics are inferred from them.

Earlier full runs intermittently failed the pre-existing benchmark process timing tests (`test_timeout_stops_uncooperative_child_and_process_group` and `test_interruption_stops_own_child_and_preserves_sanitized_failure`). They also failed before backend integration; a clean-base targeted run passed them, and the final full integrated run passed both. Their timing sensitivity has not been fixed or reclassified as a feature regression.

The existing legacy-store `after_copy` crash test deterministically failed on clean `4e4b387`: its `shutil.copytree` monkeypatch recursively killed the child after an arbitrary nested directory, before the asserted complete jobs-tree copy. The test-only hook now targets completion of the top-level jobs copy, preserving SIGKILL/recovery/orphan assertions without changing production legacy migration code. All 18 existing store migration tests passed afterward.

## Real HTTP/browser acceptance

The runner started a fixture-only HTTP process on loopback, used actual Chromium and 400 synthetic timed source segments, stopped that process, started a new one against the same database, and opened a fresh browser for persisted Undo/Redo/deletion. It did not run an ASR/diarization worker. **16 checks passed, zero page errors, zero external requests observed by the routed first browser context.** Both result JSON files were aggregated programmatically; `contractStub` is false.

Covered workflows:

- Entire recording default; one preview; Cancel leaves revision/copies unchanged; one Apply all produces nine blocks while retaining all 400 ordered source IDs and words.
- Whole grouping is one history operation; Undo restores source partitions and Redo restores exact saved grouping.
- Manual source-boundary split survives regrouping; stable repeat grouping adds no revision/history; selection preview uses an explicit contiguous range.
- Paused playback/search reveal source rows inside groups, including a single-result search unchanged while grouping is applied. Internal silence is not highlighted as speech.
- Stale second-tab save returns a conflict and retains its visible draft; explicit discard reloads current saved state.
- Exact manual text Undo/Redo; a new edit after Undo invalidates Redo.
- Current grouped JSON v2, source/original JSON v1, readable TXT and automatic saved copies; SRT cue times unchanged and immutable published JSON bytes unchanged. Backend tests separately cover VTT timing and all copy formats.
- Desktop 1440 px, tablet 760 px and narrow 390 px: no horizontal overflow; usable one-shot preview/cancel. Desktop/narrow screenshots were also visually inspected.
- Draft gating and disconnected-save failure preserve visible text without publishing it.
- Fresh HTTP process/browser retain exact saved text/history; undoing the linear stack restores original grouping and redoing restores exact saved text, partitions and manual boundaries.
- Explicit recording deletion removes its directory and history endpoint ownership; a synthetic shared-model ownership sentinel remains unchanged.

Synthetic local evidence: `/opt/data/profiles/hefajstos/cache/scratch/local-scribe-grouping-pz0m6hgg/` (`browser-grouping-results.json`, `browser-restart-results.json`, screenshots and pre-restart snapshot). Scratch artifacts are not permanent project data; rerun the committed scripts to regenerate evidence.

## Test-first and review evidence

Backend vertical cycles demonstrated missing history/grouping/API/exports before implementing them. The parent independently read the backend and ran the integrated suite. UI browser RED cycles demonstrated missing preview, Apply/history controls, grouped reading view and export selectors before adding them. An independent frontend reviewer found that unchanged search/playback IDs could stay hidden after grouping; the parent reproduced actual Chromium `false !== true`, a separate fix context changed the source-partition reveal dependencies, and both the contract and real-backend browser flows passed afterward. The source partition signature excludes draft text, preserving native textarea editing/undo behavior.

Early `UI_CONTRACT_FIXTURE=1` runs explicitly stubbed grouping HTTP responses to test the UI in isolation. They are not counted as backend/restart acceptance. One early Chromium renderer crash occurred during an isolated UI run; a diagnostic rerun showed no cgroup OOM events and passed, as did the complete real-backend run. The cause of that single crash was not established.

## Limits and recovery

- No access to the owner's Mac, private recordings or live app store; no new real-model, GPU, ASR-quality or OS-network-denied evidence. Existing release exceptions remain unchanged.
- Grouping is deterministic and conservative, not speaker correction or subtitle realignment. Defaults are product tuning settings, not measured quality thresholds.
- Existing saved edits become the initial history checkpoint; overwritten pre-upgrade history is unrecoverable. Back up the complete stopped data directory before upgrading. A failed history migration rolls back its new schema/backfill instead of resetting the store.
- CLI restore still reads v1 JSON: export **Source segments** or **Original ASR**, not grouped v2, for that workflow.
- Current Chromium is exercised. Safari/Firefox and physical mobile devices have not been exercised; the legacy textarea height fallback on expanding grouped sources remains outside this browser evidence.
- Local-copy write errors do not roll back committed edits; retry file generation or restart. Tests cover failure and repair for grouping, split, Undo and Redo.
- No PR merge, issue closure, release or deployment is performed by this task. Remote PR/check status must be read separately; local tests are not CI.

# Reversible local proofreading (#17–#19)

This continuation stacks on PR #20 without merging it. Live acceptance comes from issues #14 and #17–#19. Grouping remains optional; the existing history owns accepted batches.

## Workflow and boundaries

Configure an explicitly loaded LM Studio instance on literal HTTP loopback. Preview either the entire saved recording or one saved source/grouped block. Save/discard visible manual drafts first. An optional recording glossary is retained with the latest task; it protects spellings and is never an instruction channel. Review server-computed inline differences, reject individual/selected/all suggestions, or accept an individual/selected batch as one persistent Undo operation. Uncertain phrases require listening and manual editing. After accepting a batch, remaining suggestions require a fresh preview of the current revision.

Pending suggestions never modify saved exports. Original source text, IDs, speakers, times and grouping/manual split boundaries remain immutable. No grammar/style repair, translation, filler deletion, summaries, speaker changes or ASR replacement. Small spelling changes are guarded heuristically; human review remains necessary. This is not a factual-correctness guarantee.

## Runtime and persistence

A separate `proofreading_tasks` table (migration 6, recording-owned foreign key) stores source revision/attempt, queued/running/cancelling/terminal state, snapshot, glossary, validated suggestions and model/prompt/settings/token/time provenance. The existing supervised worker runs one correction task or ASR/diarization pipeline at a time. A cross-store process lock also serializes cooperating LocalScribe versions on the same Mac. Older running versions do not participate; stop their active processing before validation or upgrading.

Inference runs outside SQLite transactions and HTTP handlers. Each chunk uses at most eight targets, a conservative UTF-8 byte budget and read-only neighbors. Oversized segments/glossaries fail with a smaller-selection instruction. No tools, MCP, redirects, proxies, cloud fallback, downloads or browser model credentials are used. Readiness requires a loaded instance with 8192+ context and reasoning-off capability. Responses require schema-valid JSON, complete non-thinking output, exact old values, known unique target IDs and conservative protected-token checks. Invalid output fails the entire preview, preserving saved text.

Cancel marks the task and drains the current bounded model request before releasing heavy-work ownership; no partial preview is published. Restart marks running tasks interrupted. A transport failure or process crash during generation leaves a durable shared barrier: no new heavy work starts until LocalScribe observes the configured LM Studio instance unloaded. Never infer GPU quiescence from browser disconnection; never unload unrelated sessions. A normal cancelled response can release the barrier without unloading. Deleting a recording cascades its task/history rows; an already in-flight model response still drains without publishing.

## HTTP contract

All mutations retain the existing session-token/Origin protection.

- `GET /api/proofreading/readiness`: loaded-model/setup and heavy-work recovery information.
- `GET /api/jobs/{id}/proofreading`: latest durable task, suggestions, glossary and stale flag.
- `POST /api/jobs/{id}/proofreading`: `{expectedRevision, segmentIds?, glossary?}`; omitted IDs mean the entire recording. Explicit IDs must be a contiguous source range. Returns 202.
- `POST .../proofreading/{task}/cancel`: request cancellation.
- `POST .../proofreading/{task}/apply` or `/reject`: `{expectedRevision, segmentIds}`. Apply verifies attempt/revision and exact saved old values transactionally, records one operation, and refreshes saved copies. Rejection affects pending suggestions only.

No changes to original/current export selection or source cue timings. File-copy errors retain their existing retry/repair behavior. Pre-upgrade overwritten edits remain unrecoverable; never test upgrades against the personal store.

Current JSON provenance also records accepted proofreading batches (model/settings/prompt, accepted revision/attempt and target IDs). The provenance snapshot is part of the same reversible history state. It records accepted AI history, not a guarantee that every current word is exclusively AI-produced; later manual edits remain possible. Original JSON preserves only the immutable source provenance.

# Transcript history and deterministic grouping (#15, #16)

Implementation scope approved by Marcin: history + model-free grouping and one review PR. No merge, issue closure, AI runtime, model downloads or Mac access.

## Public seams and acceptance

Test at the existing Jobs service, HTTP API/export, and real browser boundaries. Preserve original published JSON/media, immutable IDs/times, security, explicit saves, local file repair and deletion ownership. Migrate existing saved edits as the initial checkpoint (no reconstruction of overwritten history). History is linear and persistent; undo/redo write new monotonically increasing revisions, and new operations invalidate redo. Mutations use a revision check and verify stored before/after values transactionally; no-op grouping creates no operation/revision. A batch is one undo unit.

## Shared HTTP/UI contract

Existing PATCH transcript (`revision`, `texts`, `names`) remains compatible and records a manual-save operation. New mutations use `expectedRevision`.

- `GET /api/jobs/{id}/history` -> `{revision, canUndo, canRedo, operations: [{id, type, createdAt, baseRevision, resultRevision, applied}]}`. Operations describe the current linear stack (redo entries retained until branching). Types: `manual_save`, `grouping`, `split`. Provenance and exact before/after snapshots stay persisted server-side; no need to expose all text in the history list.
- `POST /api/jobs/{id}/history/undo` or `/redo`, body `{expectedRevision}` -> saved Transcript.
- `POST /api/jobs/{id}/grouping/preview`, body `{expectedRevision, segmentIds?: string[]}` -> `{revision, beforeCount, afterCount, changed, blocks: Block[]}`. Omitted segmentIds means entire recording. Selection must be a nonempty contiguous ordered source range, never gather across interjections. Preview is stateless and never alters saved exports/history.
- `POST /api/jobs/{id}/grouping/apply`, same body -> saved Transcript. Server deterministically recomputes the preview inside the revision guard; it never trusts client-provided blocks.
- `POST /api/jobs/{id}/grouping/split`, body `{expectedRevision, beforeSegmentId}` -> saved Transcript. Split only inside an existing saved block; persist the explicit barrier across repeat grouping. Undo can reverse it. Resetting manual splits is not part of this first UI.
- Saved Transcript retains v1 source segments and adds `grouping: {blocks: Block[], manualSplits: string[]}`. An ungrouped transcript returns singleton blocks (or frontend falls back to singletons for older fixtures). Block: `{id, segmentIds: string[], start, end, speakerId: string | null, text}`. Text reflects current saved source texts, boundary whitespace only. IDs derived from first segment, not mutable display names.
- `GET .../export?format=...&source=current|original&layout=grouped|segmented`. Defaults current/grouped. Original uses immutable source text/names; segmented renders source cues. SRT/VTT always retain original source cue boundaries/times regardless of layout. Current grouped JSON uses an explicitly versioned v2 envelope/extension; original or segmented JSON offers v1-compatible schema. Automatic copies use current saved grouping. No pending previews in exports.

## Grouping rules

Only adjacent same known stable speaker IDs, no overlap/unknown attribution, no backwards or overlapping timing. Defaults: gap <= 2 s; block duration <= 60 s; soft character cap 1200 (an individual source segment is never truncated). Also treat source word/turn overlap ambiguity as a barrier where present. Preserve exact source order and lexical content, normalize joining whitespace only. Do not merge across explicit manual split boundaries. Selection preserves grouping outside its boundaries without losing/duplicating segments.

## Browser/UI

Extend the inspector with Transcript tools (collapsible narrow-screen), Entire recording default, Selection via start/end source segment controls, one Preview grouping with counts and browsable groups, Apply all/Cancel. Require save/discard of manual drafts before any history/grouping mutation. Saved grouped view shows readable blocks, expandable editable original segments and split-before controls. Seeking/highlighting/search reveal source segment within its block and never treat internal silence as speech. History has Undo/Redo and persisted operation list. Exports distinguish original/current and grouped/segmented. Existing textareas keep native keyboard undo.

## Evidence

Hundreds of synthetic segments in one preview/apply; barriers and lexical/ID preservation; restart undo/redo; redo invalidation; stale tab draft retention; originals unchanged; unchanged subtitle timing; saved-copy failure/repair; ownership deletion; desktop/narrow actual Chromium. Run make check/build and review. This is software fixture evidence, not ASR accuracy, Mac or real-model evidence.

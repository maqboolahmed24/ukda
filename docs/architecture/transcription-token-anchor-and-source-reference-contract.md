# Transcription Token Anchor And Source Reference Contract

Scope: Canonical token-anchor materialization for transcription outputs, including deterministic token IDs, geometry persistence, and source provenance for line and rescue flows.

## Canonical Store

`token_transcription_results` is the only canonical token-anchor table for Phase 4 engine outputs.

Required fields:
- `run_id`
- `page_id`
- `line_id` (nullable)
- `token_id`
- `token_index`
- `token_text`
- `token_confidence`
- `bbox_json` (nullable)
- `polygon_json` (nullable)
- `source_kind` (`LINE | RESCUE_CANDIDATE | PAGE_WINDOW`)
- `source_ref_id`
- `projection_basis` (`ENGINE_OUTPUT | REVIEW_CORRECTED`)
- `created_at`
- `updated_at`

## Deterministic Token IDs

Token IDs are deterministic for a persisted run/page output and are generated from a stable seed that includes:
- run/page identity
- source provenance (`source_kind`, `source_ref_id`)
- canonical line link (or null)
- token order (`token_index`)
- token span and token text

Implications:
- IDs are stable and deep-link-safe for the same persisted output.
- IDs are not ephemeral client IDs.
- IDs are unique within a run/page token set.

## Geometry Contract

Token geometry is normalized and validated as page-bounded data:
- `bbox_json` uses `x`, `y`, `width`, `height`
- `polygon_json` uses `points: [{x, y}, ...]`
- geometry is bounded to page width/height and must remain valid

Line-backed token geometry is derived from canonical layout PAGE-XML line coords when available. Rescue-backed geometry is derived from accepted rescue candidate geometry.

## Source-Provenance Contract

### Line-backed anchors
- `source_kind = LINE`
- `source_ref_id` must match a canonical line ID
- `line_id` must match `source_ref_id`

### Rescue-backed anchors
- `source_kind = RESCUE_CANDIDATE` or `PAGE_WINDOW`
- `source_ref_id` must match an accepted/resolved rescue candidate ID
- `line_id` is optional and only populated when a canonical line link exists
- rescue-only text must not be forced onto fake line IDs

### Source-reference safety
- token `source_ref_id` values are internal anchor references
- raw storage paths and path-like values are rejected

## Workspace/API Surfaces

Workspace and downstream readers consume:
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/lines`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/tokens`

These payloads are the canonical source for line/token selection and provenance context; clients do not reverse-engineer anchors from raw PAGE-XML.

## Non-goals

This contract does not define:
- manual correction UI behavior
- normalized transcript layer lifecycle
- privacy decisioning rules
- search indexing internals

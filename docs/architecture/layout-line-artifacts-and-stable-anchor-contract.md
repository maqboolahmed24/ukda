# Layout Line Artifacts And Stable Anchor Contract

> Status: Active (Prompt 43)
> Scope: Stable line/region anchors, canonical layout-derived crops/thumbnails/context windows, and line-artifact API ownership

## Stable Identity Rules

- Region and line IDs are canonical layout IDs shared across PAGE-XML and overlay JSON for the same run/page result.
- The segmentation pipeline and canonical normalization keep IDs deterministic for identical input and serialization.
- Downstream transcription and rescue flows must treat these line/region IDs as the only supported layout anchors.

## Canonical Artifact Storage Layout

All layout line artifacts are controlled-derived objects:

- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/thumbnail.png`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/lines/{line_id}.png`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/regions/{region_id}.png` (optional when region crop is valid)
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/context/{line_id}.json`

Canonical PAGE-XML and overlay keys remain:

- `.../page/{page_index}.xml`
- `.../page/{page_index}.json`

## Canonical Table Ownership

`layout_line_artifacts` is authoritative for downstream lookup of layout-derived line artifacts:

- `run_id`
- `page_id`
- `line_id`
- `region_id` (nullable)
- `line_crop_key`
- `region_crop_key` (nullable)
- `page_thumbnail_key`
- `context_window_json_key`
- `artifacts_sha256`

Write behavior:

- replace-per-page within the same run/page is deterministic and idempotent
- reruns write a new artifact set under the new `run_id`
- historical run artifacts are never overwritten by a newer run

## Artifact Materialization Rules

- Line crops are generated only for valid canonical line anchors.
- Region crops are optional and generated only when region bounds are valid.
- Page thumbnails are deterministic, bounded, and run-scoped.
- Context-window manifests keep stable IDs and neighbor references without leaking raw storage internals.
- `artifacts_sha256` is derived from persisted line-crop, region-crop (or empty), thumbnail, and context-window bytes.

## API Contract

Metadata route:

- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/lines/{lineId}/artifacts`

Returns run/page/line anchor metadata and same-origin access paths:

- `lineCropPath`
- `regionCropPath` (nullable)
- `pageThumbnailPath`
- `contextWindowPath`
- `contextWindow` payload

Same-origin asset routes:

- `GET /.../lines/{lineId}/crop?variant=line|region`
- `GET /.../pages/{pageId}/thumbnail`
- `GET /.../lines/{lineId}/context`

No raw object keys are exposed by this API contract.

## Downstream Ownership Boundary

- Phase 3 owns line-artifact generation and persistence.
- Phase 4 consumes `layout_line_artifacts` for stable line-targeted transcription context.
- This contract does not implement transcript generation, token anchors, or rescue-candidate lifecycle.

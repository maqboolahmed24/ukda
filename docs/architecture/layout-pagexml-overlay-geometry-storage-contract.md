# Layout PAGE-XML, Overlay, And Geometry Contract

> Status: Active (Prompt 40)
> Scope: Canonical PAGE-XML serialization, overlay cache contract, geometry normalization, and controlled storage/access rules

## Canonical Source Of Truth

- PAGE-XML is the canonical structural artefact for layout output.
- Overlay JSON is a derived rendering cache for browser workspace performance.
- Overlay payloads must remain derivable from canonical PAGE-XML-backed layout structure.

## Canonical Overlay Contract

`GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/overlay` returns:

- `schemaVersion`
- `runId`
- `pageId`
- `pageIndex`
- `page.width`, `page.height`
- `elements[]` where each element has:
  - `id`
  - `type` (`REGION` or `LINE`)
  - `parentId`
  - `polygon`
  - region-only: `childIds`, optional `regionType`
  - line-only: optional `baseline`
- `readingOrder[]` (`fromId`, `toId`)

Contract guarantees:

- stable element IDs and parent/child references
- deterministic polygon simplification/canonicalization
- no ad hoc viewer-only geometry schema

## Geometry Validation And Normalization Rules

- polygons and baselines must contain finite numeric coordinates (no NaN/Inf)
- coordinates must stay within page bounds
- geometry cannot be empty after normalization
- duplicate and collinear points are collapsed deterministically
- invalid payloads fail closed (validation error), not silently accepted

## Canonical Storage Layout

Layout output artefacts are controlled-derived only:

- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}.xml`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}.json`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/manifest.json`

`page_layout_results` remains authoritative for page-level output pointers and hashes:

- `page_xml_key`
- `overlay_json_key`
- `page_xml_sha256`
- `overlay_json_sha256`

Manifest payload includes page mappings and hashes:

- `pageId`
- `pageIndex`
- `pageXmlKey`
- `overlayJsonKey`
- `pageXmlSha256`
- `overlayJsonSha256`

## Controlled Artefact Access

- `GET /.../overlay` returns canonical overlay JSON through authenticated API access.
- `GET /.../pagexml` returns canonical PAGE-XML through authenticated API access.
- Raw/public storage URLs are never returned to the browser.
- Responses include private cache headers and ETag support for revalidation.

Required audit events:

- `LAYOUT_OVERLAY_ACCESSED`
- `LAYOUT_PAGEXML_ACCESSED`

## Related Contract

Stable line/region anchors plus layout thumbnail/crop/context artefacts are defined in:

- `docs/architecture/layout-line-artifacts-and-stable-anchor-contract.md`

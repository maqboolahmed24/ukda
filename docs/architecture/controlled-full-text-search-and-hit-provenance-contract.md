# Controlled Full-Text Search And Hit Provenance Contract

Status: Implemented in Prompt 89
Scope: Canonical controlled search query API, active-index-only result serving, token-anchor/fallback hit semantics, and deterministic workspace handoff.

## Canonical API Surface

- `GET /projects/{projectId}/search`
- `POST /projects/{projectId}/search/{searchDocumentId}/open`

No parallel project search backend or alternate hit payload shape is allowed.

## Query Contract

`GET /projects/{projectId}/search` accepts:

- `q` (required, trimmed, 1-600 chars)
- `documentId` (optional)
- `runId` (optional)
- `pageNumber` (optional, `>= 1`)
- `cursor` (optional, `>= 0`, default `0`)
- `limit` (required by contract, bounded in implementation to `1..100`, default `25`)

Search responses are deterministic for a stable index generation and filter set:

- ordered by `page_number`, `document_id`, `run_id`, then row `id`
- cursor pagination uses `nextCursor`
- missing `cursor` is equivalent to `cursor=0`

## Active Index Isolation

Search reads only from `project_index_projections.active_search_index_id`.

- no implicit fallback to "latest successful"
- no cross-generation result mixing
- no cross-project row exposure
- when no active search index exists, search and open fail closed (`409`)

## Search Document Contract

`search_documents` is the canonical search-hit materialization for one `search_index_id` generation.

Required columns used by Prompt 89:

- `search_index_id`
- `document_id`
- `run_id`
- `page_id`
- `line_id`
- `token_id`
- `source_kind` (`LINE | RESCUE_CANDIDATE | PAGE_WINDOW`)
- `source_ref_id`
- `page_number`
- `match_span_json`
- `token_geometry_json`
- `search_text`
- `search_metadata_json`

Rows are append-only per generation and preserve provenance to page/line/token/source references.

## Hit Payload Semantics

Each search hit returns:

- `searchDocumentId`
- `searchIndexId`
- `documentId`
- `runId`
- `pageId`
- `pageNumber`
- `lineId` (nullable)
- `tokenId` (nullable)
- `sourceKind`
- `sourceRefId`
- `matchSpanJson` (nullable)
- `tokenGeometryJson` (nullable)
- `searchText`
- `searchMetadataJson`

Provenance rules:

- token-anchored hits carry `tokenId` and token geometry when available
- rescue/page-window hits carry exact source provenance (`sourceKind`, `sourceRefId`)
- non-token highlighting uses exact stored `matchSpanJson`; no approximate/guessed context is fabricated

## Workspace Handoff Contract

`POST /projects/{projectId}/search/{searchDocumentId}/open` resolves the hit in the active generation and returns `workspacePath`:

`/projects/:projectId/documents/:documentId/transcription/workspace?page={pageNumber}&runId={runId}[&lineId={lineId}][&tokenId={tokenId}][&sourceKind={sourceKind}][&sourceRefId={sourceRefId}]`

Mapping is deterministic and lossless for available fields only:

- `line_id -> lineId`
- `token_id -> tokenId`
- `source_kind -> sourceKind`
- `source_ref_id -> sourceRefId`

Missing optional provenance fields are omitted, not synthesized.

## RBAC And Safety

Project-scoped search read/open is allowed for:

- `PROJECT_LEAD`
- `RESEARCHER`
- `REVIEWER`
- `ADMIN`

`AUDITOR` does not use the interactive project search surface and is denied by project-read role gates.

Error payloads remain sanitized and do not expose raw transcript content.

## Audit Coverage

Opening a hit emits:

- `SEARCH_RESULT_OPENED`

Event metadata includes route and selected hit provenance identifiers (`search_index_id`, document/run/page context, source refs).

## Prompt 90 Boundary

Prompt 89 stabilizes search contracts and handoff behavior.
Prompt 90 may polish:

- zero-state and query ergonomics
- result-card presentation and highlighting UX
- jump-to-context interaction polish

Prompt 90 must not introduce contract churn for the Prompt 89 API or hit schema.

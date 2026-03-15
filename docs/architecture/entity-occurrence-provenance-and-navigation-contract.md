# Entity Occurrence Provenance And Navigation Contract

Status: Implemented in Prompt 91  
Scope: Entity occurrence semantics, span-basis interpretation, and deep-link-safe transcription navigation.

## Provenance Model

Entity occurrences are evidence links, not free text snippets.

Each occurrence preserves:

- document/run/page identity
- optional line and token anchors
- source provenance (`source_kind`, `source_ref_id`)
- optional exact span offsets (`occurrence_span_json`)
- explicit span basis metadata (`occurrence_span_basis_kind`, `occurrence_span_basis_ref`)

## Span-Basis Semantics

`occurrence_span_json` is interpreted only through basis fields:

- `LINE_TEXT`
  - basis reference must equal `line_id`
  - span offsets are line-text relative
- `PAGE_WINDOW_TEXT`
  - source must be `PAGE_WINDOW`
  - basis reference must equal `source_ref_id`
  - span offsets are page-window-text relative
- `NONE`
  - `occurrence_span_json` must be null
  - no offset interpretation is attempted

Client code must never guess basis from path shape or infer line-relative offsets when basis says otherwise.

## Workspace Navigation Contract

Occurrence rows carry enough provenance to reopen transcription context at:

`/projects/:projectId/documents/:documentId/transcription/workspace?page={pageNumber}&runId={runId}[&lineId={lineId}][&tokenId={tokenId}][&sourceKind={sourceKind}][&sourceRefId={sourceRefId}]`

Rules:

- include `lineId`, `tokenId`, `sourceKind`, `sourceRefId` only when present
- never drop richer provenance in favor of line-only fallback
- navigation stays generation-safe because entity reads are scoped to one active `entityIndexId`

## API Payload Guarantees

`GET /projects/{projectId}/entities/{entityId}/occurrences` returns:

- one `entityIndexId` for the whole page
- occurrences only from that same generation
- complete provenance fields and a deterministic `workspacePath`

No route mixes occurrences from superseded entity generations.

## Regression Coverage Expectations

Prompt 91 regression tests must keep validating:

- list/detail/occurrence reads all use the same active `entityIndexId`
- occurrence links preserve token/source context
- page-window spans are interpreted only via persisted basis metadata
- auditor role remains blocked from interactive project entity discovery

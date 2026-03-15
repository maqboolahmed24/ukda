# Controlled Entity Index And Lineage Contract

Status: Implemented in Prompt 91  
Scope: Phase 10 Iteration 10.2 controlled entity product, active-generation query routes, and activation gates.

## Canonical Product Boundary

The controlled entity index is a first-class internal data product. It is not a side effect of search indexing.

Prompt 91 owns:

- canonical `controlled_entities` and `entity_occurrences`
- active-index-only entity list/detail/occurrence APIs
- entity activation gates for provenance/canonicalization/coverage
- occurrence links back to transcription workspace with source provenance

Out of scope here:

- safeguarded derivative entity products (Prompt 92)
- public/external entity APIs
- graph expansion workflows

## Canonical Tables

### `controlled_entities`

- `id`
- `project_id`
- `entity_index_id`
- `entity_type` (`PERSON | PLACE | ORGANISATION | DATE`)
- `display_value`
- `canonical_value`
- `confidence_summary_json`
- `created_at`

Rows are scoped to one `entity_index_id` generation and remain append-only by generation lineage.

### `entity_occurrences`

- `id`
- `entity_index_id`
- `entity_id`
- `document_id`
- `run_id`
- `page_id`
- `line_id` (nullable)
- `token_id` (nullable)
- `source_kind` (`LINE | RESCUE_CANDIDATE | PAGE_WINDOW`)
- `source_ref_id`
- `page_number`
- `confidence`
- `occurrence_span_json` (nullable)
- `occurrence_span_basis_kind` (`LINE_TEXT | PAGE_WINDOW_TEXT | NONE`)
- `occurrence_span_basis_ref` (nullable)
- `token_geometry_json` (nullable)
- `created_at`

Occurrences are always tied to one entity generation (`entity_index_id`) and never mixed across superseded builds.

## Active Index Read Contract

Entity read APIs resolve only through `project_index_projections.active_entity_index_id`.

- no fallback to “latest succeeded”
- no cross-generation joins
- when active pointer is null, routes fail closed with conflict

## API Surface

- `GET /projects/{projectId}/entities?q={q}&entityType={entityType}&cursor={cursor}&limit={limit}`
- `GET /projects/{projectId}/entities/{entityId}`
- `GET /projects/{projectId}/entities/{entityId}/occurrences?cursor={cursor}&limit={limit}`

Each response includes `entityIndexId` so operators can tie reads and bug reports back to one active generation.

## Activation Gates

`POST /projects/{projectId}/entity-indexes/{indexId}/activate` is rejected unless all pass:

1. Canonicalization validation:
   - supported entity type
   - non-empty display value
   - stored canonical value equals canonicalizer output for `(entity_type, display_value)`

2. Occurrence provenance completeness:
   - required source/document/run/page references present
   - source kind and span-basis combinations are coherent
   - span payloads are only accepted when basis metadata is explicit and valid

3. Eligible-input coverage:
   - uses snapshot counters when provided (`eligibleInputCount`/`coveredInputCount`, with snake-case aliases)
   - blocks activation when covered < eligible
   - preserves no-input snapshots and empty generations when eligibility is explicitly zero or absent

## RBAC

Project entity workspace read is allowed for:

- `PROJECT_LEAD`
- `RESEARCHER`
- `REVIEWER`
- `ADMIN`

`AUDITOR` does not use project-scoped interactive entity discovery routes.

## Audit Events

Prompt 91 adds:

- `ENTITY_LIST_VIEWED`
- `ENTITY_DETAIL_VIEWED`
- `ENTITY_OCCURRENCES_VIEWED`

Index lifecycle events from Prompt 88 continue unchanged.

## Prompt 92 Hand-off

Prompt 92 builds safeguarded derivative indexes on top of this contract.
It must not duplicate or fork `controlled_entities` / `entity_occurrences`, and it must preserve active-generation lineage semantics.

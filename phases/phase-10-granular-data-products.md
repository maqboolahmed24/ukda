# Phase 10: Granular Data Products (Search + Controlled Entity Index + Safeguarded Derivatives) - The Discovery Engine

> Status: ACTIVE
> Web Root: /web
> Active Phase Ceiling: 11
> Execution Policy: Phase 0 through Phase 11 are ACTIVE for this prompt program.
> Web Translation Overlay (ACTIVE): preserve existing workflow intent and phase semantics while translating any legacy desktop or WinUI terms into equivalent browser-native routes, layouts, and interaction patterns under /web.

## Phase Objective
Move from static document outputs to queryable Controlled discovery products and policy-controlled safeguarded derivative indexes.

## Entry Criteria
Start Phase 10 only when all are true:
- transcription, privacy, and provenance artefacts are stable enough to index reproducibly
- tier boundaries for Controlled and safeguarded outputs remain enforced
- governance-ready or policy-pinned upstream outputs exist for the safeguarded derivative families this phase will index

## Scope Boundary
Phase 10 creates discovery products and derived indexes.

Out of scope for this phase:
- external release approval outside the Phase 8 gateway
- production hardening and pen-test readiness activities that belong to Phase 11

## Phase 10 Non-Negotiables
- Secure web application is the active delivery target: preserve phase behavior and governance contracts while implementing browser-native interaction, routing, and layout patterns from first principles (no desktop-mechanics carryover).
- All workspace and page surfaces inherit the canonical `Obsidian Folio` experience contract (dark-first Fluent 2 tokens, app-window adaptive states, single-fold defaults, keyboard-first accessibility); see `ui-premium-dark-blueprint-obsidian-folio.md`.
- Recall-first behavior from `UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` is normative for token-anchored search provenance and geometry fallback.
1. Search and indexing must respect the same access boundaries as source artefacts.
2. Entity extraction and indexing are versioned data products, not hidden side effects.
3. Safeguarded derivatives cannot expose raw identifier fields or reconstructable joins.
4. Search hits must preserve provenance back to page, line, and run.
5. Search highlighting must resolve to token-level anchors when available.

## Iteration Model
Build Phase 10 in five iterations (`10.0` to `10.4`). Each iteration must improve discoverability without weakening disclosure controls.

## Iteration 10.0: Indexing Model + Rebuild Pipeline

### Goal
Create explicit index products for transcript, entity, and derivative data.

### Backend Work
- versioned `search_indexes`, `entity_indexes`, and `derivative_indexes`
- rebuild and rollback support
- provenance links from index documents back to source runs

Tables:
- `search_indexes`
  - `id`
  - `project_id`
  - `version`
  - `source_snapshot_json`
  - `source_snapshot_sha256`
  - `rebuild_dedupe_key`
  - `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
  - `supersedes_index_id` (nullable)
  - `superseded_by_index_id` (nullable)
  - `failure_reason` (nullable)
  - `created_by`
  - `created_at`
  - `started_at`
  - `finished_at`
  - `canceled_by` (nullable)
  - `canceled_at` (nullable)
  - `activated_by` (nullable)
  - `activated_at` (nullable)
- `entity_indexes`
  - same lifecycle fields, `source_snapshot_json`, `source_snapshot_sha256`, `rebuild_dedupe_key`, `failure_reason`, and activation metadata as `search_indexes`
- `derivative_indexes`
  - same lifecycle fields, `source_snapshot_json`, `source_snapshot_sha256`, `rebuild_dedupe_key`, `failure_reason`, and activation metadata as `search_indexes`
- `search_documents`
  - `id`
  - `search_index_id`
  - `document_id`
  - `run_id`
  - `page_id`
  - `line_id` (nullable when only page-level anchoring exists)
  - `token_id` (nullable when only line/page-level anchoring exists)
  - `source_kind` (`LINE | RESCUE_CANDIDATE | PAGE_WINDOW`)
  - `source_ref_id`
  - `page_number`
  - `match_span_json` (nullable; exact character offsets/excerpt for non-token fallback highlighting)
  - `token_geometry_json` (nullable; bbox/polygon payload when available)
  - `search_text`
  - `search_metadata_json`
  - `created_at`
- `derivative_index_rows`
  - `id`
  - `derivative_index_id`
  - `derivative_snapshot_id`
  - `derivative_kind`
  - `source_snapshot_json`
  - `display_payload_json`
  - `suppressed_fields_json`
  - `created_at`
- `project_index_projections`
  - `project_id`
  - `active_search_index_id` (nullable)
  - `active_entity_index_id` (nullable)
  - `active_derivative_index_id` (nullable)
  - `updated_at`
- activate actions update `project_index_projections`, while failed rebuilds leave the active pointers unchanged
- failed rebuilds never replace the currently active index pointer
- project search, entity, and derivative read surfaces use `project_index_projections` as the sole source of current-generation truth; they must not infer "latest successful" from historical index rows
- rebuild requests compute a deterministic `rebuild_dedupe_key` from `(project_id, index_kind, source_snapshot_sha256, normalized build parameters)`; when an equivalent active, queued, running, or successful generation already exists and `force` is not set, the rebuild endpoints return that existing generation instead of creating a duplicate competing version
- all three cancel endpoints (`search-indexes/{indexId}/cancel`, `entity-indexes/{indexId}/cancel`, and `derivative-indexes/{indexId}/cancel`) are allowed only while the targeted index row is `QUEUED` or `RUNNING`
- queued index generations transition directly to `CANCELED`, while running generations transition to `CANCELED` only through worker-cooperative shutdown; cancel requests against terminal index rows are rejected instead of rewriting historical state
- activating a search index is rejected unless the candidate index row already has `status = SUCCEEDED` and token-anchor validity plus geometry-coverage gates pass for every eligible transcript basis, with explicit fallback markers only for historical line-only runs that are intentionally excluded from token-level search activation
- activating an entity index is rejected unless the candidate index row already has `status = SUCCEEDED` and occurrence-provenance completeness, canonicalization validation, and eligible-input coverage gates pass for the candidate generation
- activating a derivative index is rejected unless the candidate index row already has `status = SUCCEEDED` and suppression-policy checks, anti-join disclosure checks, and snapshot completeness gates pass for every generated derivative row in the candidate generation
- rollback support in v1 is explicit re-activation of an older `SUCCEEDED` generation in the same project through the existing activate endpoint; rollback updates only `project_index_projections` and never mutates or clones the historical index row being restored

APIs:
- `GET /projects/{projectId}/indexes/active`
- `GET /projects/{projectId}/search-indexes`
- `POST /projects/{projectId}/search-indexes/rebuild`
  - accepts optional `force=true`; otherwise deduplicates by `rebuild_dedupe_key`
- `GET /projects/{projectId}/search-indexes/{indexId}`
- `GET /projects/{projectId}/search-indexes/{indexId}/status`
- `POST /projects/{projectId}/search-indexes/{indexId}/cancel`
- `POST /projects/{projectId}/search-indexes/{indexId}/activate`
- `GET /projects/{projectId}/entity-indexes`
- `POST /projects/{projectId}/entity-indexes/rebuild`
  - accepts optional `force=true`; otherwise deduplicates by `rebuild_dedupe_key`
- `GET /projects/{projectId}/entity-indexes/{indexId}`
- `GET /projects/{projectId}/entity-indexes/{indexId}/status`
- `POST /projects/{projectId}/entity-indexes/{indexId}/cancel`
- `POST /projects/{projectId}/entity-indexes/{indexId}/activate`
- `GET /projects/{projectId}/derivative-indexes`
- `POST /projects/{projectId}/derivative-indexes/rebuild`
  - accepts optional `force=true`; otherwise deduplicates by `rebuild_dedupe_key`
- `GET /projects/{projectId}/derivative-indexes/{indexId}`
- `GET /projects/{projectId}/derivative-indexes/{indexId}/status`
- `POST /projects/{projectId}/derivative-indexes/{indexId}/cancel`
- `POST /projects/{projectId}/derivative-indexes/{indexId}/activate`

RBAC:
- project-scoped index metadata is readable by `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, and `ADMIN`
- rebuild and activate actions are restricted to `ADMIN`
- `AUDITOR` does not use project-scoped mutation routes in Iteration 10.0; read-only admin index-quality surfaces arrive in Iteration 10.4

### Web Client Work
- project-scoped index route:
  - `/projects/:projectId/indexes`
  - `/projects/:projectId/indexes/search/:indexId`
  - `/projects/:projectId/indexes/entity/:indexId`
  - `/projects/:projectId/indexes/derivative/:indexId`
- index management surface:
  - shows current search, entity, and derivative index versions from `GET /projects/{projectId}/indexes/active`
  - links into index detail views exposed by the existing project-scoped APIs
  - polls the per-index status endpoints during rebuilds or cancellations
  - keeps rebuild, cancel, and activate controls visible only to `ADMIN`

### Tests and Gates (Iteration 10.0)
#### Integration
- index builds are reproducible from the same input runs
- equivalent rebuild requests without `force=true` return the existing generation identified by `rebuild_dedupe_key`
- failed rebuilds do not replace the active index
- canceled rebuilds leave the previously active index pointer unchanged and surface `CANCELED`
- cancel requests against already terminal index rows are rejected, and running-build cancellation completes only after the index worker records cooperative shutdown
- search, entity, and derivative generations all persist full `source_snapshot_json` plus `source_snapshot_sha256`, so every index lineage can be reconstructed instead of relying on a hash-only shorthand
- search-index activation is blocked when token-anchor validity or geometry-coverage gates fail for eligible transcript inputs
- entity-index activation is blocked when occurrence provenance or canonicalization gates fail
- derivative-index activation is blocked when suppression or anti-join disclosure gates fail
- Audit events emitted:
  - `INDEX_ACTIVE_VIEWED`
  - `SEARCH_INDEX_LIST_VIEWED`
  - `SEARCH_INDEX_DETAIL_VIEWED`
  - `SEARCH_INDEX_STATUS_VIEWED`
  - `SEARCH_INDEX_RUN_CREATED`
  - `SEARCH_INDEX_RUN_STARTED`
  - `SEARCH_INDEX_RUN_FINISHED`
  - `SEARCH_INDEX_RUN_FAILED`
  - `SEARCH_INDEX_RUN_CANCELED`
  - `ENTITY_INDEX_LIST_VIEWED`
  - `ENTITY_INDEX_DETAIL_VIEWED`
  - `ENTITY_INDEX_STATUS_VIEWED`
  - `ENTITY_INDEX_RUN_CREATED`
  - `ENTITY_INDEX_RUN_STARTED`
  - `ENTITY_INDEX_RUN_FINISHED`
  - `ENTITY_INDEX_RUN_FAILED`
  - `ENTITY_INDEX_RUN_CANCELED`
  - `DERIVATIVE_INDEX_LIST_VIEWED`
  - `DERIVATIVE_INDEX_DETAIL_VIEWED`
  - `DERIVATIVE_INDEX_STATUS_VIEWED`
  - `DERIVATIVE_INDEX_RUN_CREATED`
  - `DERIVATIVE_INDEX_RUN_STARTED`
  - `DERIVATIVE_INDEX_RUN_FINISHED`
  - `DERIVATIVE_INDEX_RUN_FAILED`
  - `DERIVATIVE_INDEX_RUN_CANCELED`

### Exit Criteria (Iteration 10.0)
Discovery products have explicit pipelines and versioned index state.

## Iteration 10.1: Controlled Full-Text Search

### Goal
Allow `PROJECT_LEAD`, `RESEARCHER`, and `REVIEWER` to search Controlled transcripts quickly and navigate back to evidence.

### Backend Work
- full-text transcript search API
- page and line provenance in search hits, including `documentId`, `runId`, `pageNumber`, and `lineId` when a hit resolves below page level
- token-level provenance in search hits when available (`token_id` + geometry payload)
- token source provenance in search hits when available (`source_kind` + `source_ref_id`)
- exact fallback match spans in search hits when token provenance is unavailable, using `match_span_json` from `search_documents`
- every search response includes the `search_index_id` that produced the hit set so audits and bug reports can trace results back to a specific active index build
- search results are served from `search_documents` rows attached to the active `search_index_id`; rebuilds and rollbacks must not mix documents across index generations

RBAC:
- `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, and `ADMIN` can search Controlled transcripts for projects they can already access
- `AUDITOR` does not use the interactive project search surface

APIs:
- `GET /projects/{projectId}/search`
  - query shape: `?q={query}&documentId={documentId}&runId={runId}&pageNumber={pageNumber}&cursor={cursor}&limit={limit}`
  - omit any optional filter parameter instead of sending placeholder values
  - filters: `documentId`, `runId`, and `pageNumber`
  - pagination: cursor-based with `limit`
  - response includes the active `search_index_id` and hit rows derived only from `search_documents` under that index
  - hit payload includes `token_id`, `source_kind`, `source_ref_id`, `match_span_json`, and geometry when available, otherwise a documented line/page fallback marker with exact stored span offsets
  - rejects the query when `project_index_projections.active_search_index_id` is null instead of guessing from the newest successful build

### Web Client Work
- `/projects/:projectId/search`
- search UI:
  - query input
  - filters
  - results list
- open result jumps to `/projects/:projectId/documents/:documentId/transcription/workspace?page={pageNumber}&runId={runId}&lineId={lineId}&tokenId={tokenId}&sourceKind={sourceKind}&sourceRefId={sourceRefId}` and highlights the exact token when available, otherwise the exact rescue/page-window source when provenance is present, otherwise the persisted `match_span_json` line/span fallback

### Tests and Gates (Iteration 10.1)
#### Integration
- search hits resolve to correct page and line context
- ACL enforcement blocks unauthorized search access
- search responses identify the active `search_index_id` used for the query
- opening a search hit emits `SEARCH_RESULT_OPENED`
- token-anchored hits resolve to exact token highlight when token IDs are present.
- rescue-candidate and page-window hits reopen the correct source context when `source_kind` and `source_ref_id` are present.
- non-token hits reopen with exact stored `match_span_json` fallback highlighting instead of approximate line-only highlighting

### Exit Criteria (Iteration 10.1)
`PROJECT_LEAD`, `RESEARCHER`, and `REVIEWER` can search Controlled transcripts and jump directly to source context.

## Iteration 10.2: Controlled Entity Index

### Goal
Extract and index entities as a reusable internal product.

### Backend Work
- entity extraction for people, places, organisations, and dates
- entity-to-transcript segment linking
- Controlled-only index backend

Tables:
- `controlled_entities`
  - `id`
  - `project_id`
  - `entity_index_id`
  - `entity_type`
  - `display_value`
  - `canonical_value`
  - `confidence_summary_json`
  - `created_at`
- `entity_occurrences`
  - `id`
  - `entity_index_id`
  - `entity_id`
  - `document_id`
  - `run_id`
  - `page_id`
  - `line_id` (nullable when only page-level anchoring exists)
  - `token_id` (nullable when only line/page-level anchoring exists)
  - `source_kind` (`LINE | RESCUE_CANDIDATE | PAGE_WINDOW`)
  - `source_ref_id`
  - `page_number`
  - `confidence`
  - `occurrence_span_json` (nullable; exact offsets only when a canonical text basis exists)
  - `occurrence_span_basis_kind` (`LINE_TEXT | PAGE_WINDOW_TEXT | NONE`)
  - `occurrence_span_basis_ref` (nullable; uses `line_id` for `LINE_TEXT` and `source_ref_id` for `PAGE_WINDOW_TEXT`)
  - `token_geometry_json` (nullable)
  - `created_at`

APIs:
- `GET /projects/{projectId}/entities?q={q}&entityType={entityType}&cursor={cursor}&limit={limit}`
  - reads only from `project_index_projections.active_entity_index_id`; rejects the request when no active entity index exists and includes `entity_index_id` in the response payload
  - supports server-side search and filter for the entity list by free-text query and entity type
- `GET /projects/{projectId}/entities/{entityId}`
  - returns detail only when the entity belongs to the active `entity_index_id`, and includes that `entity_index_id` in the response payload
- `GET /projects/{projectId}/entities/{entityId}/occurrences?cursor={cursor}&limit={limit}`
  - returns occurrences only from the same active `entity_index_id` and includes that `entity_index_id` in paging metadata

Activation rule:
- `POST /projects/{projectId}/entity-indexes/{indexId}/activate` is rejected unless the candidate index passes occurrence-provenance completeness, canonicalization validation, and eligible-input coverage gates

RBAC:
- `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, and `ADMIN` can read entity lists, detail, and occurrence views for projects they can already access
- `AUDITOR` does not use the project-scoped entity workspace

### Web Client Work
- routes:
  - `/projects/:projectId/entities`
  - `/projects/:projectId/entities/:entityId`
- entity search and filter UI backed by `GET /projects/{projectId}/entities?q={q}&entityType={entityType}&cursor={cursor}&limit={limit}`
- entity detail panel showing source occurrences and confidence
- occurrence deep links reuse the transcription workspace contract with `tokenId`, `sourceKind`, and `sourceRefId` when available so rescue/page-window evidence is not flattened to line-only navigation

### Tests and Gates (Iteration 10.2)
#### Unit
- entity extraction schema validation

#### Integration
- entity occurrence links match transcript segments
- entity and occurrence rows remain scoped to the same `entity_index_id`, so rebuilds and rollbacks do not mix generations
- entity list, detail, and occurrence reads all resolve through the same active `entity_index_id` instead of mixing superseded generations
- entity occurrence links preserve token and source provenance when available and reopen the correct transcription context
- `occurrence_span_json` is interpreted only through the persisted occurrence-span basis fields, so page-window occurrences do not rely on ambiguous line-relative offsets

### Exit Criteria (Iteration 10.2)
Entity discovery is available internally with traceable lineage.

## Iteration 10.3: Safeguarded Derivative Indexes

### Goal
Expose lower-risk derived indexes without leaking raw identifiers.

### Backend Work
- safeguarded derivative generation:
  - redacted entity lists
  - aggregated counts by category, period, or geography
- versioned `derivative_snapshots` keyed to the source candidate or run inputs
- every `derivative_snapshot` is linked to the `derivative_index_id` that materialized it so previews and release candidates can trace back to the exact derivative generation that produced the snapshot
- derivative previews are served from `derivative_index_rows` attached to the requested `derivative_snapshot_id` and that snapshot's own `derivative_index_id`; preview routes must not materialize ad hoc rows outside that generation or silently mix rows from a superseded snapshot
- policy-aware field suppression
- anti-join checks for reconstructable combinations
- any derivative intended for release is frozen as an immutable candidate snapshot and remains internal until Phase 8 approval

Tables:
- `derivative_snapshots`
  - `id`
  - `project_id`
  - `derivative_index_id`
  - `derivative_kind`
  - `source_snapshot_json`
  - `policy_version_ref`
  - `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
  - `supersedes_derivative_snapshot_id` (nullable)
  - `superseded_by_derivative_snapshot_id` (nullable)
  - `storage_key` (nullable until derivative generation succeeds)
  - `snapshot_sha256` (nullable until derivative generation succeeds)
  - `candidate_snapshot_id` (nullable until a Phase 8 candidate snapshot is frozen from this derivative)
  - `created_by`
  - `created_at`
  - `started_at`
  - `finished_at`
  - `failure_reason` (nullable)

APIs:
- `GET /projects/{projectId}/derivatives?scope={scope}`
  - defaults `scope=active` and lists derivative snapshots from `project_index_projections.active_derivative_index_id`
  - `scope=historical` may include unsuperseded successful snapshots from prior derivative-index generations in the same project and includes `derivative_index_id` plus `isActiveGeneration` in each row
  - rejects the request when no active derivative index exists and `scope=active`
- `GET /projects/{projectId}/derivatives/{derivativeId}`
  - returns detail with the snapshot's `derivative_index_id` and current supersession status
- `GET /projects/{projectId}/derivatives/{derivativeId}/status`
- `GET /projects/{projectId}/derivatives/{derivativeId}/preview`
  - serves preview rows only when `derivative_index_rows.derivative_snapshot_id = {derivativeId}` under that snapshot's own `derivative_index_id`, and includes both `derivative_index_id` and `derivative_snapshot_id` in the response payload
- `POST /projects/{projectId}/derivatives/{derivativeId}/candidate-snapshots`
  - freezes the derivative as an immutable Phase 8 candidate snapshot without exposing a direct release path
  - is idempotent for an unsuperseded snapshot: when `candidate_snapshot_id` already exists, return that existing candidate instead of creating a duplicate
  - is rejected unless the derivative snapshot is `SUCCEEDED`, has populated `storage_key` and `snapshot_sha256` values, belongs to a derivative-index generation in the same project, and has not been superseded

Activation rule:
- `POST /projects/{projectId}/derivative-indexes/{indexId}/activate` is rejected unless the candidate derivative generation passes suppression-policy checks, anti-join disclosure checks, and snapshot completeness gates

RBAC:
- derivative preview is readable by `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, and `ADMIN` when the caller already has access to the underlying safeguarded derivative
- candidate-snapshot creation is restricted to `PROJECT_LEAD`, `REVIEWER`, or `ADMIN`

### Web Client Work
- routes:
  - `/projects/:projectId/derivatives`
  - `/projects/:projectId/derivatives/:derivativeId`
  - `/projects/:projectId/derivatives/:derivativeId/status`
  - `/projects/:projectId/derivatives/:derivativeId/preview`
- derivative preview page:
  - shows what can be frozen as a candidate snapshot for Phase 8 review
  - highlights suppressed fields
  - stays internal-only until it passes Phase 8 review
- only `PROJECT_LEAD`, `REVIEWER`, or `ADMIN` can freeze a derivative into a candidate snapshot; `RESEARCHER` can inspect previews but cannot create release candidates

### Tests and Gates (Iteration 10.3)
#### Disclosure Gate
- safeguarded derivatives pass `no raw identifier fields` test
- anti-join checks block reconstructable derivative outputs
- repeated candidate-freeze requests for the same unsuperseded derivative snapshot return the existing `candidate_snapshot_id` instead of creating conflicting Phase 8 candidates
- queued, running, failed, or incomplete derivative snapshots never expose candidate-freeze eligibility or pretend to have final storage/hash fields
- unsuperseded successful historical derivative snapshots remain previewable and freezable even after a newer derivative index becomes active

### Exit Criteria (Iteration 10.3)
Safe derivatives are deliberate products rather than ad hoc export files.

## Iteration 10.4: Quality, Freshness, and Audit Controls

### Goal
Make discovery products trustworthy enough for sustained operational use.

### Backend Work
- query audit logging
- rebuild audit logging
- persisted `search_query_audits` with:
  - `id`
  - `project_id`
  - `actor_user_id`
  - `search_index_id`
  - `query_sha256`
  - `query_text_key`
  - `filters_json`
  - `result_count`
  - `created_at`
- `query_text_key` stores the raw query text in Controlled audit storage for `ADMIN` and read-only `AUDITOR`; ordinary operational events use the normalized `query_sha256`
- audit events:
  - `SEARCH_QUERY_EXECUTED`
  - `SEARCH_RESULT_OPENED`
  - `SEARCH_INDEX_RUN_CREATED`
  - `SEARCH_INDEX_RUN_CANCELED`
  - `SEARCH_INDEX_ACTIVATED`
  - `ENTITY_INDEX_RUN_CREATED`
  - `ENTITY_INDEX_RUN_CANCELED`
  - `ENTITY_INDEX_ACTIVATED`
  - `ENTITY_DETAIL_VIEWED`
  - `ENTITY_OCCURRENCES_VIEWED`
  - `DERIVATIVE_INDEX_RUN_CREATED`
  - `DERIVATIVE_INDEX_RUN_CANCELED`
  - `DERIVATIVE_INDEX_ACTIVATED`
  - `DERIVATIVE_CANDIDATE_SNAPSHOT_CREATED`
  - `DERIVATIVE_DETAIL_VIEWED`
  - `DERIVATIVE_PREVIEW_VIEWED`
  - `INDEX_QUALITY_VIEWED`
- index freshness metrics
- review workflow for extraction-quality spot checks

APIs:
- `GET /admin/index-quality?projectId={projectId}`
- `GET /admin/index-quality/{indexKind}/{indexId}`

RBAC:
- `GET /admin/index-quality?projectId={projectId}` and `GET /admin/index-quality/{indexKind}/{indexId}` are readable by `ADMIN` and read-only `AUDITOR`
- web-route visibility is not sufficient authorization; backend handlers for index-quality reads must enforce the same role checks server-side

### Web Client Work
- freshness indicators
- Admin-only route:
  - `/admin/index-quality?projectId={projectId}`
  - `/admin/index-quality/:indexKind/:indexId`
- `ADMIN` and read-only `AUDITOR` panel for index quality checks

### Tests and Gates (Iteration 10.4)
#### Integration
- freshness metrics update after rebuilds
- query audit events capture actor, normalized query hash, Controlled query-text reference, filters, and target indexes
- derivative preview access emits `DERIVATIVE_PREVIEW_VIEWED`
- derivative freeze actions emit `DERIVATIVE_CANDIDATE_SNAPSHOT_CREATED`
- derivative freeze actions persist `derivative_snapshots.candidate_snapshot_id` once the immutable Phase 8 candidate is created
- derivative rerenders record supersession history through `supersedes_derivative_snapshot_id` and `superseded_by_derivative_snapshot_id`
- derivative preview rows remain scoped to the same `derivative_snapshot_id` and that snapshot's own `derivative_index_id`, so rerenders and rollbacks do not leak mixed-generation preview content
- admin index-quality reads emit `INDEX_QUALITY_VIEWED`
- admin index-quality detail reads emit `INDEX_QUALITY_DETAIL_VIEWED`
- only `ADMIN` can trigger rebuilds; `AUDITOR` remains read-only on index quality surfaces

### Exit Criteria (Iteration 10.4)
Search and derivative products are observable, reviewable, and safe to maintain at scale.

## Handoff to Later Phases
- Phase 11 hardens indexing, search latency, audit pipelines, and derivative-generation operations for production.
- Any releasable derivative continues to flow through Phase 8 as an immutable candidate snapshot rather than through direct derivative endpoints.

## Phase 10 Definition of Done
Move to Phase 11 only when all are true:
1. Controlled full-text and entity search operate on versioned indexes with provenance-rich hits.
2. Safeguarded derivative indexes pass explicit no-leakage and anti-join gates.
3. Search access controls match artefact access controls.
4. Query and rebuild audit trails exist for operational and compliance review.
5. Discovery products are stable enough to justify platform-scale hardening.
6. No safeguarded derivative route or action bypasses Phase 8 for external release.
7. Token-level search anchors plus token source provenance are present for eligible runs, with explicit fallback behavior when only line/page anchors exist.

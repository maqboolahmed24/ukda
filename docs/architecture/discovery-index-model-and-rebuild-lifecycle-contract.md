# Discovery Index Model And Rebuild Lifecycle Contract

## Scope

Phase 10 Prompt 88 introduces one canonical index-management model for project-scoped discovery products.

This contract covers:

- versioned `search_indexes`, `entity_indexes`, and `derivative_indexes`
- immutable source snapshot pinning (`source_snapshot_json` + `source_snapshot_sha256`)
- deterministic rebuild dedupe keys and `force=true` override behavior
- `project_index_projections` as the only active pointer authority
- cancel and activate semantics, including rollback via re-activation

## Canonical Tables

### `search_indexes`, `entity_indexes`, `derivative_indexes`

Each family is append-only lineage with the same lifecycle columns:

- `id`
- `project_id`
- `version`
- `source_snapshot_json`
- `source_snapshot_sha256`
- `build_parameters_json`
- `rebuild_dedupe_key`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `supersedes_index_id`
- `superseded_by_index_id`
- `failure_reason`
- `created_by`, `created_at`
- `started_at`, `finished_at`
- `cancel_requested_by`, `cancel_requested_at`
- `canceled_by`, `canceled_at`
- `activated_by`, `activated_at`

Each family uses per-project monotonic `version` uniqueness and never rewrites historical rows in place.

### `search_documents`

Stores search-ready rows scoped to one `search_index_id`, including:

- token or fallback anchor context (`line_id`, `token_id`, `source_kind`, `source_ref_id`)
- safe highlight payloads (`match_span_json`, `token_geometry_json`)
- immutable search text/materialization metadata

### `derivative_index_rows`

Stores derivative row materialization scoped to one `derivative_index_id`, including:

- source snapshot context
- display payload
- explicitly suppressed fields payload

### `project_index_projections`

Single authoritative active-pointer projection per project:

- `project_id`
- `active_search_index_id`
- `active_entity_index_id`
- `active_derivative_index_id`
- `updated_at`

No read path infers current generation from "latest successful"; active truth is projection-only.

## Rebuild Dedupe Rules

`rebuild_dedupe_key` is deterministic SHA-256 over canonical JSON of:

- `project_id`
- `index_kind`
- `source_snapshot_sha256`
- normalized `build_parameters_json`

Behavior:

- without `force=true`, equivalent `QUEUED`, `RUNNING`, or `SUCCEEDED` generations are reused
- with `force=true`, a fresh append-only generation is created
- failed/canceled generations are not auto-promoted and do not replace active pointers

## Cancel, Activate, And Rollback

### Cancel

- allowed only when status is `QUEUED` or `RUNNING`
- `QUEUED` cancels transition directly to terminal `CANCELED`
- `RUNNING` cancel is request-first (`cancel_requested_*`) and terminal `CANCELED` only after worker-cooperative completion
- cancel on terminal rows is rejected (`409`)

### Activate

- allowed only for `SUCCEEDED` generations
- activation updates only `project_index_projections` and generation activation metadata
- activation does not clone or mutate historical lineage rows

### Rollback

- rollback is explicit re-activation of older `SUCCEEDED` generation via the same activate endpoint
- rollback changes only projection pointers, preserving append-only history

## API Surface

Project-scoped read routes:

- `GET /projects/{projectId}/indexes/active`
- `GET /projects/{projectId}/search-indexes`
- `GET /projects/{projectId}/search-indexes/{indexId}`
- `GET /projects/{projectId}/search-indexes/{indexId}/status`
- equivalent list/detail/status routes for entity and derivative families

Project-scoped mutation routes (ADMIN only):

- `POST /projects/{projectId}/search-indexes/rebuild` (`force=true` optional)
- `POST /projects/{projectId}/search-indexes/{indexId}/cancel`
- `POST /projects/{projectId}/search-indexes/{indexId}/activate`
- equivalent rebuild/cancel/activate routes for entity and derivative families

## RBAC

Read:

- `PROJECT_LEAD`
- `RESEARCHER`
- `REVIEWER`
- `ADMIN`

Mutate:

- `ADMIN` only

`AUDITOR` does not use project-scoped mutation routes in this iteration.

## Audit Coverage

Prompt 88 emits append-only index lifecycle/read events:

- `INDEX_ACTIVE_VIEWED`
- `*_INDEX_LIST_VIEWED`
- `*_INDEX_DETAIL_VIEWED`
- `*_INDEX_STATUS_VIEWED`
- `*_INDEX_RUN_CREATED`
- `*_INDEX_RUN_STARTED`
- `*_INDEX_RUN_FINISHED`
- `*_INDEX_RUN_FAILED`
- `*_INDEX_RUN_CANCELED`

Where `*` is `SEARCH`, `ENTITY`, or `DERIVATIVE`.

## Next Prompt Boundary

Prompt 88 delivers lineage/projection/orchestration scaffolding only.

Prompts 89-92 deepen:

- full-text query semantics and token-level search UX
- controlled entity extraction/index query products
- safeguarded derivative snapshot query products and disclosure checks
- richer activation gates and freshness/quality operations

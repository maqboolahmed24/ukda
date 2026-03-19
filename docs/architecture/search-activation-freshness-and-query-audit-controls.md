# Search Activation, Freshness, And Query-Audit Controls

Status: Implemented in Prompt 93
Scope: Recall-first search activation gates, freshness/readiness truth, rollback semantics, controlled query-audit storage, and admin/auditor index-quality operations.

## Canonical Activation Gate (Search)

Search activation is enforced by one canonical evaluator in the API service layer:

- `IndexService.evaluate_search_activation_gate(...)`

`POST /projects/{projectId}/search-indexes/{indexId}/activate` is rejected unless all required checks pass.

Required checks:

- generation status is `SUCCEEDED`
- eligible-input coverage counters exist
- token-anchor validity counters satisfy eligible-input floor
- token-geometry coverage counters satisfy eligible-input floor
- historical line-only exclusions are explicit and valid
- fallback markers/reason are present when line-only exclusions are declared

Canonical blocker codes:

- `RUN_NOT_SUCCEEDED`
- `SEARCH_ELIGIBLE_INPUTS_MISSING`
- `SEARCH_LINE_ONLY_EXCLUDED_INVALID`
- `SEARCH_LINE_ONLY_FALLBACK_MARKER_MISSING`
- `SEARCH_LINE_ONLY_FALLBACK_REASON_MISSING`
- `TOKEN_ANCHOR_VALIDITY_MISSING`
- `TOKEN_ANCHOR_VALIDITY_FAILED`
- `TOKEN_GEOMETRY_COVERAGE_MISSING`
- `TOKEN_GEOMETRY_COVERAGE_FAILED`

The evaluator is reused by activation and index-quality surfaces. No parallel activation-gate implementation is allowed.

## Freshness Truth And Status

Freshness is projection-first and never inferred from "latest successful" alone.

Source of active truth:

- `project_index_projections.active_search_index_id`

Freshness statuses:

- `current`
- `stale`
- `missing`
- `blocked`

Returned freshness data includes:

- active generation id/version/status
- latest succeeded generation id/version/finished time
- stale generation gap
- reason text
- blocker codes when status is `blocked`

For search, a generation can be `blocked` even when `SUCCEEDED` if recall-first gate checks fail.

## Rollback Semantics

Rollback is explicit re-activation of an older `SUCCEEDED` search generation through the same activate endpoint:

- `POST /projects/{projectId}/search-indexes/{indexId}/activate`

Rollback rules:

- updates only `project_index_projections.active_search_index_id`
- does not clone historical rows
- does not mutate immutable lineage payloads
- preserves append-only index history

## Controlled Query-Audit Pipeline

Search query execution appends immutable audit rows:

- table: `search_query_audits`
- fields: `id`, `project_id`, `actor_user_id`, `search_index_id`, `query_sha256`, `query_text_key`, `filters_json`, `result_count`, `created_at`

Raw query text is not stored in ordinary operational events. It is stored in controlled storage and referenced by key:

- table: `search_query_texts`
- reference: `search_query_audits.query_text_key`

Operational and admin list surfaces use normalized hash and key:

- `query_sha256`
- `query_text_key`

No non-admin/non-auditor read surface exposes raw query text.

## Admin Index-Quality Surfaces (Phase 11 Ops Consumption)

Canonical API routes:

- `GET /admin/index-quality?projectId={projectId}`
- `GET /admin/index-quality/{indexKind}/{indexId}`
- `GET /admin/index-quality/query-audits?projectId={projectId}&cursor={cursor}&limit={limit}`

RBAC:

- allowed: `ADMIN`, `AUDITOR`
- denied: all other platform roles

Canonical web routes:

- `/admin/index-quality?projectId={projectId}`
- `/admin/index-quality/:indexKind/:indexId`
- `/admin/index-quality/query-audits?projectId={projectId}`

Phase 11 operations use these surfaces as the search-quality source of truth for:

- stale/blocked detection
- rollback readiness checks
- query-audit review without raw-query disclosure

## Audit Event Coverage

Prompt 93 extends audit coverage with:

- `SEARCH_QUERY_EXECUTED`
- `SEARCH_RESULT_OPENED`
- `SEARCH_INDEX_RUN_CREATED`
- `SEARCH_INDEX_RUN_CANCELED`
- `SEARCH_INDEX_ACTIVATED`
- `INDEX_QUALITY_VIEWED`
- `INDEX_QUALITY_DETAIL_VIEWED`
- `INDEX_QUALITY_QUERY_AUDITS_VIEWED`

These events are append-only and route-attributed through request context metadata.

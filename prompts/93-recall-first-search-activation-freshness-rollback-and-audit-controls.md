You are the implementation agent for UKDE. Work directly in the repository. Do not ask clarifying questions. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: assume zero chat memory and reread the repo plus the listed phase files before changing anything.
- Sequenced: if the repo already contains partial implementation from earlier prompts, extend and reconcile it instead of restarting from scratch.

The actual product source of truth is the extracted `/phases` directory in repo root. Do not mention or expect a zip. Read `/phases` first on every run.

## Mandatory first actions
1. Inspect the full repository tree.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`
   - `/phases/phase-10-granular-data-products.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — active search index logic, query APIs, search routes, token-anchor coverage checks, admin operations/index-quality surfaces, audit code, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second search activation gate, a second freshness model, or conflicting rollback semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for recall-first token-anchor requirements, index freshness, query audits, rollback semantics, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that controlled search cannot be activated unless token-anchor validity and geometry coverage gates pass for eligible runs, with explicit fallback handling only where the phase allows it.

## Objective
Enforce recall-first search activation, freshness checks, rollback paths, and audit controls.

This prompt owns:
- search-index activation gating tied to recall-first token-anchor readiness
- freshness metrics and stale-index detection
- query audit logging with controlled raw-query storage
- admin index-quality and freshness read surfaces
- explicit rollback and re-activation flows for search indexes
- audit coverage for queries, rebuilds, activation, rollback, and quality reads

This prompt does not own:
- search result UX
- entity or derivative discovery features
- semantic ranking changes
- a second search backend
- general observability dashboards outside search/index quality

## Phase alignment you must preserve
From Phase 10 Iteration 10.0, 10.1, and 10.4, plus the recall-first patch:

### Required search activation rules
- `POST /projects/{projectId}/search-indexes/{indexId}/activate` is rejected unless:
  - candidate row already has `status = SUCCEEDED`
  - token-anchor validity passes for eligible transcript inputs
  - geometry-coverage gates pass for eligible transcript inputs
  - fallback markers are explicit only for intentionally excluded historical line-only runs
- active search truth comes only from `project_index_projections.active_search_index_id`
- rollback is explicit re-activation of an older `SUCCEEDED` generation and updates only the projection

### Required search query audit logging
Persist `search_query_audits` with:
- `id`
- `project_id`
- `actor_user_id`
- `search_index_id`
- `query_sha256`
- `query_text_key`
- `filters_json`
- `result_count`
- `created_at`

Rules:
- `query_text_key` stores raw query text in Controlled audit storage
- ordinary operational views use the normalized `query_sha256`
- query audit reads remain restricted to `ADMIN` and read-only `AUDITOR`

### Required admin index-quality and query-audit routes
- `GET /admin/index-quality?projectId={projectId}`
- `GET /admin/index-quality/{indexKind}/{indexId}`
- `GET /admin/index-quality/query-audits?projectId={projectId}&cursor={cursor}&limit={limit}`

RBAC:
- readable by `ADMIN` and read-only `AUDITOR`
- backend handlers must enforce role checks server-side

### Required web surfaces
- `/admin/index-quality?projectId={projectId}`
- `/admin/index-quality/:indexKind/:indexId`
- `/admin/index-quality/query-audits?projectId={projectId}`

### Required audit events
Use or reconcile:
- `SEARCH_QUERY_EXECUTED`
- `SEARCH_RESULT_OPENED`
- `SEARCH_INDEX_RUN_CREATED`
- `SEARCH_INDEX_RUN_CANCELED`
- `SEARCH_INDEX_ACTIVATED`
- `INDEX_QUALITY_VIEWED`
- `INDEX_QUALITY_DETAIL_VIEWED`
- `INDEX_QUALITY_QUERY_AUDITS_VIEWED`

## Implementation scope

### 1. Activation gate evaluator
Implement or refine a canonical activation gate evaluator for search indexes.

Requirements:
- checks candidate status, token-anchor validity, and geometry coverage
- returns typed blocker details
- blocks activation safely and explicitly
- does not allow “latest successful” shortcuts
- remains deterministic and testable

### 2. Freshness metrics and status
Implement or refine freshness tracking.

Requirements:
- freshness metrics update after rebuilds and activations
- current active search generation can be compared against latest completed rebuilds
- status clearly distinguishes:
  - current
  - stale
  - missing
  - blocked
- freshness stays tied to the active projection, not guessed from history

### 3. Query audit pipeline
Implement or refine `search_query_audits`.

Requirements:
- query execution appends audit rows
- normalized `query_sha256` is always stored
- raw query text goes only to controlled storage via `query_text_key`
- filters and target `search_index_id` are captured
- no raw query text leaks into ordinary logs

### 4. Admin index-quality APIs
Implement or refine the admin read surfaces.

Requirements:
- per-project index quality summary
- per-index detail read
- freshness indicators
- token-anchor coverage and fallback usage summaries where useful
- `ADMIN` and read-only `AUDITOR` access only
- typed contracts

### 5. Rollback path
Refine rollback semantics for search indexes.

Requirements:
- rollback uses the existing activate endpoint against an older `SUCCEEDED` generation
- rollback updates only `project_index_projections.active_search_index_id`
- historical rows remain immutable
- rollback does not clone or mutate index history

### 6. Web admin quality surfaces
Implement or refine the index-quality web surfaces.

Requirements:
- calm, dense operational presentation
- freshness indicators
- activation blockers and rollback context where useful
- query audit summaries without exposing raw query text
- no giant admin console aesthetic

### 7. Audit and regression
Add or refine regression coverage.

At minimum cover:
- activation blocked when token-anchor validity fails
- activation blocked when geometry coverage gates fail
- freshness metrics update after rebuilds and activation
- query audit rows capture actor, normalized query hash, filters, result count, and `search_index_id`
- query-audit read surface emits `INDEX_QUALITY_QUERY_AUDITS_VIEWED`
- raw query text remains controlled-only
- rollback updates only the active projection

### 8. Documentation
Document:
- search activation gate rules
- freshness semantics
- query audit storage and access rules
- rollback semantics
- how Phase 11 ops surfaces and controls consume this search quality truth

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- search activation gate evaluator
- freshness metrics/status reads
- `search_query_audits`
- admin index-quality APIs
- tests

### Web
- admin index-quality summary/detail surfaces
- freshness and blocker presentation
- rollback-aware index detail refinements

### Docs
- recall-first search activation and freshness doc
- controlled query-audit and rollback doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**` only if tiny search-quality helpers are needed
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small admin quality/status refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- search UI
- entity or derivative discovery
- broad operations dashboards outside search/index quality
- a second search audit pipeline

## Testing and validation
Before finishing:
1. Verify search activation is blocked when token-anchor validity fails.
2. Verify search activation is blocked when geometry coverage gates fail.
3. Verify freshness metrics update after rebuilds and activation.
4. Verify query audit rows capture normalized query hashes and controlled raw-query references.
5. Verify raw query text does not leak to ordinary logs or non-admin views.
6. Verify rollback re-activates older successful generations without mutating history.
7. Verify admin/auditor RBAC on index-quality and query-audit reads.
8. Verify docs match the implemented search quality and audit behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- recall-first search activation gates are real
- freshness checks are real
- rollback paths are real
- query audit controls are real
- admin/auditor quality surfaces are real
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

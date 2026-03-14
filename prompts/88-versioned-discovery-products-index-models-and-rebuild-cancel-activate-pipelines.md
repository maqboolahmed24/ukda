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
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`
   - `/phases/phase-10-granular-data-products.md`
3. Then review the current repository generally — transcription outputs, token anchors, governance artefacts, current jobs/workers, routes, shared UI, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second indexing framework, a second active-index projection model, or competing rebuild/cancel/activate semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for index model semantics, rebuild dedupe rules, activation gates, projection ownership, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that search, entity, and derivative products are explicit versioned data products with append-only lineage and explicit active pointers.

## Objective
Stand up versioned discovery products, index models, and rebuild/cancel/activate pipelines.

This prompt owns:
- the canonical index schemas and projections
- rebuild/cancel/activate workflows
- deterministic rebuild dedupe behavior
- source snapshot pinning
- explicit active index projections
- index management routes and detail/status reads
- rollback by re-activating older successful generations
- append-only audit coverage for index lifecycle

This prompt does not own:
- full-text search query UX
- entity extraction product logic
- derivative snapshot logic beyond index-row scaffolding
- quality/freshness dashboards
- a second index-management system

## Phase alignment you must preserve
From Phase 10 Iteration 10.0:

### Required tables
Implement or reconcile:
- `search_indexes`
- `entity_indexes`
- `derivative_indexes`
- `search_documents`
- `derivative_index_rows`
- `project_index_projections`

Index rows require:
- `id`
- `project_id`
- `version`
- `source_snapshot_json`
- `source_snapshot_sha256`
- `rebuild_dedupe_key`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `supersedes_index_id`
- `superseded_by_index_id`
- `failure_reason`
- create/start/finish/cancel/activate metadata

Projection:
- `project_index_projections`
  - `project_id`
  - `active_search_index_id`
  - `active_entity_index_id`
  - `active_derivative_index_id`
  - `updated_at`

### Core rebuild rules
- rebuild requests compute a deterministic `rebuild_dedupe_key` from `(project_id, index_kind, source_snapshot_sha256, normalized build parameters)`
- equivalent rebuild requests without `force=true` return the existing generation instead of creating a duplicate
- failed rebuilds do not replace active pointers
- cancel is allowed only while `QUEUED` or `RUNNING`
- queued generations can become `CANCELED` directly
- running cancellations complete only via worker-cooperative shutdown
- activating an older `SUCCEEDED` generation is the explicit rollback path; rollback updates only the active projection

### Required APIs
- `GET /projects/{projectId}/indexes/active`
- `GET /projects/{projectId}/search-indexes`
- `POST /projects/{projectId}/search-indexes/rebuild`
- `GET /projects/{projectId}/search-indexes/{indexId}`
- `GET /projects/{projectId}/search-indexes/{indexId}/status`
- `POST /projects/{projectId}/search-indexes/{indexId}/cancel`
- `POST /projects/{projectId}/search-indexes/{indexId}/activate`
- and the same pattern for:
  - `entity-indexes`
  - `derivative-indexes`
- rebuild endpoints must accept source snapshot reference plus normalized build parameters used to compute `rebuild_dedupe_key`
- rebuild endpoints support optional `force=true`; without force, equivalent rebuilds return the existing generation

### RBAC
- project-scoped index metadata readable by `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, and `ADMIN`
- rebuild, cancel, and activate actions restricted to `ADMIN`
- `AUDITOR` does not use project-scoped mutation routes in this iteration

### Required web routes
- `/projects/:projectId/indexes`
- `/projects/:projectId/indexes/search/:indexId`
- `/projects/:projectId/indexes/entity/:indexId`
- `/projects/:projectId/indexes/derivative/:indexId`

## Implementation scope

### 1. Canonical index schemas and snapshots
Implement or refine the canonical index models.

Requirements:
- one versioned lineage per search/entity/derivative family
- full `source_snapshot_json` plus `source_snapshot_sha256`
- no hash-only shorthand that makes lineage opaque
- no second hidden projection or status store

### 2. Rebuild pipeline
Implement rebuild orchestration for all three index families.

Requirements:
- deterministic dedupe key
- optional `force=true` override
- queued/running/succeeded/failed/canceled lifecycle
- worker-friendly orchestration
- append-only attempts
- no duplicate competing active generations for equivalent requests

### 3. Cancel and activate behavior
Implement or refine:
- cancel
- activate
- rollback by activating older successful generations

Requirements:
- terminal-state cancellation is rejected
- failed/canceled generations do not replace active pointers
- activate only for `SUCCEEDED` rows
- rollback uses the same activate endpoint and never clones history

### 4. Active projection reads
Implement or refine:
- `GET /projects/{projectId}/indexes/active`

Requirements:
- active search/entity/derivative pointers are explicit
- current-generation truth comes only from `project_index_projections`
- no “latest successful” inference

### 5. Index management surfaces
Implement or refine the web management UI.

Requirements:
- current active search/entity/derivative generations visible
- rebuild, cancel, activate controls visible only to `ADMIN`
- detail pages and status polling for each index family
- calm empty/loading/error/not-ready states
- no giant operations console aesthetic

### 6. Audit and tests
Use the canonical audit path and add coverage.

At minimum cover:
- reproducible rebuild inputs produce same dedupe key
- equivalent rebuild requests without force return existing generation
- failed rebuilds leave active pointers unchanged
- canceled rebuilds leave active pointers unchanged
- activation updates only the active projection
- rollback does not mutate historical rows
- audit events:
  - `INDEX_ACTIVE_VIEWED`
  - `SEARCH_INDEX_LIST_VIEWED`
  - `SEARCH_INDEX_DETAIL_VIEWED`
  - `SEARCH_INDEX_STATUS_VIEWED`
  - `SEARCH_INDEX_RUN_CREATED`
  - `SEARCH_INDEX_RUN_STARTED`
  - `SEARCH_INDEX_RUN_FINISHED`
  - `SEARCH_INDEX_RUN_FAILED`
  - `SEARCH_INDEX_RUN_CANCELED`
  - corresponding entity/derivative events

### 7. Documentation
Document:
- index model and projection ownership
- rebuild dedupe rules
- cancel/activate/rollback semantics
- what Prompts 89–92 will deepen next

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / workers / contracts
- index schemas
- rebuild/cancel/activate pipelines
- active projection reads
- tests

### Web
- index management route
- index detail/status routes
- admin-only controls and status polling

### Docs
- discovery index model and rebuild doc
- active projection and rollback doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small management/detail/status refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- full-text query UX
- entity extraction logic
- derivative snapshot logic beyond index lineage scaffolding
- quality/freshness dashboards
- a second index-management model

## Testing and validation
Before finishing:
1. Verify reproducible rebuild inputs generate the same dedupe key.
2. Verify equivalent rebuild requests without `force=true` return the existing generation.
3. Verify failed rebuilds do not replace active pointers.
4. Verify canceled rebuilds do not replace active pointers.
5. Verify cancel is allowed only for `QUEUED` or `RUNNING` generations and rejected for terminal states.
6. Verify activation updates only `project_index_projections`.
7. Verify rollback is explicit re-activation of an older `SUCCEEDED` generation.
8. Verify role boundaries for read vs rebuild/cancel/activate actions.
9. Verify docs match the implemented index and lifecycle behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- versioned search/entity/derivative index lineages are real
- rebuild/cancel/activate pipelines are real
- active projections are explicit and authoritative
- rollback semantics are real and append-only
- the repo is ready for search, entity, and derivative feature layers
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

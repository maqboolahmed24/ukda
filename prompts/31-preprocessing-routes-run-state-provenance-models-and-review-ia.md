You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed phase files before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first on each run.

## Mandatory first actions
1. Inspect the relevant repository areas and any existing implementation this prompt may extend.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-01-ingest-document-viewer-v1.md`
   - `/phases/phase-02-preprocessing-pipeline-v1.md`
3. Then review the current repository generally — document/viewer routes, page models, jobs, workers, shared UI, typed data layer, audit code, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second preprocessing route family, a second run model, or conflicting compare-surface ownership.

## Source-of-truth hierarchy
Use this precedence order when implementing:
1. The specific `/phases` files listed in this prompt for product behavior and acceptance logic.
2. `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md` when this prompt depends on web-first execution semantics.
3. `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` when this prompt depends on recall-first, rescue, token-anchor, search-anchoring, or conservative-masking semantics.
4. `/phases/blueprint-ukdataextraction.md`, `/phases/README.md`, and `/phases/ui-premium-dark-blueprint-obsidian-folio.md` as supporting product context when they are listed or clearly relevant.
5. This prompt for task scope and deliverables.
6. Current repository state for reconciling implementation details.
7. Official external docs for implementation mechanics only.

Treat current repository state as implementation context, not as the primary source of product truth.

## Conflict-resolution rule
- `/phases` wins for preprocessing route ownership, run lineage, active-run projection behavior, compare-surface ownership, RBAC, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the Phase 1 viewer as the reading surface and `/preprocessing/compare` as the canonical preprocessing diagnostics surface. Do not blur them together.

## Objective
Stand up preprocessing routes, run state, provenance models, and review information architecture for derived page workflows.

This prompt owns:
- the canonical preprocessing route family
- the preprocessing run data model and per-page result model
- the active-run projection model
- source-page metadata extensions needed by preprocessing
- preprocessing overview, quality, runs, metadata, and compare information architecture
- typed preprocessing API scaffolding
- RBAC and audit surfaces for preprocessing run administration
- consistent shell integration with the existing document/viewer family

This prompt does not own:
- the real preprocessing engine
- real grayscale output generation
- compare-mode image rendering depth
- later aggressive profile controls
- layout/transcription/privacy work

## Phase alignment you must preserve
From Phase 2 Iteration 2.0:

### Required routes
- `/projects/:projectId/documents/:documentId/preprocessing`
  - internal tabs:
    - `Pages`
    - `Quality`
    - `Processing runs`
    - `Metadata`
- `/projects/:projectId/documents/:documentId/preprocessing/quality`
- `/projects/:projectId/documents/:documentId/preprocessing/runs/:runId`
- `/projects/:projectId/documents/:documentId/preprocessing/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`
- existing viewer route remains:
  - `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`
  - with compare mode and a right inspector drawer for metrics + run selection where supported

### Ownership rule
- `/preprocessing/compare` is the canonical run-analysis surface for preprocessing diagnostics, metrics, and before/after comparison between runs
- viewer compare mode is an in-context reading aid and must link back to `/preprocessing/compare` when deeper diagnostics are needed

### Required data model
Add or reconcile:

#### `preprocess_runs`
- `id`
- `project_id`
- `document_id`
- `parent_run_id`
- `attempt_number`
- `superseded_by_run_id`
- `profile_id`
- `params_json`
- `params_hash`
- `pipeline_version`
- `container_digest`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `created_by`
- `created_at`
- `started_at`
- `finished_at`
- `failure_reason`

#### `page_preprocess_results`
- `run_id`
- `page_id`
- `page_index`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `input_object_key`
- `output_object_key_gray`
- `output_object_key_bin`
- `metrics_json`
- `sha256_gray`
- `sha256_bin`
- `warnings_json`
- `failure_reason`
- `created_at`
- `updated_at`

#### `document_preprocess_projections`
- `document_id`
- `project_id`
- `active_preprocess_run_id`
- `active_profile_id`
- `updated_at`

Rules:
- overview, quality, and viewer-default variant reads use `active_preprocess_run_id` when a caller does not request a specific run
- reruns append a new `preprocess_runs` row, increment `attempt_number`, preserve `parent_run_id`, and record the forward lineage link on the superseded source row through `superseded_by_run_id`

### Required `pages` source metadata extensions
Add if missing:
- `source_width`
- `source_height`
- `source_dpi`
- `source_color_mode` (`RGB | RGBA | GRAY | CMYK | UNKNOWN`)

### Required API scaffolding
- `GET /projects/{projectId}/documents/{documentId}/preprocessing/overview`
- `GET /projects/{projectId}/documents/{documentId}/preprocessing/quality?runId={runId}&warning={warning}&status={status}&cursor={cursor}`
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/active`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/status`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/pages`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/pages/{pageId}`
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/rerun`
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/cancel`
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/activate`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`

### Required RBAC
- `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, `ADMIN` can view quality and runs
- only `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can create, rerun, cancel, or activate preprocessing runs

### Required audit events
Emit or reconcile:
- `PREPROCESS_OVERVIEW_VIEWED`
- `PREPROCESS_QUALITY_VIEWED`
- `PREPROCESS_RUNS_VIEWED`
- `PREPROCESS_ACTIVE_RUN_VIEWED`
- `PREPROCESS_RUN_VIEWED`
- `PREPROCESS_RUN_STATUS_VIEWED`
- `PREPROCESS_RUN_CREATED`
- `PREPROCESS_RUN_STARTED`
- `PREPROCESS_RUN_FINISHED`
- `PREPROCESS_RUN_FAILED`
- `PREPROCESS_RUN_CANCELED`
- `PREPROCESS_RUN_ACTIVATED`

Creation events must include params hash and pipeline version.

## Implementation scope

### 1. Data model and contract scaffolding
Implement or reconcile the preprocessing schema.

Requirements:
- one canonical `preprocess_runs` model
- one canonical `page_preprocess_results` model
- one canonical `document_preprocess_projections` model
- typed shared contracts
- no duplicate run schema
- future rerun lineage is preserved without overbuilding the engine now

If the current repo already has partial preprocessing models, migrate or reconcile them toward the phase contract instead of replacing them wholesale.

### 2. Route family and information architecture
Implement or refine the preprocessing route family.

Requirements:
- all routes fit the canonical project/document shell
- tabs or equivalent internal navigation for:
  - Pages
  - Quality
  - Processing runs
  - Metadata
- compare route is clearly the canonical diagnostics surface
- viewer compare mode entrypoint is consistent but does not replace `/preprocessing/compare`
- deep links reload safely
- breadcrumbs remain orientation-only

### 3. Overview page
Build the preprocessing overview route.

Requirements:
- clear page header
- calm summary of active run state
- safe empty state when no preprocessing run exists yet
- entrypoints to:
  - run preprocessing
  - view quality
  - view processing runs
  - compare runs when enough material exists
- no fake metrics before the engine exists

### 4. Processing runs surfaces
Implement or refine:
- runs list
- run detail
- run status polling
- rerun/cancel/activate affordance shells

Requirements:
- runs table columns and detail hierarchy are dense but clear
- run detail includes summary shell and parameters drawer/collapsible section
- active runs can be polled through the status endpoint
- if the engine is not yet live, states remain accurate (`QUEUED`, `RUNNING`, etc.) without fake success

### 5. Quality surface
Implement the quality route shell.

Requirements:
- can read from active run projection by default
- supports typed filter/query inputs such as warning/status/cursor
- remains useful even before the engine is fully live
- no fake before/after images yet unless the repo already has simple placeholders
- clear empty and not-yet-available messaging

### 6. Compare surface skeleton
Implement or refine `/preprocessing/compare`.

Requirements:
- accepts `baseRunId` and `candidateRunId`
- has a bounded compare workspace shell
- clarifies that it is the canonical diagnostics surface
- can safely render empty/not-ready/no-results states until later compare-focused work deepens the compare UI
- integrates with the viewer compare entrypoint if appropriate and consistent

### 7. API scaffolding behavior
Implement the listed preprocessing APIs in an accurate Phase 2.0 state.

Requirements:
- create run endpoint can create a `QUEUED` run and seed consistent state
- active run endpoint reads the projection
- list/detail/status endpoints are typed and RBAC-protected
- rerun/cancel/activate endpoints are present with correct role boundaries
- activate updates the projection without mutating historical run rows
- if the engine is not yet present, do not fake preprocessing outputs

### 8. Source page metadata extensions
Reconcile `pages` so preprocessing has stable immutable source metadata.

Requirements:
- width/height/dpi/color-mode source fields exist and are trustworthy
- preprocessing does not overwrite source page facts
- future downstream phases can rely on these fields as-is

### 9. Audit and shell integration
Use the existing audit path and shell system.

Requirements:
- audit events emitted as specified
- no second audit path
- route surfaces look like part of the same product, not a parallel tool
- current viewer/document routes link into preprocessing via canonical routes and preserve document/run context in URL state

### 10. Documentation
Document:
- preprocessing route ownership
- run and projection models
- compare-surface ownership
- what the deterministic engine work will add
- what later work should add in compare and quality review tooling

## Required deliverables

### Backend / contracts
- preprocessing schema/migrations
- typed contracts
- preprocessing API scaffolding
- tests

### Web
- preprocessing overview
- quality route
- runs list/detail surfaces
- compare route shell
- metadata surface
- shell/navigation/breadcrumb integration

### Docs
- preprocessing information architecture and route contract doc
- preprocessing run/projection model doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small tabs/table/drawer/compare-shell refinements are needed
- `/workers/**` only if small queue/run scaffolding is required for accurate `QUEUED` creation
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- actual preprocessing image generation
- compare-image rendering depth
- aggressive profile controls
- layout/transcription/privacy/export work
- a second preprocessing route family
- fake success outputs

## Testing and validation
Before finishing:
1. Verify all preprocessing routes exist and fit the canonical shell.
2. Verify preprocessing routes reload and deep-link safely.
3. Verify RBAC boundaries for view vs create/rerun/cancel/activate.
4. Verify audit events are emitted.
5. Verify active projection behavior is consistent.
6. Verify create/run scaffolding does not fake outputs when the engine is not yet live.
7. Verify viewer compare entry and `/preprocessing/compare` ownership stay consistent.
8. Verify docs match actual routes, APIs, and current scope boundaries.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- preprocessing overview/quality/runs/compare routes are implemented, navigable, and deep-linkable via the documented route contract
- run records and active-projection pointers are persisted with typed status/provenance fields and document-scoped queries
- compare surface ownership is clear
- RBAC and audit tests cover run create, rerun, cancel, and activate actions
- current schema and route contracts support preprocessing run execution and compare selection without structural route rewrites
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

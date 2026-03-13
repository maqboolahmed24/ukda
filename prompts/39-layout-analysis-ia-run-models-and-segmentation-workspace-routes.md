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
   - `/phases/phase-03-layout-segmentation-overlays-v1.md`
3. Then review the current repository generally — project/document routes, page models, preprocessing projections, jobs, workers, shared UI primitives, typed contracts, audit code, browser tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second layout-analysis route family, a second run model, or conflicting workspace ownership.

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
- `/phases` wins for layout route ownership, run-model semantics, projection behavior, workspace structure, RBAC, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that advanced segmentation tools live in dedicated workspaces and do not clutter general document views.

## Objective
Stand up layout-analysis information architecture, run models, and segmentation-workspace routes for structured page understanding.

This prompt owns:
- the canonical layout-analysis route family
- the layout run and projection data model
- page-level layout-result and recall-check scaffolding
- layout overview, page triage, runs, and workspace shells
- optional activation and cancellation scaffolding for layout runs
- RBAC and audit surfaces for layout analysis
- web shells and typed APIs that later work can extend with real inference and overlays

This prompt does not own:
- the real segmentation engine
- canonical PAGE-XML and overlay payload implementation
- manual correction tools
- reading-order editing
- layout crops/context windows
- recall-first rescue enforcement or strict downstream activation gates
- transcription or privacy features

## Phase alignment you must preserve
From Phase 3 Iteration 3.0:

### Required routes
- `/projects/:projectId/documents/:documentId/layout`
  - internal tabs:
    - `Layout overview`
    - `Page triage`
    - `Runs`
- `/projects/:projectId/documents/:documentId/layout/runs/:runId`
- `/projects/:projectId/documents/:documentId/layout/workspace?page={pageNumber}&runId={runId}`

### Workspace contract
Layout workspace surfaces inherit the single-fold adaptive contract:
- top toolbar:
  - run selector
  - overlay toggles
  - `Open triage`
- left rail:
  - page filmstrip
- center:
  - page canvas
- right inspector:
  - page metrics
  - regions/lines list with selection highlighting
- default composition keeps page-level vertical scrolling out of the shell

In Iteration 3.0 the workspace is read-only and may stay explicit about missing overlay data until later work materializes canonical layout outputs.

### Required data model
Implement or reconcile:

#### `layout_runs`
- `id`
- `project_id`
- `document_id`
- `input_preprocess_run_id`
- `run_kind` (`AUTO`)
- `parent_run_id`
- `attempt_number`
- `superseded_by_run_id`
- `model_id`
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

#### `page_layout_results`
- `run_id`
- `page_id`
- `page_index`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `page_recall_status` (`COMPLETE | NEEDS_RESCUE | NEEDS_MANUAL_REVIEW`)
- `active_layout_version_id`
- `page_xml_key`
- `overlay_json_key`
- `page_xml_sha256`
- `overlay_json_sha256`
- `metrics_json`
- `warnings_json`
- `failure_reason`
- `created_at`
- `updated_at`

#### `layout_recall_checks`
- `run_id`
- `page_id`
- `recall_check_version`
- `missed_text_risk_score`
- `signals_json`
- `created_at`

#### `layout_rescue_candidates`
- `id`
- `run_id`
- `page_id`
- `candidate_kind` (`LINE_EXPANSION | PAGE_WINDOW`)
- `geometry_json`
- `confidence`
- `source_signal`
- `status` (`PENDING | ACCEPTED | REJECTED | RESOLVED`)
- `created_at`
- `updated_at`

#### `document_layout_projections`
- `document_id`
- `project_id`
- `active_layout_run_id`
- `active_input_preprocess_run_id`
- `updated_at`

Rules:
- overview, triage, and workspace defaults read from `document_layout_projections.active_layout_run_id` when a caller does not request a specific run
- reruns append a new `layout_runs` row, increment `attempt_number`, preserve `parent_run_id`, and record the forward lineage link through `superseded_by_run_id`
- manual-edit and reading-order-edit run kinds are reserved for later workflow-specific implementation
- this prompt may expose an explicit active layout projection if the repository already supports it, but recall-first rescue gates and stricter downstream invalidation rules remain outside this prompt's scope

### Required APIs
Implement or reconcile:
- `GET /projects/{projectId}/documents/{documentId}/layout/overview`
- `POST /projects/{projectId}/documents/{documentId}/layout-runs`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/active`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/status`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages`
- `POST /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/activate`
- `POST /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/cancel`

Canonical PAGE-XML and overlay payload contracts are outside this prompt's scope.
Do not overbuild them here beyond basic placeholder support if the workspace needs it.

### Required RBAC
- only `PROJECT_LEAD`, `RESEARCHER`, or `REVIEWER` can view layout artefacts and routes
- only `PROJECT_LEAD`, `REVIEWER`, or `ADMIN` can create or cancel runs
- activation follows the same write-capable role boundaries where an activation scaffold is present, unless the current repo already has a stricter pattern

### Required audit events
Emit or reconcile:
- `LAYOUT_OVERVIEW_VIEWED`
- `LAYOUT_TRIAGE_VIEWED`
- `LAYOUT_RUNS_VIEWED`
- `LAYOUT_ACTIVE_RUN_VIEWED`
- `LAYOUT_RUN_CREATED`
- `LAYOUT_RUN_STARTED`
- `LAYOUT_RUN_FINISHED`
- `LAYOUT_RUN_FAILED`
- `LAYOUT_RUN_CANCELED`

## Implementation scope

### 1. Canonical layout-analysis route family
Implement or refine the route family exactly under the project/document scope.

Requirements:
- no second layout route family
- shell, breadcrumb, and page-header consistency across overview, triage, runs, and run-detail routes
- deep-link-safe route loading
- tabs or equivalent internal navigation for overview / triage / runs
- workspace route with `page` and `runId` query usage that remains bounded and browser-safe

### 2. Layout data model and projection scaffolding
Implement or reconcile the listed data models.

Requirements:
- one canonical layout run model
- one canonical page result model
- one canonical layout projection model
- one canonical recall-check and rescue-candidate scaffold
- typed contracts aligned with backend reality
- no fake inference output inserted just to satisfy UI routes

If optional denormalized tables such as `layout_elements` help later work and fit the current repo, you may reserve them, but do not let them become the canonical source of truth.

### 3. Layout overview surface
Implement or refine the layout overview.

Requirements:
- summary cards read from the active layout projection when present
- primary CTA: `Run layout analysis`
- secondary action: `View run details`
- calm empty/loading/error states
- if no active run exists, overview remains clear and useful
- no fake metrics if inference has not been built yet

### 4. Page triage surface
Implement or refine the page-triage table.

Requirements:
- columns:
  - page number
  - issues
  - region count
  - line count
  - coverage percent
  - status
- filters:
  - missing lines
  - overlaps
  - low coverage
  - complex layout / uncertain structure
- row selection opens a right-side details drawer with:
  - overlay preview placeholder or clear not-yet-available state
  - metrics
  - `Open in workspace`
- bounded scroll, keyboard-safe selection, and calm table states

### 5. Runs list and run detail shell
Implement or refine the runs surfaces.

Requirements:
- runs list is consistent and typed
- run detail route exists and fits the canonical shell
- active run is clearly shown when an explicit active projection already exists
- activation and cancel affordances are role-aware where the current repo exposes them
- active runs may poll the status endpoint
- no fake success output before the engine exists

### 6. Read-only workspace shell
Implement or refine the segmentation workspace shell.

Requirements:
- toolbar with run selector, overlay toggles, and `Open triage`
- left filmstrip
- center canvas
- right inspector with page metrics and regions/lines list shell
- overlay toggles may remain clear placeholders until canonical payload and rendering work deepens them
- the workspace must preserve the bounded single-fold shell contract
- focus, keyboard, and adaptive states remain consistent

### 7. Optional activation scaffolding
Implement or refine only the minimum explicit activation scaffold the current repo can support without stealing ownership from later recall and invalidation prompts.

Requirements:
- if an activation path is exposed now, only `SUCCEEDED` runs may be candidates
- any activation path updates `document_layout_projections.active_layout_run_id` explicitly
- any activation path records `active_input_preprocess_run_id` explicitly
- historical run rows remain immutable
- do not hardwire recall-first rescue gating or downstream transcription invalidation semantics here; those stricter rules are outside this prompt's scope
- if the repo is not ready for an accurate activation path yet, reserve the typed contract or disabled control state instead of inventing fake semantics

### 8. API scaffolding and typed contracts
Expose typed contracts the UI can consume now.

Requirements:
- list/detail/status pages are typed
- page list endpoint can serve triage and workspace selectors
- overview contracts are explicit
- empty and not-ready states are representable without lying
- no route should need to infer active/default run by guessing

### 9. Documentation
Document:
- the layout route family
- route ownership and information architecture
- run and projection model ownership
- any activation scaffold that exists today, and which stricter gates are intentionally deferred
- what later layout-output, inference, and rendering work should add
- what is intentionally a shell or clear placeholder at this stage

## Required deliverables

### Backend / contracts
- layout run and projection schema/migrations
- typed layout API scaffolding
- tests

### Web
- `/projects/:projectId/documents/:documentId/layout`
- `/projects/:projectId/documents/:documentId/layout/runs/:runId`
- `/projects/:projectId/documents/:documentId/layout/workspace?page={pageNumber}&runId={runId}`
- overview, triage, runs, and workspace shells
- role-aware run actions

### Docs
- layout-analysis information architecture and route contract doc
- layout run/projection model doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small tabs/table/drawer/workspace-shell refinements are needed
- `/workers/**` only if a small queue/run scaffold is required to create accurate `QUEUED` runs
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- the real segmentation engine
- canonical PAGE-XML serialization
- canonical overlay JSON payloads
- manual editing tools
- reading-order editing
- layout line crops/context windows
- a second layout shell

## Testing and validation
Before finishing:
1. Verify the layout routes exist and fit the canonical shell.
2. Verify overview, triage, runs, and workspace routes reload and deep-link safely.
3. Verify run creation, list, detail, status, activate, and cancel scaffolding are consistent.
4. Verify RBAC boundaries for view vs create/cancel/activate.
5. If activation scaffolding exists, verify it updates the explicit layout projection without mutating history.
6. Verify placeholder or deferred activation states remain accurate where stricter gates are not yet implemented.
7. Verify workspace remains bounded and keyboard-safe even before full overlay payloads exist.
8. Verify audit events are emitted through the canonical path.
9. Verify docs match the actual route and model scaffolding.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the layout-analysis route hierarchy and ownership boundaries are implemented as documented without parallel route families
- layout run records and active projection pointers are persisted with typed status/provenance fields
- overview, triage, runs, and workspace routes render typed data with distinct empty/not-ready/error states
- any activation scaffold that exists is explicit and accurate without pre-implementing later rescue and invalidation rules
- canonical PAGE-XML/overlay route contracts are documented and consumable without adding a second layout route family
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

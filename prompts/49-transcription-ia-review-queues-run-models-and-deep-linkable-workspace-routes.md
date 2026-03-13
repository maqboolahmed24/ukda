You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed phase files before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first on each run.

## Mandatory first actions
1. Inspect the full repository tree.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-04-handwriting-transcription-v1.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`
3. Then review the current repository generally — layout projections, line/context artefacts, transcription-related models if any, current project/document routes, shared UI/data-layer primitives, audit code, browser tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second transcription route family, a second run/projection model, or a hidden state model that fights the deep-linkable workspace route.

## Source-of-truth hierarchy
Use this precedence order when implementing:
1. The specific `/phases` files listed in this prompt for product behavior and acceptance logic.
2. `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md` when this prompt depends on web-first execution semantics.
3. `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` when this prompt depends on recall-first, rescue, token-anchor, search-anchoring, or conservative-masking semantics.
4. `/phases/blueprint-ukdataextraction.md`, `/phases/README.md`, `/phases/ui-premium-dark-blueprint-obsidian-folio.md`, and `/phases/phase-00-foundation-release.md` as supporting product context when they are listed or clearly relevant.
5. This prompt for task scope and deliverables.
6. Current repository state for reconciling implementation details.
7. Official external docs for implementation mechanics only.

Treat current repository state as implementation context, not as the primary source of product truth.

## Conflict-resolution rule
- `/phases` wins for transcription route ownership, data-model semantics, projection behavior, token-anchor requirements, RBAC, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that transcription is a document-scoped workspace family with explicit run lineage and deep-linkable review context.

## Objective
Stand up transcription IA, review queues, run models, and deep-linkable workspace routes.

This prompt owns:
- the canonical transcription route family
- transcription runs and result-schema foundations
- transcription projections
- overview, triage, runs, artefacts, and workspace shells
- typed transcription APIs for read/create/cancel/status flows
- deep-linkable workspace route semantics
- read-only review queues and run detail shells
- audit and RBAC wiring for transcription surfaces

This prompt does not own:
- the primary transcription engine
- fallback or comparison engines
- manual correction implementation
- token-anchor materialization logic
- full model-catalog governance UI
- privacy or search features

## Phase alignment you must preserve
From Phase 4 Iteration 4.0:

### Required routes
- `/projects/:projectId/documents/:documentId/transcription`
  - tabs:
    - `Overview`
    - `Triage`
    - `Runs`
    - `Artefacts`
- `/projects/:projectId/documents/:documentId/transcription/runs/:runId`
- `/projects/:projectId/documents/:documentId/transcription/workspace?page={pageNumber}&runId={runId}&lineId={lineId}&tokenId={tokenId}&sourceKind={sourceKind}&sourceRefId={sourceRefId}`

Rules:
- `lineId` is optional and deep-links to a highlighted line
- `tokenId` is optional and deep-links to exact token highlight when token anchors exist
- `sourceKind` and `sourceRefId` are optional for rescue-candidate or page-window provenance when no stable line anchor exists

### Required information hierarchy
- `Overview`: current state and progress
- `Triage`: where quality issues are concentrated
- `Workspace`: focused read/edit verification surface

### Required tables
Implement or reconcile at minimum:
- `transcription_runs`
- `page_transcription_results`
- `line_transcription_results`
- `token_transcription_results`
- `transcript_versions`
- `document_transcription_projections`
- `transcription_output_projections`

Where the repo already has a minimal `approved_models` placeholder, reconcile it. Full catalog and role-map governance belong to the corresponding model-catalog work.

### Required run fields
Preserve the Phase 4.0 contract for `transcription_runs`, including:
- `input_preprocess_run_id`
- `input_layout_run_id`
- `engine`
- `model_id`
- `prompt_template_id`
- `prompt_template_sha256`
- `response_schema_version`
- `confidence_basis`
- `params_json`
- `pipeline_version`
- `container_digest`
- `attempt_number`
- `supersedes_transcription_run_id`
- `superseded_by_transcription_run_id`
- `status`
- timestamps and failure reason

### Required projections
Preserve or reconcile:
- `document_transcription_projections.active_transcription_run_id`
- `active_layout_run_id`
- `active_preprocess_run_id`
- `downstream_redaction_state`
- `downstream_redaction_invalidated_at`
- `downstream_redaction_invalidated_reason`

Rules:
- overview, triage, and workspace defaults resolve through the activated transcription projection
- reruns append new run rows and preserve lineage
- activation updates the projection without mutating historical rows
- activation requires token-anchor materialization for pages not marked `NEEDS_MANUAL_REVIEW` by Phase 3 recall status

### Required APIs
Implement or refine:
- `GET /projects/{projectId}/documents/{documentId}/transcription/overview`
- `GET /projects/{projectId}/documents/{documentId}/transcription/triage?status={status}&confidenceBelow={threshold}&page={pageNumber}`
- `POST /projects/{projectId}/documents/{documentId}/transcription-runs`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/active`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/status`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages`
- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/activate`
- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/cancel`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/lines`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/tokens`

The PATCH line-edit endpoint is reserved for later human-correction work unless the current repo requires a minimal stub for schema consistency.

### Required tests and gates
- RBAC:
  - only `PROJECT_LEAD`, `RESEARCHER`, or `REVIEWER` can view transcription surfaces
  - run/cancel/edit-capable actions are limited to `PROJECT_LEAD`, `REVIEWER`, or `ADMIN`
- projection defaults resolve through the activated transcription projection
- in-flight progress polls the dedicated run-status endpoint instead of full run detail reload
- audit events exist for overview, triage, run create/start/finish/fail/cancel/view/status/activate
- no-egress remains enforced
- token-anchor gate remains a real activation prerequisite, even if token materialization itself is implemented later

## Implementation scope

### 1. Canonical transcription route family
Implement or refine the route family under the project/document scope.

Requirements:
- one canonical transcription area
- no second parallel route family
- shell, breadcrumb, and page-header consistency
- deep-link-safe loading
- tabs or equivalent internal navigation for overview / triage / runs / artefacts
- deep-linkable workspace route with the exact query contract from the phase

### 2. Transcription run and result schema foundation
Implement or reconcile the core schema.

Requirements:
- canonical `transcription_runs`
- canonical page/line/token result tables
- canonical `transcript_versions`
- canonical `document_transcription_projections`
- canonical `transcription_output_projections`
- append-only run lineage
- no fake inference output inserted just to satisfy UI shells

Where `approved_models` is absent, you may create the narrowest FK-ready placeholder needed for the Phase 4.0 run model. Full catalog and project assignment governance belong to the corresponding model-catalog work.

### 3. Overview surface
Implement or refine the overview route.

Requirements:
- clear page header
- summary of current state and progress
- accurate empty state when no transcription run exists
- primary CTA `Run transcription`
- links to triage, runs, and workspace
- no fake metrics before inference exists

### 4. Triage surface
Implement or refine the triage route shell.

Requirements:
- table-first or queue-first design
- filter support for status and confidence threshold
- calm empty/loading/error states
- route-safe URL-state behavior
- no fake confidence scores before engine output exists
- reads from the active transcription projection when appropriate

### 5. Runs list and run detail shells
Implement or refine:
- runs list
- run detail
- run-status polling
- role-aware activate/cancel affordance shells

Requirements:
- dense but clear runs table
- run detail summary cards
- active run clearly marked
- in-flight progress uses the dedicated status endpoint
- no fake success outputs before engine prompts own inference

### 6. Read-only workspace shell
Implement or refine the transcription workspace shell.

Requirements:
- deep-linkable via page/run/line/token/source context
- bounded single-fold composition
- reading surface plus transcript panel shell
- line highlight context
- safe empty/not-ready/error states
- no full human-edit implementation yet
- no second viewer shell

### 7. Projection and activation scaffolding
Implement or refine projection logic and activation scaffolding.

Requirements:
- defaults resolve through `document_transcription_projections.active_transcription_run_id`
- activation updates active transcription, layout, and preprocess basis values without mutating history
- if token anchors are not yet materialized, activation fails explicitly
- no “latest successful” fallback

### 8. Typed APIs and canonical data layer integration
Expose and consume the APIs through the repo’s canonical data layer.

Requirements:
- typed contracts
- status polling uses dedicated status endpoint
- overview/triage/workspace consume canonical queries
- no route-local ad hoc fetch drift
- empty and not-ready states remain representable without lying

### 9. Audit and RBAC
Use the canonical audit path.

At minimum emit or reconcile:
- `TRANSCRIPTION_OVERVIEW_VIEWED`
- `TRANSCRIPTION_TRIAGE_VIEWED`
- `TRANSCRIPTION_RUN_CREATED`
- `TRANSCRIPTION_RUN_STARTED`
- `TRANSCRIPTION_RUN_FINISHED`
- `TRANSCRIPTION_RUN_FAILED`
- `TRANSCRIPTION_RUN_CANCELED`
- `TRANSCRIPTION_RUN_VIEWED`
- `TRANSCRIPTION_RUN_STATUS_VIEWED`
- `TRANSCRIPTION_ACTIVE_RUN_VIEWED`
- `TRANSCRIPTION_RUN_ACTIVATED`

### 10. Documentation
Document:
- transcription route ownership
- run/result/projection model ownership
- workspace deep-link semantics
- activation prerequisites and token-anchor gate
- what later model-catalog and transcription work will deepen next

## Required deliverables
### Backend / contracts
- transcription schema/migrations
- typed APIs for overview/triage/runs/workspace reads
- projection scaffolding
- tests

### Web
- transcription overview
- transcription triage
- runs list/detail shells
- read-only workspace shell
- shell/navigation/breadcrumb integration

### Docs
- transcription IA and route contract doc
- transcription run/projection model doc
- any README updates required for developer usage


## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small tabs/table/drawer/workspace-shell refinements are needed
- `/workers/**` only if a small queue scaffold is required for accurate `QUEUED` creation
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- primary inference engine
- fallback engines
- manual correction tools
- token-anchor generation
- model-catalog governance UI beyond the narrowest placeholder required for run-model consistency
- privacy or search work

## Testing and validation
Before finishing:
1. Verify all transcription routes exist and fit the canonical shell.
2. Verify routes reload and deep-link safely.
3. Verify RBAC boundaries for view vs run/cancel/activate actions.
4. Verify active projection defaults are consistent.
5. Verify in-flight progress uses the status endpoint.
6. Verify activation fails explicitly when token-anchor prerequisites are unmet.
7. Verify audit events are emitted through the canonical path.
8. Verify docs match the actual routes, APIs, and scope boundaries.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the transcription route family (`overview`, `triage`, `runs`, `workspace`) is implemented and reachable for authorized users
- run and projection records are persisted with typed status fields and active projection pointers queryable by document
- overview, triage, runs, and workspace routes each render typed data and distinct empty/not-ready/error states
- workspace route restores selected run/page context from URL params (`runId`, `page`, and optional `lineId`/`tokenId`) after reload
- RBAC and audit are correct
- inference rollout can use existing transcription route and projection contracts without adding a second route family
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

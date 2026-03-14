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
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-05-privacy-redaction-workflow-v1.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`
3. Then review the current repository generally — transcription projections, token-anchor availability, privacy-related schemas if any, project/document routes, typed contracts, audit code, browser tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second privacy route family, a second run model, or conflicting review-projection semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for privacy IA, route ownership, run-model semantics, append-only review events, safe-preview posture, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that privacy review is run-based, auditable, token-aware when possible, and never leaks raw preview or object-store paths.

## Objective
Stand up privacy-review information architecture, work queues, run models, and safe-preview routes.

This prompt owns:
- the canonical privacy route family
- privacy run, finding, page-review, run-review, output, and projection models
- overview, triage, runs, compare, events, and workspace shells
- safe-preview and preview-status route scaffolding
- append-only page and run event timelines
- run-approval and activation prerequisites
- typed privacy APIs and shell integration
- audit and RBAC for the privacy tranche

This prompt does not own:
- direct-identifier detection logic
- masking decision engine
- dual-control completion workflow beyond the baseline review scaffolding defined in this iteration
- export/release workflows
- a second privacy shell or route family

## Phase alignment you must preserve
From Phase 5 Iteration 5.0:

### Required routes
- `/projects/:projectId/documents/:documentId/privacy`
  - tabs:
    - `Overview`
    - `Triage`
    - `Runs`
- `/projects/:projectId/documents/:documentId/privacy/runs/:runId`
- `/projects/:projectId/documents/:documentId/privacy/runs/:runId/events`
- `/projects/:projectId/documents/:documentId/privacy/workspace?page={pageNumber}&runId={runId}&findingId={findingId}&lineId={lineId}&tokenId={tokenId}`
- `/projects/:projectId/documents/:documentId/privacy/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}&page={pageNumber}&findingId={findingId}&lineId={lineId}&tokenId={tokenId}`

### Required overview behavior
- summary cards for the active run:
  - findings by category
  - unresolved findings
  - pages blocked for review
  - safeguarded-preview readiness
- primary CTA: `Create privacy review run`
- overflow actions:
  - `Compare runs`
  - `Open active workspace`
  - `Complete review`
- overview cards and workspace entry resolve through the explicit active-run projection

### Required triage behavior
Columns:
- page number
- findings
- unresolved items
- review status
- last reviewed by

Filters:
- category
- unresolved only
- direct identifiers only

Row selection opens a details drawer with:
- page preview
- top findings
- `Open in workspace`

### Required workspace shell
- left rail: page thumbnails and review status
- center canvas: page image with line or span highlight overlay
- right panel: transcript and findings list
- top toolbar:
  - previous / next page
  - `Next unresolved`
  - show / hide highlights
  - `Show safeguarded preview`

### Required tables
Implement or reconcile:
- `redaction_runs`
- `redaction_findings`
- `redaction_area_masks`
- `redaction_decision_events`
- `redaction_page_reviews`
- `redaction_page_review_events`
- `redaction_run_reviews`
- `document_redaction_projections`
- `redaction_run_review_events`
- `redaction_outputs`

Use the exact field sets from Phase 5.0, including:
- policy snapshot capture on `redaction_runs`
- append-only event rows
- approved-run locking semantics
- active-run projections
- explicit `redaction_outputs.status = PENDING | READY | FAILED | CANCELED`

### Required APIs
Implement or refine the canonical Phase 5.0 surface, including:
- `GET /projects/{projectId}/documents/{documentId}/privacy/overview`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/active`
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/status`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/review`
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/start-review`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/events`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/cancel`
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/activate`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/findings`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/review`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/events`
- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/findings/{findingId}`
- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/review`
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/complete-review`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/preview-status`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/preview`
- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/area-masks/{maskId}`

### Required RBAC
- `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, and `ADMIN` can view privacy runs and surfaces
- `PROJECT_LEAD`, `REVIEWER`, or `ADMIN` are required to create, cancel, activate, start/complete run review, resolve findings, update page reviews, and update area masks

### Required audit events
Use or reconcile the Phase 5.0 event set, including:
- `REDACTION_RUN_CREATED`
- `REDACTION_RUN_STARTED`
- `REDACTION_RUN_FINISHED`
- `REDACTION_RUN_FAILED`
- `REDACTION_RUN_CANCELED`
- `REDACTION_ACTIVE_RUN_VIEWED`
- `REDACTION_RUN_ACTIVATED`
- `PRIVACY_TRIAGE_VIEWED`
- `PRIVACY_WORKSPACE_VIEWED`
- `REDACTION_FINDING_DECISION_CHANGED`
- `REDACTION_PAGE_REVIEW_UPDATED`
- `REDACTION_PAGE_REVIEW_VIEWED`
- `REDACTION_PAGE_EVENTS_VIEWED`
- `REDACTION_RUN_REVIEW_OPENED`
- `REDACTION_RUN_REVIEW_CHANGES_REQUESTED`
- `REDACTION_RUN_REVIEW_COMPLETED`
- `PRIVACY_OVERVIEW_VIEWED`
- `PRIVACY_RUN_VIEWED`
- `REDACTION_RUN_STATUS_VIEWED`
- `REDACTION_RUN_REVIEW_VIEWED`
- `REDACTION_RUN_EVENTS_VIEWED`
- `REDACTION_COMPARE_VIEWED`
- `SAFEGUARDED_PREVIEW_REGENERATED`
- `SAFEGUARDED_PREVIEW_STATUS_VIEWED`
- `SAFEGUARDED_PREVIEW_ACCESSED`
- `SAFEGUARDED_PREVIEW_VIEWED`

## Implementation scope

### 1. Canonical privacy route family
Implement or refine the route family exactly under the project/document scope.

Requirements:
- no second privacy route family
- shell/breadcrumb/page-header coherence
- deep-link-safe route loading
- tabs for Overview / Triage / Runs
- compare and workspace routes respect the same shell and adaptive-state model
- route parameters remain bounded and browser-safe

### 2. Privacy run and review schema
Implement or reconcile the Phase 5.0 schema exactly enough to support the shells and later detector/decision work.

Requirements:
- run, finding, page-review, run-review, output, and projection models are canonical
- append-only event tables are authoritative for history
- approved-run locking semantics are represented
- active-run projection exists without mutating historical rows
- no fake detector output is inserted just to satisfy UI shells

### 3. Overview, triage, and runs surfaces
Implement or refine the overview, triage, and runs shell.

Requirements:
- overview cards use active projection truthfully
- triage is table-first and dense
- runs list and run detail are calm and exact
- row selection and details drawer are keyboard-safe
- empty/loading/error/not-ready states remain honest
- no flashy “security dashboard” styling

### 4. Workspace shell
Implement or refine the privacy workspace shell.

Requirements:
- left rail page thumbnails and review status
- center image with highlight overlay shell
- right panel with transcript and findings list
- toolbar with previous/next page, next unresolved, show/hide highlights, safeguarded preview toggle
- bounded single-fold layout
- truthful not-ready state when findings/preview are not yet populated

### 5. Run review and event timelines
Implement or refine the event and review surfaces.

Requirements:
- merged append-only run timeline ordering follows the documented stable order
- page-scoped event views do not reconstruct history from mutable projections
- start-review and complete-review scaffolding are truthful and typed
- approved-run locking rules are modeled even before full detector/decision rollout

### 6. Safe-preview routes
Implement or refine safe-preview and preview-status routes as controlled-only internal read paths.

Requirements:
- preview bytes stream through authenticated internal endpoints only
- no raw object-store URLs
- preview-status is explicit
- empty/not-ready/failed states are representable without lying

### 7. Projection and activation scaffolding
Implement or refine:
- `document_redaction_projections.active_redaction_run_id`
- activation prerequisites:
  - run review approved
  - page preview projections ready
- activating a redaction run updates the active projection without mutating historical rows
- activating a redaction run also marks `document_transcription_projections.downstream_redaction_state = CURRENT` for the exact transcription basis used by that run

### 8. Audit and browser quality
Use the canonical audit path and add shell/browser coverage.

Requirements:
- audit events flow through the canonical system
- visual regression for Overview, Triage, and Workspace shell states
- accessibility scans for those surfaces
- no second browser-test stack

### 9. Documentation
Document:
- privacy IA and route ownership
- schema and projection ownership
- append-only event-timeline semantics
- safe-preview route rules
- what Prompt 60–62 deepen next

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- Phase 5.0 schema/migrations
- typed privacy APIs
- event timeline and projection logic
- tests

### Web
- privacy overview
- privacy triage
- runs list/detail shells
- workspace shell
- compare/events shells
- safe-preview route integration

### Docs
- privacy IA and route contract doc
- privacy run/review/projection model doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small tabs/table/drawer/workspace-shell refinements are needed
- `/workers/**` only if a tiny queue scaffold is required for truthful `QUEUED` creation
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- detector logic
- masking decision engine
- dual-control completion logic beyond baseline scaffolding
- export/release workflows
- a second privacy shell
- public preview delivery

## Testing and validation
Before finishing:
1. Verify the privacy route family exists and fits the canonical shell.
2. Verify overview, triage, runs, compare, events, and workspace routes reload safely.
3. Verify run and page event timelines are append-only and ordered deterministically.
4. Verify RBAC boundaries for view vs create/cancel/activate/start-review/complete-review/finding-resolution/page-review/area-mask actions.
5. Verify approved runs reject later mutation paths according to the modeled locking rules.
6. Verify safe-preview routes remain authenticated and do not leak raw object-store paths.
7. Verify activation updates the active redaction projection coherently.
8. Verify audit events are emitted through the canonical path.
9. Verify visual and accessibility shell gates pass.
10. Verify docs match the implemented Phase 5.0 behavior.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the privacy IA and route family are real
- the run/review/projection/event models are real
- safe-preview routes are real and controlled
- shell routes expose documented extension points for detector and decision modules without route-family renaming
- RBAC and audit tests cover privacy run create, view, and decision actions across required roles
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

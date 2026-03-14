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
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-02-preprocessing-pipeline-v1.md`
3. Then review the current repository generally — preprocessing routes, run models, page result models, compare/viewer integrations, typed API client, shared UI primitives, audit code, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second quality surface, a second rerun flow, or a conflicting profile-selection system.

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
- `/phases` wins for quality-tab ownership, table columns, filter semantics, rerun behavior, role boundaries, and acceptance logic.
- Official docs win only for implementation mechanics.
- Keep the triage surface dense, operational, and filter-first. Do not turn it into a noisy dashboard or a second viewer.

## Objective
Build document-quality triage queues, hotspot filtering, and targeted rerun flows for operators.

This prompt owns:
- the document-quality tab
- hotspot and quality filtering
- per-page quality details drawer
- targeted page selection for reruns
- rerun wizard
- compare-runs action integration
- partial-run targeting on the backend
- run-comparison API for warning and metric deltas
- operator-grade triage ergonomics for weak pages

This prompt does not own:
- advanced aggressive-profile behavior beyond safe profile selection
- full compare polish beyond what is needed to support triage
- later layout/transcription/privacy workflows
- global cross-document quality dashboards outside the current document scope

## Phase alignment you must preserve
From Phase 2 Iteration 2.3:

### Iteration Objective
Enable fast triage of weak pages and selective reruns without reprocessing full documents.

### Document Quality tab
Table-first design with columns:
- page number
- warnings
- skew
- blur score
- DPI
- status

Filters:
- warning type
- skew range
- blur threshold
- failed only

Additional behavior:
- bulk page selection
- primary CTA: `Re-run preprocessing`
- secondary action: `Compare runs`
- details drawer:
  - before/after mini previews
  - metrics breakdown
  - `Open in viewer`

### Re-run wizard
1. choose scope (whole document or selected pages)
2. choose profile (`Conservative`, `Balanced`, `Aggressive`)
3. confirm and run

Rule:
- advanced parameters remain collapsed by default

### Backend requirements
- partial run targeting (`target_page_ids` in params)
- profile system with baked profiles and explicit expanded params
- run comparison API (per-page run list and warning deltas)
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/rerun`
  - accepts optional page subset and profile override
  - expands to concrete params
  - creates a new run without mutating the source run
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`
  - returns per-page warning deltas, metric deltas, and output availability
- compare reads emit `PREPROCESS_COMPARE_VIEWED`

### Phase role boundaries to preserve
- `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, `ADMIN` can view quality and runs
- only `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can create, rerun, or cancel preprocessing runs

### Required tests
- profile expansion correctness (`profile -> concrete params`)
- subset targeting processes only selected pages
- selected-page run produces outputs only for requested subset
- quality filters and bulk selection work
- rerun from selected pages creates new run
- viewer can select newly created run

## Implementation scope

### 1. Document quality tab
Implement or refine the quality tab inside the canonical preprocessing route family.

Requirements:
- table-first layout
- exact columns from the phase contract
- calm, dense presentation
- bounded list region
- route-safe empty/loading/error/no-results states
- works cleanly in the canonical shell
- supports deep-link entry via `/preprocessing/quality`

### 2. Hotspot filtering and queue ergonomics
Implement crisp triage filtering.

Requirements:
- warning-type filter
- skew-range filter
- blur-threshold filter
- failed-only filter
- active filter visibility
- predictable URL-state ownership where it helps reload/back-forward/share behavior
- fast bulk selection workflow
- no giant advanced-filter wall

The table should make it easy to isolate “bad pages first” without becoming visually noisy.

### 3. Quality details drawer
Implement or refine the per-page details drawer.

Requirements:
- before/after mini previews
- metrics breakdown
- current warning set
- status
- `Open in viewer`
- bounded internal scrolling
- focus trap and return focus
- no page-height blowout
- works cleanly with row selection

If compare mini previews require already-existing compare artefacts, use the canonical asset and compare paths rather than inventing ad hoc image fetches.

### 4. Bulk page selection
Implement restrained bulk-selection mechanics for quality triage.

Requirements:
- select individual pages
- select multiple filtered pages
- clear selection
- visible selection count
- selection survives predictable in-table interactions where sensible
- unauthorized users do not see actionable rerun controls
- no unsupported destructive bulk semantics

### 5. Re-run wizard
Implement or refine the rerun wizard.

Requirements:
- step 1: choose scope
  - whole document
  - selected pages
- step 2: choose profile
  - `Conservative`
  - `Balanced`
  - `Aggressive`
- step 3: confirm and run
- advanced parameters remain collapsed by default
- keyboard-safe flow
- calm and exact copy
- no wizard theater or fake optimistic success

If the repo already has compare, runs, and profile primitives in the current implementation, reuse them.

### 6. Partial-run targeting backend
Implement or refine partial-run targeting.

Requirements:
- support `target_page_ids` in params
- subset reruns process only the selected pages
- source run remains immutable
- new run is created with:
  - new run ID
  - preserved lineage
  - expanded params
  - recomputed params hash
- target subset is explicit and queryable later
- no accidental processing of non-selected pages

### 7. Profile expansion and rerun behavior
Implement the rerun API correctly.

Requirements:
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/rerun`
- accepts optional page subset
- accepts profile override
- expands profile to concrete params
- persists expanded params
- creates a new run without mutating the source run
- uses canonical run lineage and projection rules
- respects role boundaries

### 8. Run comparison API and Compare Runs action
Implement or refine:
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`

Requirements:
- returns per-page warning deltas
- returns metric deltas
- returns output availability
- typed contract
- compare reads emit `PREPROCESS_COMPARE_VIEWED`
- the quality tab's `Compare runs` action opens the canonical compare surface with `baseRunId` and `candidateRunId` in route/query state

### 9. Viewer handoff
Make the rerun-and-review loop consistent.

Requirements:
- rerun from selected pages creates a new run
- newly created run can be selected in viewer/preprocess compare surfaces
- `Open in viewer` from the quality drawer preserves consistent page context
- the user is not forced into unrelated routes to verify results

### 10. Documentation
Document:
- quality tab ownership
- filter semantics
- selected-page rerun semantics
- profile selection behavior
- run comparison API contract
- how later work may deepen triage without rewriting the information architecture

## Required deliverables

### Backend / contracts
- partial-run targeting support
- rerun endpoint refinement
- run comparison API
- typed quality/compare contracts
- tests

### Web
- preprocessing quality tab
- hotspot filtering
- bulk selection
- details drawer
- rerun wizard
- compare-runs integration
- viewer handoff

### Docs
- quality triage and selective rerun doc
- compare-runs and subset-targeting contract doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**` only if a small run-subset scheduling refinement is needed
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small table/drawer/wizard/metrics-preview refinements are needed
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- broad cross-document quality dashboards
- aggressive advanced-profile behavior beyond safe selection
- full compare-surface redesign
- layout/transcription/privacy workflows
- a second rerun wizard or second compare route

## Testing and validation
Before finishing:
1. Verify profile expansion correctness (`profile -> concrete params`).
2. Verify subset targeting processes only selected pages.
3. Verify selected-page runs create outputs only for the requested subset.
4. Verify quality filters and bulk selection work.
5. Verify rerun from selected pages creates a new run.
6. Verify viewer/preprocess compare can select the newly created run via route/query state without manual refresh.
7. Verify role boundaries for view vs rerun actions.
8. Verify compare reads emit the expected audit event.
9. Verify docs match the actual quality/rerun/compare behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the quality triage surface is real
- hotspot filtering is real
- targeted reruns are real
- the compare-runs flow is real
- role-aware operator workflows are consistent
- the UI stays dense, dark, calm, and exact
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

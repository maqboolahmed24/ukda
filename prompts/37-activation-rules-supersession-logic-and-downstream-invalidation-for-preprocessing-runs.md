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
   - `/phases/phase-02-preprocessing-pipeline-v1.md`
   - `/phases/phase-03-layout-segmentation-overlays-v1.md`
   - `/phases/phase-04-handwriting-transcription-v1.md`
3. Then review the current repository generally — preprocessing runs, projections, layout projections, transcription projections, typed contracts, web routes, current run/detail pages, audit code, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second activation model, a second supersession model, or hidden downstream invalidation rules scattered across the app.

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
- `/phases` wins for activation semantics, rerun lineage, explicit projections, downstream invalidation intent, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that active runs are explicit projections, historical rows remain immutable, and downstream phases must never silently keep using a stale preprocessing basis.

## Objective
Wire activation rules, supersession logic, and downstream invalidation for preprocessing runs.

This prompt owns:
- preprocess-run activation hardening
- supersession and attempt-lineage correctness
- explicit active-run projection behavior
- downstream invalidation signals for layout and transcription consumers
- activation-aware web surfaces
- typed contracts for active/current/stale basis reporting
- audit coverage for activation and projection reads
- cache invalidation and route refresh behavior for activation-sensitive surfaces

This prompt does not own:
- the preprocessing engine itself
- compare rendering
- quality triage UI beyond activation-aware updates
- layout segmentation or transcription feature work
- a second status model for later phases

## Phase alignment you must preserve
From Phase 2, Phase 3, and Phase 4:

### Preprocessing run rules
Preserve or reconcile:
- `preprocess_runs`
  - `parent_run_id`
  - `attempt_number`
  - `superseded_by_run_id`
  - `profile_id`
  - `params_json`
  - `params_hash`
  - `pipeline_version`
  - `container_digest`
  - `status`
- `document_preprocess_projections`
  - `active_preprocess_run_id`
  - `active_profile_id`
  - `updated_at`

Rules:
- reruns append a new `preprocess_runs` row
- reruns increment `attempt_number`
- reruns preserve `parent_run_id`
- reruns record the forward lineage link through `superseded_by_run_id`
- only `SUCCEEDED` runs may be activated
- activation updates `document_preprocess_projections.active_preprocess_run_id` without mutating historical run rows
- overview, quality, and viewer-default variant reads resolve through the active preprocess projection, not “latest successful”

### Downstream Phase 3 dependency
Phase 3 consumes `document_preprocess_projections.active_preprocess_run_id` as the canonical image input for layout segmentation.

Phase 3 also defines:
- `document_layout_projections.active_input_preprocess_run_id`
- `document_layout_projections.downstream_transcription_state`

### Downstream Phase 4 dependency
Phase 4 defines:
- `document_transcription_projections.active_preprocess_run_id`
- `document_transcription_projections.active_layout_run_id`
- `document_transcription_projections.downstream_redaction_state`

### Required downstream invalidation intent
When the active preprocessing run changes, downstream phases that were built against an older preprocess basis must not silently remain “current”.

This prompt must make that truth explicit and usable now, without inventing conflicting later-phase schemas.

## Implementation scope

### 1. Activation hardening
Implement or refine:
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/activate`

Requirements:
- only `SUCCEEDED` runs may be activated
- role boundaries stay correct:
  - view: `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, `ADMIN`
  - activate: `PROJECT_LEAD`, `REVIEWER`, `ADMIN`
- activating a run updates only the canonical projection
- no historical preprocess run row is rewritten to pretend it became the new truth
- activating an already-active run is handled safely and idempotently

### 2. Supersession and lineage correctness
Harden rerun lineage and supersession visibility.

Requirements:
- new reruns preserve `parent_run_id`
- `attempt_number` increments deterministically
- `superseded_by_run_id` on the superseded row is set exactly once to the newer run id
- historical runs remain immutable and queryable
- run list/detail surfaces can show:
  - active
  - superseded
  - current attempt
  - historical attempt
- no second lineage graph or alternate supersession interpretation is introduced

### 3. Downstream invalidation model
Implement explicit downstream basis-status resolution for preprocessing activation.

Requirements:
- when a layout projection exists, compare:
  - current `document_preprocess_projections.active_preprocess_run_id`
  - `document_layout_projections.active_input_preprocess_run_id`
- when they differ, layout basis is surfaced as `STALE`
- when no layout projection exists yet, layout basis is surfaced as `NOT_STARTED`
- when they match, layout basis is surfaced as `CURRENT`

For transcription:
- when a transcription projection exists, compare:
  - current `document_preprocess_projections.active_preprocess_run_id`
  - `document_transcription_projections.active_preprocess_run_id`
- when they differ, transcription basis is surfaced as `STALE`
- when no transcription projection exists yet, transcription basis is surfaced as `NOT_STARTED`
- when they match, transcription basis is surfaced as `CURRENT`

Important:
- prefer computed or projection-aligned basis-state resolution over inventing speculative new mutation-heavy DB fields
- do not rewrite layout or transcription historical rows merely because the preprocess active run changed
- do not claim downstream work is current if it was built against an older preprocess basis

### 4. Canonical active-run and downstream-impact APIs
Implement or refine the cleanest existing API path so the frontend can read:
- active preprocess run
- supersession lineage
- downstream layout basis state
- downstream transcription basis state

Prefer extending the current canonical preprocess run detail or active-run endpoints over inventing parallel endpoints.
Good targets include:
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/active`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}`
- `GET /projects/{projectId}/documents/{documentId}/preprocessing/overview`

Requirements:
- typed contracts
- explicit active/non-active flags
- explicit downstream impact summary
- no hidden “latest successful” fallback behavior
- browser consumers should not need to reverse-engineer basis staleness client-side from raw row data alone

### 5. Web activation and lineage surfaces
Refine the preprocessing runs and overview UI.

Requirements:
- active run is clearly identified
- superseded runs are clearly identified
- activation action appears only when the role and run state allow it
- run detail shows:
  - profile
  - params hash
  - attempt number
  - supersession chain
  - downstream impact summary
- overview and quality surfaces reflect the active projection accurately
- switching the active run updates:
  - preprocessing overview
  - quality defaults
  - viewer default preprocessed variant resolution where relevant
- no noisy “version management” UI; keep it calm and exact

### 6. Client cache and route refresh invalidation
Activation changes canonical defaults.
Wire client data invalidation through the canonical query keys and refresh flows.

Requirements:
- activation invalidates the canonical preprocess active-run queries
- activation invalidates overview/quality/default-variant readers that depend on the active projection
- layout and transcription summary readers refresh when their basis-state changes
- no stale cache leaves the UI pretending an old preprocess run is still the default

Use the current canonical data/query layer from the repo.
Do not add a second cache system.

### 7. Audit alignment
Use the existing audit path and emit or reconcile:
- `PREPROCESS_RUN_ACTIVATED`
- `PREPROCESS_ACTIVE_RUN_VIEWED`
- `PREPROCESS_RUN_VIEWED`

If the repo already has a consistent event taxonomy for downstream basis or projection reads, extend it carefully. Do not create a second audit path.

### 8. Documentation
Document:
- activation rules
- supersession rules
- how active preprocess projections work
- how downstream layout/transcription basis-state is resolved
- how future phases must consume the active preprocess run without guessing
- what this prompt does not mutate in historical lineage

## Required deliverables

### Backend / contracts
- activation hardening
- supersession-lineage correctness
- active-run and downstream-basis typed contracts
- tests

### Web
- runs list/detail activation refinement
- active-run and superseded-state presentation
- downstream impact summary presentation
- activation-aware cache refresh behavior

### Docs
- preprocess activation and downstream invalidation doc
- supersession and active-projection contract doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small run-detail/status presentation refinements are needed
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- preprocessing engine changes
- compare rendering changes
- layout or transcription feature implementation
- destructive cleanup of historical runs
- “latest successful” shortcuts
- a second projection model

## Testing and validation
Before finishing:
1. Verify only `SUCCEEDED` preprocess runs can be activated.
2. Verify activating a run updates only the canonical preprocess projection.
3. Verify rerun lineage preserves `parent_run_id`, `attempt_number`, and `superseded_by_run_id` correctly.
4. Verify historical runs remain immutable and queryable after activation.
5. Verify layout basis state resolves to `CURRENT`, `STALE`, or `NOT_STARTED` correctly.
6. Verify transcription basis state resolves to `CURRENT`, `STALE`, or `NOT_STARTED` correctly.
7. Verify activation invalidates dependent web queries and the affected surfaces refresh without stale active-run state.
8. Verify audit events are emitted through the canonical path.
9. Verify docs match the actual activation, supersession, and downstream invalidation behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- preprocess activation is explicit and hardened
- supersession lineage is correct and visible
- downstream layout/transcription basis-state is explicit
- no historical run rows are silently rewritten
- the web app reflects active/superseded/current/stale states accurately and without contradictory badges or defaults
- activation, supersession, and downstream invalidation rules are documented and enforced by automated tests
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

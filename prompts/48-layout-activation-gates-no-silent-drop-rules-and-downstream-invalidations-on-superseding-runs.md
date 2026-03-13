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
   - `/phases/phase-03-layout-segmentation-overlays-v1.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`
   - `/phases/phase-04-handwriting-transcription-v1.md`
3. Then review the current repository generally — layout runs, layout versions, recall checks, rescue candidates, layout projections, transcription projections, typed contracts, web surfaces, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second activation-gate path, a second stale-basis model, or conflicting downstream invalidation rules.

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
- `/phases` wins for no-silent-drop rules, recall gating, superseding-run behavior, downstream transcription invalidation, and activation semantics.
- Official docs win only for implementation mechanics.
- Preserve the normative rule that no layout run may be promoted while recall status is unresolved on any page, and no downstream state may remain “current” when its basis has been superseded.

## Objective
Enforce layout activation gates, no-silent-drop rules, and downstream invalidations on superseding runs.

This prompt owns:
- hard activation gating for layout runs
- superseding-run and superseding-version downstream invalidation behavior
- no-silent-drop enforcement in activation and active-basis resolution
- layout-to-transcription stale/current/not-started projection logic
- gate-blocker surfaces in layout runs/detail/overview
- typed blocker and downstream-impact contracts
- cache invalidation and route refresh behavior for activation-sensitive UI
- regression coverage for gate failures and stale-basis transitions

This prompt does not own:
- new recall-check algorithms
- rescue transcription
- transcription inference
- a second projection model
- silent auto-promotion of historical or incomplete runs

## Phase alignment you must preserve
From Phase 3 and the normative patch:

### No-silent-drop rule
- every page must have explicit `page_recall_status`
- no run can be promoted if any page lacks explicit recall-status resolution

### Page recall-status classes
- `COMPLETE`
- `NEEDS_RESCUE`
- `NEEDS_MANUAL_REVIEW`

### Existing layout projection rules
- `document_layout_projections.active_layout_run_id`
- `document_layout_projections.active_input_preprocess_run_id`
- `document_layout_projections.downstream_transcription_state` (`NOT_STARTED | CURRENT | STALE`)
- `downstream_transcription_invalidated_at`
- `downstream_transcription_invalidated_reason`

### Existing run/version lineage rules
- layout runs are append-only
- layout versions are append-only
- supersession is explicit through forward links
- historical rows remain immutable

### Required activation state
- only `SUCCEEDED` runs may be activated
- unresolved recall status blocks activation
- activating a layout run marks downstream transcription `STALE` unless transcription has never started, in which case `NOT_STARTED`
- editing pages on the active layout run also invalidates downstream transcription basis accurately

## Implementation scope

### 1. Canonical activation gate evaluation
Implement or refine the activation-gate evaluator for layout runs.

Requirements:
- only `SUCCEEDED` runs may activate
- any page lacking explicit recall status blocks activation
- gate results are explicit and typed
- blockers are inspectable by the UI
- no silent fallback to “good enough”
- no hidden override path

Good blocker examples:
- unresolved recall status
- missing required active page version metadata if the current repo depends on it
- other canonically required readiness checks already present in the repo

### 2. Superseding-run invalidation
Enforce downstream invalidation when a newer layout basis supersedes the old one.

Requirements:
- activating a different layout run updates the canonical layout projection
- downstream transcription state becomes:
  - `NOT_STARTED` if no transcription basis exists yet
  - `STALE` if an active transcription basis exists and points to an older layout basis
  - `CURRENT` only when the active transcription projection matches the active layout basis
- superseded historical runs remain readable but not implicitly current
- no UI surface guesses “latest successful” instead of reading the explicit projection

### 3. Superseding-version invalidation
Handle page-level edits on the active layout run consistently.

Requirements:
- when a page save creates a new active layout version on the active layout run, downstream transcription basis becomes `STALE`
- invalidation timestamp and reason are persisted
- stale reason distinguishes activation-based invalidation from manual-edit invalidation where possible
- historical versions remain immutable

### 4. Canonical active-basis and blocker APIs
Expose the cleanest canonical read surfaces for:
- current active layout run
- activation blockers for a candidate run
- downstream transcription basis state
- invalidation reason and timestamp

Prefer extending existing active/detail/overview routes over inventing parallel APIs.

Requirements:
- typed contracts
- browser consumers do not need to reconstruct gate state from raw tables alone
- gate-blocker information is explicit
- downstream impact summary is explicit

### 5. Web gate-blocker and stale-basis surfaces
Refine the layout runs, run detail, and overview surfaces.

Requirements:
- activation controls are shown only to eligible roles
- blocked activation shows exact blockers
- active run and superseded runs are clearly identified
- downstream transcription state is visible and calm
- stale-basis reasons are legible without noisy warnings
- gate surfaces remain dense, exact, and operational

### 6. Client cache and route invalidation
Activation and invalidation change canonical defaults.

Requirements:
- activating a layout run invalidates active-run, overview, triage, workspace-default, and downstream-summary readers that depend on the layout projection
- page-save invalidation updates downstream-basis readers consistently
- stale UI cache never pretends an old basis is still current
- use the canonical query/cache layer already in the repo

### 7. Audit alignment
Use the canonical audit path.

At minimum emit or reconcile the cleanest existing coverage for:
- `LAYOUT_RUN_ACTIVATED`
- activation failures due to unresolved recall status
- downstream invalidation events already defined or present

Do not create a second audit path.

### 8. Regression gates
Add meaningful regression coverage.

At minimum cover:
- activation blocked when recall status is unresolved
- successful activation updates the layout projection
- activating a new layout run makes downstream transcription `STALE` when applicable
- no transcription yet yields `NOT_STARTED`
- manual page edit on active layout run also makes downstream transcription `STALE`
- superseded runs remain historical and readable

### 9. Documentation
Document:
- layout activation gate rules
- no-silent-drop enforcement
- superseding-run and superseding-version invalidation rules
- how downstream transcription basis state is resolved
- what Phase 4 must consume from these projections without guessing

## Required deliverables
### Backend / contracts
- activation-gate evaluator
- active-basis and blocker contracts
- downstream invalidation logic
- tests

### Web
- gate-blocker presentation
- stale/current/not-started projection surfaces
- activation-aware cache refresh behavior

### Docs
- layout activation gates and downstream invalidation doc
- no-silent-drop enforcement doc
- any README updates required for developer usage


## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small blocker/status presentation refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- new recall algorithms
- rescue transcription
- a second projection model
- silent auto-promotion
- transcription inference features
- rewriting historical runs or versions

## Testing and validation
Before finishing:
1. Verify unresolved recall status blocks activation.
2. Verify only `SUCCEEDED` runs can activate.
3. Verify successful activation updates the canonical layout projection.
4. Verify activating a new layout run marks downstream transcription `STALE` when applicable.
5. Verify absence of transcription basis yields `NOT_STARTED`.
6. Verify active-run page edits mark downstream transcription `STALE`.
7. Verify superseded runs and versions remain immutable and readable.
8. Verify gate blockers and stale reasons surface cleanly in the UI.
9. Verify docs match the implemented gate and invalidation behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- layout activation gates are real and enforced
- no-silent-drop behavior is enforced
- downstream transcription invalidation on superseding runs or versions is real
- UI surfaces reflect current/stale/not-started state accurately
- later transcription work can rely on explicit layout basis state
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

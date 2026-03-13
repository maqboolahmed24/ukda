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
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-03-layout-segmentation-overlays-v1.md`
   - `/phases/phase-04-handwriting-transcription-v1.md` for downstream stale-basis expectations only
3. Then review the current repository generally — layout workspace code, overlay contracts, layout run and version models, stable line/region IDs, artefact generation, transcription projection models, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second edit system, a second version-history model, or conflicting geometry-validation rules.

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
- `/phases` wins for edit-mode scope, append-only correction history, optimistic locking, downstream invalidation, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that each save creates a new immutable layout version and never mutates prior history.

## Objective
Add audited manual correction tools for regions, lines, geometry, and reading-order edits.

This prompt owns:
- the broad layout edit mode
- geometry editing tools for regions and lines
- line split/merge/delete and region assignment tools
- append-only page-level correction history
- optimistic-lock-safe save flow
- undo/redo stack
- downstream transcription invalidation on edits to the active layout run
- audit coverage and regression tests for correction tools

This prompt does not own:
- automatic segmentation inference
- recall-first rescue generation
- transcription logic
- multi-user real-time collaboration
- broad crop/context regeneration beyond what is required to keep edited pages accurate

## Phase alignment you must preserve
From Phase 3 Iteration 3.3:

### Iteration objective
Enable minimal but essential manual fixes for segmentation failure cases.

### Required web tools
Add `Edit mode` toggle (default off).

Tool modes:
- select/pan
- draw region polygon
- edit vertices
- draw baseline polyline (optional in v1)
- split line
- merge lines
- delete element
- assign region type

Required:
- undo/redo stack

Inspector editing:
- region properties:
  - type
  - include/exclude from reading order
- line properties:
  - assign to region
  - line order within region

### Required backend model
Persist edits as new layout version using append-only strategy:
- `layout_versions`
  - `id`
  - `run_id`
  - `page_id`
  - `base_version_id` (nullable)
  - `superseded_by_version_id` (nullable)
  - `version_kind` (`SEGMENTATION_EDIT | READING_ORDER_EDIT`)
  - `version_etag`
  - `page_xml_key`
  - `overlay_json_key`
  - `page_xml_sha256`
  - `overlay_json_sha256`
  - `created_by`
  - `created_at`

Rules:
- each save creates a new immutable `layout_versions` row
- each save updates `page_layout_results.active_layout_version_id` to the newest saved version for that page
- the prior version row is marked superseded through `superseded_by_version_id`

### Required API
- `PATCH /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/elements`
  - accepts operation list (`add | move | delete | retag` and related geometry operations) plus the caller’s current `version_etag`
  - applies against the current version
  - persists a new `layout_versions` row
  - returns new version metadata
  - rejects stale `version_etag` values with optimistic-lock conflict

### Required downstream invalidation
If the edited page belongs to the active layout run:
- set `document_layout_projections.downstream_transcription_state = STALE`
- persist `downstream_transcription_invalidated_at`
- persist a reason later phases can surface

### Required audit events
- `LAYOUT_EDIT_APPLIED`
- `LAYOUT_DOWNSTREAM_INVALIDATED`

## Implementation scope

### 1. Canonical edit mode
Implement or refine the canonical edit mode in the layout workspace.

Requirements:
- default off
- explicit mode toggle
- read-only and edit states are clearly distinct
- edit mode remains calm, dense, and professional
- no accidental edit activation through ordinary inspection clicks
- edit mode does not create a second workspace or second route family

### 2. Geometry editing tools
Implement the required tool modes.

At minimum support:
- select/pan
- draw region polygon
- edit vertices
- split line
- merge lines
- delete element
- assign region type

Optional in this prompt only if it fits the repository and remains consistent:
- draw baseline polyline

Requirements:
- geometry edits remain bounded and precise
- stable region/line IDs are preserved or regenerated according to the repo’s canonical rules
- invalid geometry is rejected safely
- cross-page edits are impossible
- no hidden mutation of the canonical source artefacts without version creation

### 3. Inspector editing
Implement or refine the inspector edit path.

Requirements:
- region properties:
  - type
  - include/exclude from reading order
- line properties:
  - assign to region
  - line order within region
- edits can be staged before save
- inspector and canvas remain in sync
- edit UX remains keyboard-safe and bounded
- no form clutter or giant side panels

### 4. Undo/redo stack
Implement or refine undo/redo.

Requirements:
- available only within the current page edit session
- clear save/discard model
- does not silently commit edits
- survives common in-session operations consistently
- integrates with pointer and keyboard interactions where useful
- unsaved state is visible but not noisy

### 5. Append-only save path
Use the canonical versioning model.

Requirements:
- every save creates a new immutable `layout_versions` row
- `page_layout_results.active_layout_version_id` updates to the new version
- `superseded_by_version_id` links to the replacement version
- no historical version row is mutated beyond the forward supersession link
- no in-place overwrite of PAGE-XML or overlay metadata pretending history changed

### 6. PATCH elements API
Implement or refine:
- `PATCH /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/elements`

Requirements:
- accepts operation list plus `version_etag`
- validates geometry and page ownership
- rejects stale writes with optimistic-lock conflict
- persists new version metadata
- returns enough typed information for the workspace to rehydrate cleanly
- does not allow cross-page or cross-document mutations

### 7. Artefact regeneration for edited pages
Edits affect downstream artefacts.

Requirements:
- write updated PAGE-XML
- regenerate overlay JSON cache
- regenerate affected line crops
- regenerate page thumbnail metadata
- regenerate context manifests for the edited page
- keep regeneration bounded to the edited page
- no unrelated pages are silently rewritten

### 8. Downstream invalidation
Harden the downstream-staleness behavior.

Requirements:
- if an edited page belongs to the active layout run, transcription basis becomes `STALE`
- invalidation timestamp and reason are persisted
- this happens through the canonical projection path, not a parallel flag
- UI surfaces can read and show the invalidation accurately
- no silent stale downstream basis remains marked current

### 9. Workspace and browser UX hardening
Refine the edit-mode UX.

Requirements:
- save and discard affordances are exact
- optimistic-lock conflict handling is calm and actionable
- focus remains visible
- no keyboard traps
- pointer + keyboard interactions remain consistent
- bounded single-fold layout stays intact
- inspector/canvas sync remains precise

### 10. Audit and tests
Use the canonical audit path and add coverage.

At minimum cover:
- add/move/delete operation tests
- invalid geometry rejection
- cross-page edit rejection
- optimistic-lock conflicts
- edit persistence after refresh
- reassign line to region and verify inspector/canvas sync
- downstream transcription state becomes `STALE` after editing an active layout run page

### 11. Documentation
Document:
- edit mode ownership
- append-only layout versioning
- `version_etag` and optimistic locking
- downstream transcription invalidation rules
- how later workspace-hardening work will further harden the workspace UX around these tools

## Required deliverables
### Backend / contracts
- layout versioning support
- PATCH elements API
- artefact regeneration path
- downstream invalidation path
- tests

### Web
- edit mode toggle
- geometry editing tools
- inspector editing
- undo/redo
- save/discard/conflict UX

### Docs
- layout edit mode and versioning doc
- downstream invalidation after layout edits doc
- any README updates required for developer usage


## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**` if a small artefact-regeneration helper is needed
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small workspace/edit-mode/undo-redo refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- full collaborative editing
- rescue/transcription logic
- a second version history model
- a second edit route or shell
- hidden silent edits without version creation

## Testing and validation
Before finishing:
1. Verify add/move/delete operations persist through append-only versioning.
2. Verify invalid polygons are rejected.
3. Verify cross-page edits are rejected.
4. Verify optimistic-lock conflicts are handled safely.
5. Verify draw region, save, refresh, and persistence work.
6. Verify reassigning a line to a region updates inspector and canvas consistently.
7. Verify editing a page on the active layout run marks downstream transcription state `STALE`.
8. Verify audit events are emitted through the canonical path.
9. Verify docs match the actual edit/versioning/invalidation behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- audited manual correction tools are real
- append-only layout versioning is real
- optimistic locking is real
- downstream transcription invalidation on active-run edits is real
- the workspace remains bounded, calm, and review-grade
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

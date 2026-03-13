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
   - `/phases/phase-04-handwriting-transcription-v1.md` for downstream context-window and anchor expectations only
3. Then review the current repository generally — layout routes, workspace code, PAGE-XML/overlay contracts, line/context artefacts, run models, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second reading-order model, a second page-version lineage path, or conflicting workspace ownership.

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
- `/phases` wins for reading-order rules, uncertainty handling, PAGE-XML ownership, workspace inspector behavior, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that reading order is generated when confidence is justified and explicitly withheld or marked unordered when ambiguity is high.

## Objective
Build reading-order inference with explicit uncertainty surfacing and reviewer override paths.

This prompt owns:
- auto reading-order inference v1
- reading-order uncertainty signals and explicit withheld-order behavior
- reading-order serialization into canonical layout artefacts
- inspector-based reviewer override for reading order only
- append-only reading-order versioning
- optimistic-lock-safe save flow
- context-window regeneration when reading order changes
- workspace inspector reading-order tab and tree view
- audit and regression coverage for reading-order updates

This prompt does not own:
- full region/line geometry editing
- broad edit-mode tooling for polygons and baselines
- reading-order crop generation beyond already-canonical artefacts
- transcription logic
- a second manual-edit system outside the canonical layout versioning path

## Phase alignment you must preserve
From Phase 3 Iteration 3.4:

### Iteration objective
Generate useful reading order when confident and safely withhold strict order when ambiguity is high.

### Backend rules
- build reading-order tree by layout groups
- detect likely columns from region geometry
- create ordered groups within high-confidence columns
- sort regions by vertical then horizontal progression per group
- use unordered groups or blank order when ambiguity exceeds threshold
- serialize reading order into PAGE-XML structures
- regenerate context-window manifests when reading-order changes affect neighboring line context

### Confidence signals
At minimum surface:
- column certainty
- overlap conflict score
- orphan line count
- non-text complexity indicators

### Versioning rule
Reading-order saves create a new `layout_versions` row rather than mutating prior PAGE-XML.

### API rule
Implement or refine:
- `PATCH /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/reading-order`
  - accepts reorder operations plus the caller’s current `version_etag`
  - persists a new layout version
  - returns updated reading-order metadata
  - rejects stale `version_etag` values with optimistic-lock conflict

### Workspace rule
In the workspace inspector, add a `Reading order` tab with:
- tree view
- drag/drop reorder
- ordered/unordered group toggle

### Audit event
- `LAYOUT_READING_ORDER_UPDATED` with reading-order metadata only

## Implementation scope

### 1. Canonical reading-order model
Implement or refine one canonical reading-order representation that is serialized into PAGE-XML and consumable by the workspace.

Requirements:
- no second hidden reading-order schema drifting separately from PAGE-XML
- tree/group structure is explicit
- uncertainty can be represented explicitly
- ordered and unordered groups are both supported
- references only existing persisted layout elements
- no duplicate indices within ordered groups

### 2. Auto reading-order inference v1
Implement the phase-defined inference path.

Requirements:
- infer likely columns from region geometry
- create reading-order groups where confidence is adequate
- sort regions within confident groups
- surface uncertainty explicitly rather than faking confidence
- avoid silently forcing a strict order in ambiguous pages
- preserve deterministic behavior for the same layout input/version/runtime

### 3. Uncertainty surfacing
Make ambiguity explicit across backend and UI.

Requirements:
- persist or expose the confidence signals in a typed way
- represent uncertain or blank order explicitly
- the workspace can show that order is withheld due to ambiguity
- no “best guess” is silently treated as definitive when thresholds are missed
- uncertainty remains inspectable and auditable

### 4. Append-only versioning for reading-order edits
Use the canonical layout versioning path.

Requirements:
- reading-order save creates a new `layout_versions` row
- prior rows remain immutable
- new row gets a new `version_etag`
- `page_layout_results.active_layout_version_id` updates to the newest saved version for that page
- the superseded version is linked through `superseded_by_version_id`
- do not create a separate version table only for reading order

If `layout_versions` does not exist yet, create the canonical model in the narrowest way needed so later layout-edit work can extend it instead of replacing it.

### 5. Reading-order patch API
Implement or refine:
- `PATCH /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/reading-order`

Requirements:
- accepts reorder operations
- accepts current `version_etag`
- validates references and ordering
- rejects stale writes with optimistic-lock conflict
- persists a new immutable version
- returns the new version metadata and updated reading-order summary
- respects role boundaries for edit-capable users only

### 6. Context-window regeneration
Reading-order changes affect downstream context.

Requirements:
- regenerate affected context-window manifests when reading order changes alter neighboring line context
- keep stable line IDs intact
- regenerate only the necessary affected artefacts for the edited page
- no unrelated page artefacts are silently rewritten

### 7. Workspace inspector integration
Implement the reading-order tab inside the canonical layout workspace.

Requirements:
- tree view
- drag/drop reorder
- ordered/unordered group toggle
- clear uncertainty presentation
- calm, dense UI
- no vertical shell blowout
- narrow-window behavior remains consistent
- focus remains visible and keyboard-safe

### 8. Reviewer override path
Implement the minimal manual override path for reading order only.

Requirements:
- reviewer-capable roles can reorder items
- users can explicitly retain unordered state where confidence is low
- save flow is exact and auditable
- unsaved changes are surfaced clearly but calmly
- no broad geometry editing tools in this prompt

### 9. Audit and tests
Use the canonical audit path and add regression coverage.

At minimum cover:
- reading-order tree validity
- no duplicate indices in ordered groups
- references only existing regions
- uncertain-layout threshold triggers blank/unordered handling
- manual reorder persists after save/refresh
- PAGE-XML reflects updated reading order
- optimistic-lock conflicts are handled safely

### 10. Documentation
Document:
- reading-order inference rules
- uncertainty semantics
- how ordered vs unordered groups work
- how reading-order versioning works
- how later layout-edit work can extend the same versioning model into broader layout editing

## Required deliverables
### Backend / contracts
- reading-order inference logic
- reading-order versioning support
- PATCH reading-order API
- typed reading-order and confidence contracts
- tests

### Web
- workspace inspector reading-order tab
- drag/drop reorder flow
- uncertainty presentation
- save/conflict handling

### Docs
- reading-order inference and uncertainty doc
- reading-order versioning and override doc
- any README updates required for developer usage


## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**` if a tiny helper is needed for context-window regeneration
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small tree/drag/drop/inspector refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- full geometry editing tools
- region or line merge/split tooling beyond reading-order-only changes
- broad edit mode
- transcription logic
- a second layout versioning system
- fake certainty when layout ambiguity is high

## Testing and validation
Before finishing:
1. Verify reading-order trees reference only existing regions.
2. Verify ordered groups contain no duplicate indices.
3. Verify uncertainty thresholds produce unordered or blank-order handling.
4. Verify manual reorder persists after save/refresh.
5. Verify PAGE-XML reflects updated reading order.
6. Verify stale `version_etag` values are rejected safely.
7. Verify context-window manifests are regenerated when neighboring order changes.
8. Verify the workspace reading-order tab is keyboard-safe and bounded.
9. Verify docs match the implemented inference and override behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- reading-order inference is real
- uncertainty is explicit and not hidden
- reviewer override exists for reading order
- append-only versioning is used
- PAGE-XML remains canonical
- reading-order outputs are versioned and exposed through typed contracts consumable by manual-correction workflows
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

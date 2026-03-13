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
   - `/phases/phase-04-handwriting-transcription-v1.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`
   - `/phases/phase-05-privacy-redaction-workflow-v1.md` for downstream token/highlight attachment expectations only
3. Then review the current repository generally — primary transcription outputs, fallback outputs, line/context artefacts, rescue candidates, workspace route semantics, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second token-anchor model, a second source-reference system, or conflicting deep-link semantics.

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
- `/phases` wins for stable token IDs, geometry requirements, source-kind semantics, rescue provenance, and downstream highlight/masking expectations.
- Official docs win only for implementation mechanics.
- Preserve the rule that promoted transcription runs must expose stable token IDs with geometry and source links suitable for exact downstream highlight and masking.

## Objective
Materialize token anchors, geometry, source references, and rescue provenance end to end.

This prompt owns:
- stable token-anchor materialization from transcription output
- token geometry and source-reference persistence
- source-kind coverage for lines, rescue candidates, and page windows
- stable token IDs suitable for deep-linking and downstream privacy/search use
- token and line APIs for the workspace
- activation-gate satisfaction for token-anchor readiness
- rescue provenance carrying through into transcription token outputs
- regression coverage for token-anchor integrity

This prompt does not own:
- manual correction UI
- normalised transcript layers
- privacy masking decisions
- search indexing
- broad downstream highlight UI outside the transcription workspace

## Phase alignment you must preserve
From Phase 4 Iteration 4.0 and 4.1:

### Required token results
Use or reconcile `token_transcription_results`:
- `run_id`
- `page_id`
- `line_id` (nullable)
- `token_id`
- `token_index`
- `token_text`
- `token_confidence`
- `bbox_json` (nullable)
- `polygon_json` (nullable)
- `source_kind` (`LINE | RESCUE_CANDIDATE | PAGE_WINDOW`)
- `source_ref_id`
- `projection_basis` (`ENGINE_OUTPUT | REVIEW_CORRECTED`)
- `created_at`
- `updated_at`

### Required primary flow rule
- materialize token-level anchors (`token_id`, geometry, source link) for downstream search and redaction
- route schema or anchor-validation failures to fallback handling instead of silently persisting invalid text

### Required activation prerequisite
- activating a transcription run requires token-anchor materialization for pages not marked `NEEDS_MANUAL_REVIEW` by Phase 3 recall status

### Required workspace route semantics
The workspace route already reserves:
- `lineId`
- `tokenId`
- `sourceKind`
- `sourceRefId`

Those parameters must become accurate, stable, and deep-link-safe.

## Implementation scope

### 1. Canonical token-anchor model
Implement or refine one canonical token-anchor materialization path.

Requirements:
- no second token store
- token IDs are stable and deterministic for a given persisted transcript version/output
- tokens are attached to the correct page and line when a line anchor exists
- rescue and page-window sources use explicit `source_kind` and `source_ref_id`
- `projection_basis = ENGINE_OUTPUT` for engine-created anchors

### 2. Geometry and source references
Persist geometry and provenance consistently.

Requirements:
- bbox and/or polygon geometry is persisted when available
- geometry remains valid and page-bounded
- line-backed tokens link to canonical line IDs
- rescue-backed tokens link to canonical rescue candidate or page-window references
- no fake line associations for rescue-only text
- no raw storage paths leak into source references

### 3. Stable token ID generation
Make token IDs trustworthy and reusable.

Requirements:
- stable within the canonical run/version basis
- deterministic for the same persisted output
- suitable for deep-linking, exact highlight, and downstream privacy/search attachment
- no ephemeral UI-only IDs
- no collisions within a page/run basis

### 4. Workspace and API integration
Implement or refine:
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/lines`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/tokens`

Requirements:
- typed contracts
- line and token payloads are sufficient for workspace highlight and scroll-to-context flows
- route/query deep links using `lineId`, `tokenId`, `sourceKind`, and `sourceRefId` become accurate
- no client-side reverse engineering from raw PAGE-XML required

### 5. Activation gating
Unlock or refine the token-anchor activation gate.

Requirements:
- for pages not marked `NEEDS_MANUAL_REVIEW`, token anchors must exist before run activation succeeds
- missing or invalid token anchors block activation explicitly
- gate failures are typed and UI-readable
- no run is silently promoted without stable token anchors where required

### 6. Rescue provenance end to end
Carry rescue-source provenance through the transcript outputs.

Requirements:
- rescue-derived outputs preserve `source_kind = RESCUE_CANDIDATE` or `PAGE_WINDOW` as appropriate
- `source_ref_id` points at the stable rescue or page-window source
- line-based and rescue-based tokens can coexist in the same page/run without ambiguity
- later work can use this to distinguish ordinary line transcription from rescue transcription

### 7. Audit and regression
Use the canonical audit path where needed and add regression coverage.

At minimum cover:
- stable token ID generation
- valid geometry bounds
- source-kind/source-ref correctness
- line-backed vs rescue-backed token integrity
- activation blocked when anchors are missing
- deep-link payload fidelity for `lineId`/`tokenId`
- no raw storage or secret-bearing references in token payloads

### 8. Documentation
Document:
- stable token-anchor rules
- geometry and source-kind semantics
- activation prerequisite semantics
- how later work consumes token anchors for:
  - correction refresh
  - privacy masking
  - search highlights
- what remains owned by later phases

## Required deliverables
### Backend / contracts
- canonical token-anchor materialization
- line and token APIs
- activation-gate refinement for token-anchor readiness
- tests

### Web
- accurate workspace deep-link and highlight integration for line/token/source context

### Docs
- token-anchor and source-reference contract doc
- activation prerequisite and downstream-use doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small line/token highlight refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- manual correction UI
- normalised transcript layers
- privacy decisioning
- search indexing
- a second token-anchor store
- fake line associations for rescue-only text

## Testing and validation
Before finishing:
1. Verify token IDs are stable and deterministic for the same persisted output.
2. Verify token geometry is valid and page-bounded when present.
3. Verify line-backed tokens reference valid line IDs.
4. Verify rescue-backed tokens preserve correct `source_kind` and `source_ref_id`.
5. Verify activation is blocked when required token anchors are missing.
6. Verify line and token APIs are typed and workspace-usable.
7. Verify workspace deep links using `lineId`, `tokenId`, `sourceKind`, and `sourceRefId` resolve consistently.
8. Verify no secret-bearing or raw storage references leak in token payloads.
9. Verify docs match the implemented token-anchor and provenance rules.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- token anchors expose deterministic `token_id` values reproducible for the same transcript version
- each token anchor stores validated geometry plus typed `source_kind` and `source_ref_id` references
- rescue provenance survives into transcript outputs
- activation attempts fail with typed blocker reasons when required token anchors are missing or invalid
- the workspace and later privacy/search phases have a stable anchor contract
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

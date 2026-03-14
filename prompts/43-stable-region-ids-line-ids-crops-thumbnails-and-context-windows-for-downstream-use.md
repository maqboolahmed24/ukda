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
   - `/phases/phase-04-handwriting-transcription-v1.md` for downstream stable-anchor and artefact expectations
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` for anchor and rescue-source expectations
3. Then review the current repository generally — layout outputs, PAGE-XML/overlay contracts, storage adapters, page/result models, typed contracts, workspace routes, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second ID scheme, a second crop/context artefact table, or conflicting downstream anchor ownership.

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
- `/phases` wins for stable line IDs, context-window artefacts, controlled storage layout, downstream transcription anchors, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that downstream transcription and rescue flows anchor to persisted layout artefacts, not ephemeral UI geometry.

## Objective
Materialize stable region IDs, line IDs, crops, thumbnails, and context windows for downstream use.

This prompt owns:
- stable region and line identity materialization
- page thumbnails, line crops, optional region crops, and per-line context windows
- the canonical `layout_line_artifacts` path and storage behavior
- API delivery of line artefact metadata
- stable downstream anchor contracts for transcription and rescue flows
- accurate page-result linkage to artefacts
- regression coverage for artefact reproducibility and validity

This prompt does not own:
- the transcription engine
- token anchor materialization
- rescue-candidate generation logic itself
- manual correction versioning
- layout workspace editing
- public asset delivery

## Phase alignment you must preserve
From Phase 3 Iteration 3.0 and 3.1:

### Required storage layout
Preserve or reconcile:
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}.xml`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}.json`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/thumbnail.png`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/lines/{line_id}.png`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/regions/{region_id}.png`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/context/{line_id}.json`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/manifest.json`

Region-crop path requirements apply when optional region crops are generated.

### Required derived artefact table
Implement or reconcile `layout_line_artifacts`:
- `run_id`
- `page_id`
- `line_id`
- `region_id` (nullable when the line is not associated to a persisted region)
- `line_crop_key`
- `region_crop_key` (nullable)
- `page_thumbnail_key`
- `context_window_json_key`
- `artifacts_sha256`

### Required stability rules
- stable line IDs and region IDs must remain reproducible from canonical layout output
- context-window generation preserves valid neighboring anchors and stable line IDs
- VLM-ready crops and context manifests are written only for valid PAGE-XML line anchors
- line crops, thumbnails, and context windows are the downstream source for later transcription and rescue flows
- original page images are not overwritten

### Required API
Implement or refine:
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/lines/{lineId}/artifacts`

Versioned history endpoints can be deepened later. Do not overbuild version browsing here unless the current repo already needs a small accurate read-only helper.

## Implementation scope

### 1. Stable ID materialization
Implement or refine stable region and line ID generation.

Requirements:
- IDs are derived deterministically from canonical layout output or a similarly stable strategy
- IDs remain stable across re-serialization of the same layout output
- IDs are suitable for downstream transcription anchoring
- IDs are present and identical in PAGE-XML and overlay representations for the same layout result
- no ad hoc UI-only IDs that drift from canonical layout artefacts

### 2. Page thumbnails
Implement or refine page-thumbnail generation for layout outputs.

Requirements:
- thumbnail is materialized at the canonical page thumbnail path
- thumbnail generation is deterministic and bounded
- thumbnail is tied to the layout run and page
- output remains controlled-only
- no public thumbnail URL path is introduced

### 3. Line crops and optional region crops
Implement or refine crop generation.

Requirements:
- line crops are generated only for valid canonical line anchors
- optional region crops are generated when region geometry supports them cleanly
- crop keys and hashes remain stable for the same underlying layout output
- crop generation does not mutate canonical source images
- failures are explicit and do not silently produce misleading crops

### 4. Context-window manifests
Implement or refine per-line context windows.

Requirements:
- context window ties the current line to neighboring anchors and page context
- manifest is persisted as JSON under the canonical storage path
- stable line IDs are preserved in the manifest
- neighboring anchor references remain valid and reproducible
- no private secrets or unrelated raw storage paths leak into the manifest

### 5. Canonical artefact metadata persistence
Implement or refine the canonical artefact table and related page-result linkage.

Requirements:
- `layout_line_artifacts` is authoritative for line crop, region crop, thumbnail, and context-window artefacts
- `artifacts_sha256` is populated from the persisted artefact bytes and remains stable for unchanged artefacts
- page result and run metadata can resolve artefact readiness cleanly
- historical artefacts remain immutable for a run
- reruns append new artefacts tied to the new run instead of overwriting prior ones

### 6. Artefact API delivery
Implement or refine:
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/lines/{lineId}/artifacts`

Requirements:
- typed response contract
- RBAC protected
- returns metadata and controlled access handles or same-origin delivery paths the repo already uses safely
- no raw storage-key leakage
- suitable for later transcription and rescue consumers
- clear not-ready and missing-artefact handling

### 7. Workspace and downstream integration
Refine only the minimum necessary web surfaces to make the artefacts real and inspectable.

Requirements:
- workspace or triage surfaces may show accurate artefact availability where useful
- no feature bloat
- downstream consumers can resolve stable line artifacts without guessing
- later transcription-facing implementation will not need to invent alternate crop/context logic

### 8. Regression and reproducibility
Add meaningful tests.

At minimum cover:
- stable line/region ID reproducibility
- thumbnail output path correctness
- line crop creation only for valid anchors
- context-window neighbor consistency
- artefact hash stability where deterministic
- no raw/public delivery leaks
- no-egress remains intact

### 9. Audit and privacy-safe observability alignment
Use the existing canonical paths.

Requirements:
- artefact reads or downloads remain within the existing audit/privacy posture
- no secret-bearing URLs or raw storage paths appear in logs
- no second audit or telemetry path is created

### 10. Documentation
Document:
- stable ID rules
- artefact storage layout
- `layout_line_artifacts` ownership
- context-window manifest semantics
- how Phase 4 must consume these artefacts for transcription and rescue
- what this prompt intentionally does not yet do

## Required deliverables

### Backend / workers / storage / contracts
- stable line/region ID materialization
- page thumbnail generation
- line crop and optional region crop generation
- context-window manifest generation
- `layout_line_artifacts` persistence
- artefact metadata API
- tests

### Web
- only small accurate availability or inspection refinements if needed

### Docs
- stable layout-artefact and anchor contract doc
- line-crop/thumbnail/context-window storage doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- storage adapters/config used by the repo
- `/packages/contracts/**`
- `/web/**` only if small accurate artefact-availability refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- transcription logic
- token anchors
- rescue-candidate generation
- manual edit version history
- public asset delivery
- a second artefact model
- rewriting historical run artefacts

## Testing and validation
Before finishing:
1. Verify stable line IDs and region IDs are reproducible.
2. Verify page thumbnails are generated at the canonical storage path.
3. Verify line crops are generated only for valid line anchors.
4. Verify optional region crops are accurate and bounded when generated.
5. Verify context-window manifests preserve valid neighboring anchors and stable line IDs.
6. Verify `layout_line_artifacts` is populated with correct keys, hashes, MIME/type metadata, and run/page/line linkage.
7. Verify the artefact API is typed, RBAC-protected, and leak-free.
8. Verify no raw/public delivery path is introduced.
9. Verify docs match the implemented stable-ID and artefact behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- stable line and region IDs are real
- page thumbnails, line crops, context windows, and optional region crops (when generated) are real
- `layout_line_artifacts` is real
- downstream consumers can resolve artefacts by `layout_run_id`, `page_number`, and `line_id` through a documented typed contract
- the controlled secure-environment posture remains intact
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

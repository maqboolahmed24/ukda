# Phase 2: Preprocessing Pipeline v1 - The Restoration Cut

> Status: ACTIVE
> Web Root: /web
> Active Phase Ceiling: 11
> Execution Policy: Phase 0 through Phase 11 are ACTIVE for this prompt program.
> Web Translation Overlay (ACTIVE): preserve existing workflow intent and phase semantics while translating any legacy desktop or WinUI terms into equivalent browser-native routes, layouts, and interaction patterns under /web.

## Phase Objective
Turn Phase 1 extracted page images into stable, reproducible, reviewable preprocessed derivatives that:

- materially improve downstream layout and handwriting model performance
- preserve provenance (original always remains available)
- expose quality metrics and before/after comparison in a professional workspace UI
- run fully inside the secure environment with no external calls

## Entry Criteria
Start Phase 2 only when all are true:
- Phase 1 page extraction and secure viewer routes are live for the target document scope.
- The preprocessing area preserves Phase 1 workflow and permission contracts while using browser-native responsive compositions rather than creating a parallel document experience.
- Optional deep links resolve to the same backing data and permissions as the primary preprocessing surface.

## Scope Boundary
Phase 2 creates deterministic preprocessing derivatives, comparison UX, and document-quality triage.

Out of scope for this phase:
- layout segmentation, PAGE-XML generation, and reading-order logic (Phase 3)
- transcription and transcript correction (Phase 4)
- privacy review, manifests, policy authoring, and export controls (Phases 5 through 8)

## Phase 2 Non-Negotiables
- Secure web application is the active delivery target: preserve phase behavior and governance contracts while implementing browser-native interaction, routing, and layout patterns from first principles (no desktop-mechanics carryover).
- All workspace and page surfaces inherit the canonical `Obsidian Folio` experience contract (dark-first Fluent 2 tokens, app-window adaptive states, single-fold defaults, keyboard-first accessibility); see `ui-premium-dark-blueprint-obsidian-folio.md`.
1. Original page images remain immutable inputs; preprocessing only creates new derived artefacts.
2. Every preprocessing profile is versioned, reproducible, and provenance-linked to the source page.
3. Compare and quality surfaces use the same controlled access rules as the Phase 1 viewer.
4. Optional aggressive techniques stay explicitly gated and never become silent defaults.

## Iteration Model
Build Phase 2 as five iterations (`2.0` to `2.4`). Each iteration must ship a usable system and avoid UI/data-model rework in later iterations.

## Iteration 2.0: UX Surfaces + Data Model Patch

### Goal
Create the right routes, screens, and preprocessing run model so Phase 2 features scale cleanly.

### Web Client Work
Use browser-native responsive compositions that match Phase 1 workflow intent (shell, list-detail, workspace) with progressive disclosure.
Viewer and compare surfaces inherit the Phase 1 Pattern D single-fold workspace contract (`Expanded | Balanced | Compact | Focus`).

#### New/updated routes
- `/projects/:projectId/documents/:documentId/preprocessing`
  - internal tabs:
    - `Pages`
    - `Quality`
    - `Processing runs`
    - `Metadata`
- `/projects/:projectId/documents/:documentId/preprocessing/quality` (optional deep link into the `Quality` tab)
- `/projects/:projectId/documents/:documentId/preprocessing/runs/:runId` (optional deep link into the `Processing runs` tab)
- `/projects/:projectId/documents/:documentId/preprocessing/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}` (optional deep link into the run-comparison surface)
- Viewer route remains `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}` with:
  - compare mode
  - right inspector drawer (metrics + run selection)

Ownership rule:
- `/preprocessing/compare` is the canonical run-analysis surface for preprocessing diagnostics, metrics, and before/after comparison between runs.
- Viewer `Compare` mode is an in-context document-reading aid; it must link back to `/preprocessing/compare` when the user needs full run diagnostics or quality triage context.

#### UX rules
- Primary surface is table or viewer canvas.
- Detailed diagnostics live in drawer or secondary pages.
- Toolbar interactions follow ARIA toolbar behavior.
- Focus visibility follows WCAG 2.2 baseline expectations.
- Default layouts avoid routine page-level vertical scrolling; overflow is absorbed through bounded panels, drawers, or virtualized regions with controlled reflow fallback.

### Backend Work
#### Data model changes
Add `preprocess_runs`:

- `id`
- `project_id`
- `document_id`
- `parent_run_id` (nullable when this is the first run for a document)
- `attempt_number`
- `superseded_by_run_id` (nullable)
- `run_scope` (`FULL_DOCUMENT | PAGE_SUBSET | COMPOSED_FULL_DOCUMENT`)
- `target_page_ids_json` (nullable)
- `composed_from_run_ids_json` (nullable)
- `profile_id` (for example `BALANCED`, `CONSERVATIVE`, `AGGRESSIVE`)
- `params_json` (expanded params actually used)
- `params_hash`
- `pipeline_version`
- `container_digest`
- `status`: `QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`
- `created_by`
- `created_at`
- `started_at`
- `finished_at`
- `failure_reason` (nullable)

Add `page_preprocess_results`:

- `run_id`
- `page_id`
- `page_index`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `quality_gate_status` (`PASS | REVIEW_REQUIRED | BLOCKED`)
- `source_result_run_id` (nullable; points at the run that physically owns the output artefacts when a composed run reuses unchanged page outputs)
- `input_object_key`
- `output_object_key_gray`
- `output_object_key_bin` (nullable)
- `metrics_json`
- `sha256_gray`
- `sha256_bin` (nullable)
- `warnings_json`
- `failure_reason` (nullable)
- `created_at`
- `updated_at`

Add `document_preprocess_projections`:

- `document_id`
- `project_id`
- `active_preprocess_run_id` (nullable until a successful run is explicitly promoted)
- `active_profile_id` (nullable)
- `updated_at`

Rules:
- preprocessing overview, quality, and viewer-default variant reads use `document_preprocess_projections.active_preprocess_run_id` when a caller does not request a specific run
- reruns append a new `preprocess_runs` row, increment `attempt_number`, preserve `parent_run_id`, and record the forward lineage link on the superseded source row through `superseded_by_run_id`
- a page result is `BLOCKED` when declared or estimated DPI is below `150`; it is `REVIEW_REQUIRED` when DPI is unknown or falls in `[150, 200)`, and only `PASS` pages may be treated as quality-clear without reviewer acknowledgement
- `PAGE_SUBSET` runs are review candidates, not directly promotable document projections
- activating a `PAGE_SUBSET` run materializes a new `COMPOSED_FULL_DOCUMENT` run that reuses unchanged page outputs from the current active full-document run and replaces only the targeted pages with the candidate outputs; that composed run becomes the new `active_preprocess_run_id`
- `PAGE_SUBSET` activation is rejected unless the document already has an activated `FULL_DOCUMENT` or `COMPOSED_FULL_DOCUMENT` preprocess run to use as the untouched-page base; the first activatable run for a document must therefore cover the full document
- when a `COMPOSED_FULL_DOCUMENT` run is created from `PAGE_SUBSET` activation, its `parent_run_id` points at the active full-document base run being replaced in the document projection, `composed_from_run_ids_json` records both the base-run ID and the subset-run ID, and the base full-document run receives the forward lineage link through `superseded_by_run_id`; the subset run remains a page-scope candidate record rather than being treated as the superseded document-wide projection
- `page_preprocess_results.source_result_run_id` records whether a page result's bytes were produced by the current run or inherited from an earlier run; `FULL_DOCUMENT` and `PAGE_SUBSET` rows point at their own `run_id`, while `COMPOSED_FULL_DOCUMENT` rows may point at the base run for unchanged pages
- composed runs do not copy inherited page bytes solely to satisfy a run-local object-key namespace; `output_object_key_gray` and `output_object_key_bin` may therefore reference storage under the `source_result_run_id` namespace, and the composed run's manifest is the authoritative map over those inherited or replaced page artefacts

Extend `pages` if missing immutable source metadata:

- `source_width`
- `source_height`
- `source_dpi`
- `source_color_mode` (`RGB | RGBA | GRAY | CMYK | UNKNOWN`)

#### API scaffolding
- `GET /projects/{projectId}/documents/{documentId}/preprocessing/overview`
- `GET /projects/{projectId}/documents/{documentId}/preprocessing/quality?runId={runId}&warning={warning}&status={status}&cursor={cursor}`
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/active`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/status`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/pages`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/pages/{pageId}`
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/rerun`
  - creates a new child run with `parent_run_id`, a freshly persisted `params_json`, and a recomputed `params_hash`
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/cancel`
  - allowed only while the target run is `QUEUED` or `RUNNING`
  - queued runs transition directly to `CANCELED`
  - running runs transition to `CANCELED` only through worker-checked cooperative cancellation; cancel requests against already terminal runs are rejected instead of rewriting terminal history
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/activate`
  - allowed only for `SUCCEEDED` runs with no `page_preprocess_results.quality_gate_status = BLOCKED`
  - `FULL_DOCUMENT` and `COMPOSED_FULL_DOCUMENT` runs update `document_preprocess_projections.active_preprocess_run_id` without mutating historical run rows
  - `PAGE_SUBSET` runs first create a successor `COMPOSED_FULL_DOCUMENT` run with `composed_from_run_ids_json` capturing both the active base run and the subset candidate run, then activate that successor
  - `PAGE_SUBSET` activation fails when no active full-document base run exists
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`

### Tests and Gates (Iteration 2.0)
#### Routing/layout gate
- New pages render a consistent web app shell with clear hierarchy, context-path breadcrumbs, and page headers.

#### Accessibility gate
- Axe scans pass on:
  - preprocessing overview page
  - quality page
  - run details page

#### RBAC gate
- Only `PROJECT_LEAD`, `RESEARCHER`, or `REVIEWER` can view quality/runs.
- Only `PROJECT_LEAD`, `REVIEWER`, or `ADMIN` can create, rerun, or cancel preprocessing runs.

#### Audit gate
- Audit events emitted:
  - `PREPROCESS_OVERVIEW_VIEWED`
  - `PREPROCESS_QUALITY_VIEWED`
  - `PREPROCESS_RUNS_VIEWED`
  - `PREPROCESS_ACTIVE_RUN_VIEWED`
  - `PREPROCESS_RUN_VIEWED`
  - `PREPROCESS_RUN_STATUS_VIEWED`
  - `PREPROCESS_RUN_CREATED`
  - `PREPROCESS_RUN_STARTED`
  - `PREPROCESS_RUN_FINISHED`
  - `PREPROCESS_RUN_FAILED`
  - `PREPROCESS_RUN_CANCELED` when applicable
  - `PREPROCESS_RUN_ACTIVATED`
- Creation event includes params hash and pipeline version.

### Exit Criteria (Iteration 2.0)
Routes, layout, and run model are ready for rapid preprocessing iteration without schema or navigation rewrites.

## Iteration 2.1: Preprocessing Engine v1

### Goal
Produce deterministic grayscale derivatives and quality metrics per page.

### Backend Work
#### Job types
- `PREPROCESS_DOCUMENT(run_id)`
- `PREPROCESS_PAGE(run_id, page_id)`
- `FINALIZE_PREPROCESS_RUN(run_id)`

#### Storage layout
Inputs:

- `controlled/derived/{project_id}/{document_id}/pages/{page_index}.png`

Outputs:

- `controlled/derived/{project_id}/{document_id}/preprocess/{run_id}/gray/{page_index}.png`
- `controlled/derived/{project_id}/{document_id}/preprocess/{run_id}/metrics/{page_index}.json`
- `controlled/derived/{project_id}/{document_id}/preprocess/{run_id}/manifest.json`

#### Preprocess algorithm v1 (grayscale path)
Run in a stable order:

1. decode and normalize to 8-bit grayscale
2. resolution standardization (record DPI; warn if unknown/low)
3. deskew (measure and correct skew angle)
4. background or shading normalization
5. denoise (small-kernel conservative cleanup)
6. contrast equalization (capped to avoid ink blowout)
7. write output and SHA-256

Pinned v1 parameters for the canonical grayscale path:

- grayscale conversion: BT.601 luma, round-to-nearest `uint8`
- `deskew_max_abs_angle_deg = 12.0`
- `deskew_apply_min_abs_angle_deg = 0.15`
- `background_norm_gaussian_sigma_px = 21`
- `denoise_median_kernel_px = 3`
- `contrast_clahe_tile_grid = 8x8`
- `contrast_clahe_clip_limit = 2.0`
- interpolation for geometric transforms: bicubic

Profile expansion may override these values only by writing the expanded concrete parameters into `params_json`; the canonical `BALANCED` v1 profile must keep these pinned defaults.

#### Page metrics
- `skew_angle_deg`
- `dpi_estimate`
- `blur_score`
- `background_variance`
- `contrast_score`
- `noise_score`
- `processing_time_ms`
- `warnings` (for example `LOW_DPI`, `HIGH_SKEW`, `HIGH_BLUR`, `LOW_CONTRAST`)

Metric definitions:

- `dpi_estimate`: declared source DPI when present, otherwise deterministic estimate from pixel dimensions plus the configured page-size heuristic; nullable only when neither input exists
- `blur_score`: normalized variance-of-Laplacian score on the deskewed grayscale output, mapped to `[0,1]` where lower means blurrier
- `background_variance`: low-frequency background variance after shading normalization, normalized to `[0,1]`
- `contrast_score`: normalized `(P90 - P10) / 255` intensity spread on the final grayscale output
- `noise_score`: normalized median absolute difference between the final grayscale output and its 3x3 median-filtered image, mapped to `[0,1]`

Quality gates:

- emit `LOW_DPI` when `dpi_estimate < 200`
- set `quality_gate_status = BLOCKED` when `dpi_estimate < 150`
- set `quality_gate_status = REVIEW_REQUIRED` when DPI is unknown or `150 <= dpi_estimate < 200`
- set `quality_gate_status = PASS` otherwise

#### Determinism and provenance rules
Every run persists:

- full parameter set
- pipeline version
- container digest

Constraint:

- same input + same params + same version must produce identical output hashes in same container/runtime.
- the canonical v1 grayscale path is bit-identical by contract; perceptual drift metrics do not waive this determinism requirement

### Web Client Work
#### Processing Runs tab
- Primary CTA: `Run preprocessing`.
- Runs table columns:
  - run ID
  - profile
  - started by
  - time
  - status
  - pages processed
- Run detail page:
  - summary cards and warning counts
  - parameters drawer (collapsed by default)

#### Pages tab
- per-page preprocess status badge from `document_preprocess_projections.active_preprocess_run_id`, not from an implicit latest-successful scan

### Tests and Gates (Iteration 2.1)
#### Unit
- Deskew angle stability on known skewed fixtures.
- Canonical parameter serialization (`same params => same hash`).
- Output keys constrained to preprocess derived prefix.

#### Integration
- Create run -> enqueue pages -> outputs written -> run finalizes.
- Retry `PREPROCESS_PAGE` is idempotent (no duplicate rows).
- Canceled runs stop scheduling additional page work and surface `CANCELED`.
- No-egress enforcement for preprocessing jobs (external calls hard fail).
- activation is blocked when any page in the candidate run has `quality_gate_status = BLOCKED`.
- cancel requests against preprocessing runs are rejected once the run is already terminal, and running-run cancellation cooperates with the worker instead of silently rewriting completed state

#### Regression
- Golden dataset (10-20 pages):
  - exact hash checks for the canonical grayscale profile
  - SSIM may be used only for explicitly marked non-canonical advanced profiles introduced later, never as a substitute for the canonical v1 hash gate
  - CI fails on unapproved drift

#### web-surface gates
- Visual snapshots for runs table states and run detail summary.
- A11y gate for tabs, tables, and drawers.

### Exit Criteria (Iteration 2.1)
Preprocessing runs produce stable grayscale outputs and metrics end-to-end with UI visibility.

## Iteration 2.2: Viewer Compare Modes + Metrics Inspector

### Goal
Let review users validate preprocessing impact directly in the viewer.

### Web Client Work
Viewer workspace enhancements:

- Compare workspace keeps the inherited single-fold state model; side rails and inspector compress before center-canvas functionality is reduced.
- Toolbar mode selector:
  - `Original`
  - `Preprocessed`
  - `Compare`
- Run selector for Preprocessed/Compare modes.
- Existing controls remain:
  - zoom
  - fit
  - rotate
- Compare rendering:
  - side-by-side split (v1)
- Right inspector drawer (collapsible):
  - page metrics
  - warning chips
  - deep link to quality table
  - deep link to the canonical `/preprocessing/compare` route for full run diagnostics

### Backend Work
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}/variants?runId={runId}`
  - returns available variants for the selected run; when `runId` is omitted, the document's explicitly activated preprocess run is used and the request fails if no active preprocess run exists
- Authenticated stream support for:
  - original image
  - preprocessed grayscale image
  - preprocessed binary image when the selected run persisted `output_object_key_bin`
- variant reads emit `PREPROCESS_VARIANT_ACCESSED`

### Tests and Gates (Iteration 2.2)
#### E2E
- Switch to Preprocessed and verify image changes.
- Switch to Compare and verify both variants render.
- Open inspector and verify metrics display.
- Keyboard toolbar navigation is predictable.

#### Accessibility
- Axe scan passes on viewer route.
- No keyboard traps.
- Focus is visible in toolbar and drawer flows.
- Reflow and zoom scenarios use controlled scrolling instead of clipping or obscured focus targets.

#### Visual regression
- Snapshots for Original, Preprocessed, Compare, inspector open/closed.

### Exit Criteria (Iteration 2.2)
Reviewers can compare variants and inspect quality without leaving the viewer.

## Iteration 2.3: Quality Triage Surface + Selective Re-run

### Goal
Enable fast triage of weak pages and selective reruns without reprocessing full documents.

### Web Client Work
#### Document Quality tab
Table-first design:

- columns:
  - page number
  - warnings
  - skew
  - blur score
  - DPI
  - status
- filters:
  - warning type
  - skew range
  - blur threshold
  - failed only
- bulk page selection
- primary CTA: `Re-run preprocessing`
- secondary action: `Compare runs`
- details drawer:
  - before/after mini previews
  - metrics breakdown
  - `Open in viewer`

#### Re-run wizard
1. choose scope (whole document or selected pages)
2. choose profile (`Conservative`, `Balanced`, `Aggressive`)
3. confirm and run

Advanced parameters remain collapsed by default.

### Backend Work
- Partial run targeting (`target_page_ids` in params).
- Profile system with baked profiles and explicit expanded params.
- Run comparison API (per-page run list and warning deltas).
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/rerun`
  - accepts optional page subset and profile override, expands to concrete params, and creates a new run without mutating the source run
  - runs with `target_page_ids` persist `run_scope = PAGE_SUBSET`; whole-document reruns persist `run_scope = FULL_DOCUMENT`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`
  - returns per-page warning deltas, metric deltas, and output availability
- compare reads emit `PREPROCESS_COMPARE_VIEWED`

### Tests and Gates (Iteration 2.3)
#### Unit
- Profile expansion correctness (`profile -> concrete params`).
- Subset targeting processes only selected pages.

#### Integration
- Selected-page run produces outputs only for requested subset.
- activating a selected-page run creates a `COMPOSED_FULL_DOCUMENT` successor that preserves untouched page outputs from the current active run and replaces only the selected pages
- activating a selected-page run without an existing active full-document base is rejected explicitly instead of guessing a composition basis

#### E2E
- Quality filters and bulk selection work.
- Re-run from selected pages creates new run.
- Viewer can select newly created run.

### Exit Criteria (Iteration 2.3)
Teams can triage and selectively improve difficult pages at scale.

## Iteration 2.4: Optional Advanced Preprocessing (Gated)

### Goal
Add stronger techniques as optional, controlled profiles without making them default behavior.

### Backend Work
#### Adaptive binarization (optional)
- Add adaptive thresholding output in optional profiles.
- Persist:
  - grayscale output (always)
  - binary output (when enabled)

#### Bleed-through reduction
- Support paired recto/verso processing when both sides are available.
- Provide conservative single-image fallback behind advanced profile.
- Require `REVIEWER`, `PROJECT_LEAD`, or `ADMIN` confirmation for bulk aggressive processing.

### Web Client Work
#### Profile descriptions
- `Balanced`: safe default
- `Aggressive`: stronger cleanup and optional binarization
- `Bleed-through`: best with paired sides

#### Viewer compare expansion
- Compare options:
  - Original vs Gray
  - Original vs Binary
  - Gray vs Binary

Avoid showing all variants at once.

### Tests and Gates (Iteration 2.4)
- Regression suite includes:
  - pages where binarization helps
  - pages where binarization harms
- Performance gate for bleed-through profile runtime.
- UI gate: advanced options remain behind progressive disclosure and clear labels.

### Exit Criteria (Iteration 2.4)
Advanced preprocessing is available, reviewable, and controlled, but not default.

## Handoff to Later Phases
- Phase 3 consumes `document_preprocess_projections.active_preprocess_run_id` as the canonical image input for layout segmentation.
- Later phases may read preprocessing metrics and derivatives, but they do not mutate the original page assets from Phase 1.

## Phase 2 Definition of Done
Move to Phase 3 only when all are true:

1. Preprocess runs are versioned, deterministic, and stored as Controlled derived artefacts.
2. Viewer supports `Original`, `Preprocessed`, and `Compare` with metrics inspector.
3. Document has a quality triage surface with filters and selective rerun workflow.
4. Accessibility and visual regression gates are green for all new screens.
5. Pipeline runs fully inside secure environment with no-egress guardrails.
6. Regression or golden test pack prevents silent preprocessing quality drift.

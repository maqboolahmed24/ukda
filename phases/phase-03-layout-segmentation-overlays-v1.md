# Phase 3: Layout Segmentation v1 + Overlays - The Shape of the Page

> Status: ACTIVE
> Web Root: /web
> Active Phase Ceiling: 11
> Execution Policy: Phase 0 through Phase 11 are ACTIVE for this prompt program.
> Web Translation Overlay (ACTIVE): preserve existing workflow intent and phase semantics while translating any legacy desktop or WinUI terms into equivalent browser-native routes, layouts, and interaction patterns under /web.

## Phase Objective
Turn Phase 2 preprocessed page images into a region and line layer that makes complex handwriting machine-readable and reviewer-usable through explicit structure:

- region-level segmentation (columns, text blocks, marginalia, stamps/graphics, tables)
- line-level segmentation (baselines and/or line polygons)
- explicit reading order with uncertainty-safe behavior
- dedicated segmentation workspace UI that keeps advanced controls out of general pages

## Entry Criteria
Start Phase 3 only when all are true:
- A successful Phase 2 preprocessing run exists for the selected document scope.
- Controlled viewer and asset-proxy patterns from earlier phases remain in force for overlay rendering.
- Phase 3 PAGE-XML will become the canonical structural input for Phase 4 transcription and the anchor source later consumed alongside Phase 4 transcripts in Phase 5 privacy review.

## Scope Boundary
Phase 3 creates canonical layout structure, overlays, reading order, and limited manual correction tools.

Out of scope for this phase:
- transcript generation or transcript correction (Phase 4)
- privacy detection, redaction decisions, manifests, and export governance (Phases 5 through 8)

## Phase 3 Non-Negotiables
- Secure web application is the active delivery target: preserve phase behavior and governance contracts while implementing browser-native interaction, routing, and layout patterns from first principles (no desktop-mechanics carryover).
- All workspace and page surfaces inherit the canonical `Obsidian Folio` experience contract (dark-first Fluent 2 tokens, app-window adaptive states, single-fold defaults, keyboard-first accessibility); see `ui-premium-dark-blueprint-obsidian-folio.md`.
- Recall-first behavior from `UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` is normative when layout-only completion semantics would conflict.
1. PAGE-XML remains the canonical output and source of truth for layout structure.
2. Manual corrections create audited new state; they never silently overwrite provenance.
3. Uncertain reading order is surfaced explicitly instead of guessed away.
4. Advanced segmentation tools stay in dedicated workspaces and do not clutter general document views.
5. Internal geometry caches may be JSON for UI performance, but every run must be serializable back to canonical PAGE-XML artefacts.
6. Stable line IDs and context artefacts must remain reproducible so Phase 4 can anchor VLM transcription back to canonical layout state.
7. No page may silently drop potential handwriting content; each page must resolve explicit recall status before downstream activation.

## Iteration Model
Build Phase 3 as five iterations (`3.0` to `3.4`). Each iteration must ship a usable upgrade and preserve clean separation between overview, triage, and workspace editing.

## Iteration 3.0: IA, UX Surfaces, and Run Data Model

### Goal
Create dedicated layout analysis surfaces and make layout inference a first-class run type.

### Web Client Work
Layout workspace surfaces inherit the Phase 1 Pattern D single-fold contract and adaptive states (`Expanded | Balanced | Compact | Focus`).

#### Routes
- `/projects/:projectId/documents/:documentId/layout`
  - internal tabs:
    - `Layout overview`
    - `Page triage`
    - `Runs`
- `/projects/:projectId/documents/:documentId/layout/runs/:runId`
- `/projects/:projectId/documents/:documentId/layout/workspace?page={pageNumber}&runId={runId}`

#### Layout Overview
- Summary cards for the activated run from `document_layout_projections.active_layout_run_id`:
  - regions detected
  - lines detected
  - pages with issues
  - structure confidence
- Primary CTA: `Run layout analysis`
- Secondary action: `View run details`

#### Page Triage (table-first)
- Table columns:
  - page number
  - issues
  - region count
  - line count
  - coverage percent
  - status
- Filters:
  - missing lines
  - overlaps
  - low coverage
  - complex layout / uncertain structure
- Row selection opens right-side details drawer:
  - overlay preview
  - metrics
  - `Open in workspace`

#### Segmentation Workspace (read-only in 3.0)
- Top toolbar:
  - run selector
  - overlay toggles
  - `Open triage`
- Left rail:
  - page filmstrip
- Center:
  - page canvas
- Right inspector:
  - page metrics
  - regions/lines list with selection highlighting
- Default composition keeps page-level vertical scrolling out of the workspace shell; dense content scrolls in bounded rails and lists.

Accessibility requirement:

- toolbar keyboard behavior follows ARIA toolbar guidance
- Reflow scenarios allow controlled scrolling without clipping focus targets.

### Backend Work
#### Data model
Add `layout_runs`:

- `id`
- `project_id`
- `document_id`
- `input_preprocess_run_id`
- `run_kind` (`AUTO | MANUAL_EDIT | READING_ORDER_EDIT`)
- `parent_run_id` (nullable when derived from an earlier layout run)
- `attempt_number`
- `superseded_by_run_id` (nullable)
- `model_id` (nullable for `MANUAL_EDIT` or `READING_ORDER_EDIT` runs)
- `profile_id` (nullable for `MANUAL_EDIT` or `READING_ORDER_EDIT` runs)
- `params_json`
- `params_hash`
- `pipeline_version`
- `container_digest`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `created_by`
- `created_at`
- `started_at`
- `finished_at`
- `canceled_by` (nullable)
- `canceled_at` (nullable)
- `failure_reason` (nullable)

Add `page_layout_results`:

- `run_id`
- `page_id`
- `page_index`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `page_recall_status` (`COMPLETE | NEEDS_RESCUE | NEEDS_MANUAL_REVIEW`)
- `active_layout_version_id` (nullable until canonical output is first materialised for that page)
- `page_xml_key` (nullable until generation succeeds)
- `overlay_json_key` (nullable until generation succeeds)
- `page_xml_sha256` (nullable until generation succeeds)
- `overlay_json_sha256` (nullable until generation succeeds)
- `metrics_json`
- `warnings_json`
- `failure_reason` (nullable)
- `created_at`
- `updated_at`

Add `layout_recall_checks`:

- `run_id`
- `page_id`
- `layout_version_id`
- `recall_check_version`
- `missed_text_risk_score`
- `signals_json`
- `created_at`

Add `layout_rescue_candidates`:

- `id`
- `run_id`
- `page_id`
- `layout_version_id`
- `candidate_kind` (`LINE_EXPANSION | PAGE_WINDOW`)
- `geometry_json`
- `confidence`
- `source_signal`
- `status` (`PENDING | ACCEPTED | REJECTED | RESOLVED`)
- `created_at`
- `updated_at`
- `resolved_by` (nullable)
- `resolved_at` (nullable)

Add `layout_rescue_candidate_events`:

- `id`
- `candidate_id`
- `run_id`
- `page_id`
- `event_type` (`CANDIDATE_CREATED | CANDIDATE_ACCEPTED | CANDIDATE_REJECTED | CANDIDATE_RESOLVED`)
- `actor_user_id` (nullable for system-generated candidate creation or downstream consumption)
- `reason` (nullable)
- `created_at`

Add `document_layout_projections`:

- `document_id`
- `project_id`
- `active_layout_run_id` (nullable until a successful run is explicitly promoted)
- `active_input_preprocess_run_id` (nullable)
- `active_layout_snapshot_hash` (nullable)
- `downstream_transcription_state` (`NOT_STARTED | CURRENT | STALE`)
- `downstream_transcription_invalidated_at` (nullable)
- `downstream_transcription_invalidated_reason` (nullable)
- `updated_at`

Rules:
- layout overview, triage, and workspace defaults read from `document_layout_projections.active_layout_run_id` when a caller does not request a specific run
- reruns append a new `layout_runs` row, increment `attempt_number`, preserve `parent_run_id`, and record the forward lineage link on the superseded source row through `superseded_by_run_id`
- activating a layout run marks downstream transcription state as `STALE` until a transcription run is explicitly activated against the current layout generation; if no transcription has ever been activated for the document, use `NOT_STARTED`
- `run_kind = AUTO` is the only batch-analysis pipeline in v1; page corrections and reading-order changes persist as `layout_versions` within that run rather than minting standalone edit runs
- `page_recall_status` mapping is deterministic in v1:
  - `COMPLETE` when `missed_text_risk_score < 0.25` and no rescue candidate survives scoring
  - `NEEDS_RESCUE` when `0.25 <= missed_text_risk_score < 0.60`, or when any rescue candidate is persisted for downstream transcription
  - `NEEDS_MANUAL_REVIEW` when `missed_text_risk_score >= 0.60`, or when the recall check cannot produce a stable rescue candidate set
- rescue-candidate lifecycle is deterministic in v1:
  - `PENDING` may exist only while the current page job is still running
  - `ACCEPTED` means the candidate is approved as Phase 4 transcription input
  - `REJECTED` means the candidate was dismissed by the recall-check logic or manual review
- `RESOLVED` is reserved for later post-transcription consumption or explicit manual closure
- no-silent-drop gate: a run cannot be activated while any page in `page_layout_results` lacks resolved `page_recall_status` (`COMPLETE | NEEDS_RESCUE | NEEDS_MANUAL_REVIEW`), while any rescue candidate remains `PENDING`, or while a `NEEDS_RESCUE` page lacks at least one `ACCEPTED` rescue candidate
- `NEEDS_MANUAL_REVIEW` pages must expose a manual rescue-decision path that transitions candidates to `ACCEPTED` or `REJECTED` and may mark accepted candidates `RESOLVED` after downstream transcription consumes them
- manual rescue decisions and later candidate closure append `layout_rescue_candidate_events`; the mutable `layout_rescue_candidates.status` field is only the current projection and must not be the sole source of rescue-review history
- `layout_recall_checks` and `layout_rescue_candidates` must pin the exact `layout_version_id` they were computed from, so later page edits can preserve or supersede recall history without losing the geometry version that produced it

Optional denormalised table for fast UI queries: `layout_elements`:

- `run_id`
- `page_id`
- `layout_version_id`
- `element_id`
- `element_type`
- `parent_id`
- `coords_json`
- `order_index`

Required derived artefact table for VLM-ready anchors: `layout_line_artifacts`:

- `run_id`
- `page_id`
- `layout_version_id`
- `line_id`
- `region_id` (nullable when the line is not associated to a persisted region)
- `line_crop_key`
- `region_crop_key` (nullable)
- `page_thumbnail_key`
- `context_window_json_key`
- `artifacts_sha256`
- `supersedes_artifact_row_id` (nullable)
- `superseded_by_artifact_row_id` (nullable)

Phase 4 and later phases read line crops, thumbnails, and context windows only from persisted `layout_line_artifacts`; these artefacts are not optional in the v1 contract.

#### Object storage
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}.xml`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}.json`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/thumbnail.png`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/lines/{line_id}.png`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/regions/{region_id}.png`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/context/{line_id}.json`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/manifest.json`

#### APIs
- `GET /projects/{projectId}/documents/{documentId}/layout/overview`
- `POST /projects/{projectId}/documents/{documentId}/layout-runs`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/active`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/status`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages`
- `POST /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/activate`
  - allowed only for `SUCCEEDED` runs and updates `document_layout_projections.active_layout_run_id`, `active_input_preprocess_run_id`, and `active_layout_snapshot_hash`
- `POST /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/cancel`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/overlay`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/pagexml` (Controlled-only)
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/lines/{lineId}/artifacts`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/versions`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/versions/{versionId}`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/recall-status`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/rescue-candidates`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/rescue-candidates/{candidateId}/events`
- `PATCH /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/rescue-candidates/{candidateId}`
  - available to `PROJECT_LEAD`, `REVIEWER`, or `ADMIN`
  - accepts `status = ACCEPTED | REJECTED`, appends `layout_rescue_candidate_events`, and rejects stale or cross-page updates
- `POST /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/rescue-candidates/{candidateId}/resolve`
  - available to `PROJECT_LEAD`, `REVIEWER`, or `ADMIN`
  - allowed only when the current candidate status is `ACCEPTED` and the caller supplies a closure reason or a downstream-transcription consumption reference; appends `layout_rescue_candidate_events` and updates the current candidate projection to `RESOLVED`

### Tests and Gates (Iteration 3.0)
#### Backend
- RBAC: only `PROJECT_LEAD`, `RESEARCHER`, or `REVIEWER` can view layout artefacts; only `PROJECT_LEAD`, `REVIEWER`, or `ADMIN` can create or cancel runs.
- Audit events emitted:
  - `LAYOUT_OVERVIEW_VIEWED`
  - `LAYOUT_TRIAGE_VIEWED`
  - `LAYOUT_RUNS_VIEWED`
  - `LAYOUT_ACTIVE_RUN_VIEWED`
  - `LAYOUT_RUN_CREATED`
  - `LAYOUT_RUN_STARTED`
  - `LAYOUT_RUN_FINISHED`
  - `LAYOUT_RUN_FAILED`
  - `LAYOUT_RUN_CANCELED` when applicable
  - `LAYOUT_RUN_VIEWED`
  - `LAYOUT_RUN_STATUS_VIEWED`
  - `LAYOUT_RUN_ACTIVATED`
  - `LAYOUT_RESCUE_CANDIDATE_UPDATED`
  - `LAYOUT_RESCUE_CANDIDATE_EVENTS_VIEWED`
  - `LAYOUT_WORKSPACE_VIEWED`
  - `LAYOUT_OVERLAY_ACCESSED` when the overlay endpoint is read
  - `LAYOUT_PAGEXML_ACCESSED` when the Controlled PAGE-XML endpoint is read
  - `LAYOUT_VERSION_VIEWED` when a saved version is opened

#### web-surface
- Visual regression for overview, triage, and workspace states (`Expanded`, `Balanced`, `Compact`, `Focus`).
- Accessibility scans pass on overview, triage, and workspace shell routes.

### Exit Criteria (Iteration 3.0)
Layout run scaffolding exists in DB and UI surfaces are ready, even if inference is still stubbed.

## Iteration 3.1: Layout Inference Engine v1 (Regions + Lines)

### Goal
Generate region polygons, line geometry, initial reading-order hints, and quality metrics from preprocessed page images.

### Backend Work
#### Jobs
- `LAYOUT_ANALYZE_DOCUMENT(run_id)`
- `LAYOUT_ANALYZE_PAGE(run_id, page_id)`
- `FINALIZE_LAYOUT_RUN(run_id)`

#### Per-page pipeline
1. select input image from chosen preprocess run
2. run segmentation model for regions and lines/baselines
3. convert model output masks to polygons
4. simplify polygons for UI performance
5. associate lines to regions
6. compute layout metrics and warnings
7. emit canonical PAGE-XML
8. materialize stable line IDs, line crops, optional region crops, page thumbnail, and per-line context windows tied back to PAGE-XML anchors
9. run missed-text recall check and persist `page_recall_status` plus any rescue candidates
10. persist PAGE-XML, overlay JSON cache, VLM-ready artefacts, and metrics

#### Metrics and warnings
Metrics:

- `num_regions`
- `num_lines`
- region coverage percent
- line coverage percent

Warnings examples:

- `LOW_LINES`
- `OVERLAPS`
- `COMPLEX_LAYOUT`
- `MISSED_TEXT_SUSPECTED`

### Tests and Gates (Iteration 3.1)
#### Unit
- Polygon validity:
  - within page bounds
  - non-empty
  - no NaN/Inf
- Line-to-region association fixtures pass.
- Context-window generation preserves valid neighboring anchors and stable line IDs.

#### Integration
- Run creation to finalization writes all expected artefacts.
- Retry is idempotent (no duplicate rows).
- Canceled runs stop scheduling additional page work and surface `CANCELED`.
- No-egress test enforces internal-only execution.
- VLM-ready crops and context manifests are written only for valid PAGE-XML line anchors.
- every page resolves `page_recall_status` and no run activation can bypass unresolved recall status.
- runs with `NEEDS_RESCUE` pages cannot activate while rescue candidates remain `PENDING` or when no `ACCEPTED` rescue candidate exists for that page.
- `NEEDS_MANUAL_REVIEW` pages can be resolved only through explicit rescue-candidate review actions; activation remains blocked until those decisions are persisted
- rescue-candidate review history is reconstructable from append-only `layout_rescue_candidate_events`, and direct writes to `RESOLVED` are rejected unless they go through the explicit resolve flow for an already accepted candidate

#### ML regression
- Gold set with PAGE-XML ground truth tracks:
  - region overlap score
  - line detection recall
  - missed-text recall-check performance and rescue-candidate quality

### Exit Criteria (Iteration 3.1)
A full document layout run produces regions, lines, metrics, and warnings visible in overview and triage UI.

## Iteration 3.2: Overlays v1 (Read-only Workspace)

### Goal
Provide professional read-only overlay inspection before editing tools are introduced.

### Web Client Work
#### Segmentation Workspace capabilities
- Top toolbar:
  - run selector
  - overlay toggles:
    - regions
    - lines
    - baselines (if present)
    - reading order arrows (if present)
  - overlay opacity control
  - `Open triage`
- Left filmstrip (collapsible)
- Center canvas with image and overlay layers
- Right inspector:
  - page metrics
  - warning chips
  - region tree
  - line list filtered by selected region

#### Interaction model (read-only)
- Hover highlights elements.
- Click selects and pins highlight.
- Inspector list selection highlights on canvas.

### Backend Work
- Provide overlay payload optimized for rendering:
  - simplified polygons
  - stable element IDs
  - parent/child references
- Add internal caching strategy for overlay resources.

### Tests and Gates (Iteration 3.2)
#### E2E
- Toggle overlays on and off.
- Select region and confirm inspector sync.
- Switch run and confirm overlay refresh.

#### Accessibility
- Toolbar keyboard operable.
- Drawer open/close focus management works.
- Focus remains visible and unobscured in main flows.

#### Visual regression
- Overlay on/off snapshots.
- Inspector open/closed snapshots.
- Zoom-state snapshots.

### Exit Criteria (Iteration 3.2)
Reviewers can inspect segmentation quality in a dedicated workspace without editing.

## Iteration 3.3: Manual Correction Tools v1

### Goal
Enable minimal but essential manual fixes for segmentation failure cases.

### Web Client Work
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

### Backend Work
- Persist edits as new layout version (append-only strategy):
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
    - `run_snapshot_hash`
    - `created_by`
    - `created_at`
  - each save creates a new immutable `layout_versions` row and a replacement PAGE-XML artefact without mutating prior versions
  - each save updates `page_layout_results.active_layout_version_id` to the newest saved version for that page and marks the previous version row as superseded through `superseded_by_version_id`
  - every save regenerates `layout_line_artifacts` rows scoped to the new `layout_version_id`; old artifact rows remain intact and are superseded rather than overwritten
  - `run_snapshot_hash` is recomputed from the set of active page layout versions in the run so downstream phases can pin a document-wide immutable layout basis even after page-level edits
- Only `PROJECT_LEAD`, `REVIEWER`, or `ADMIN` can apply or save layout edits.
- API:
  - `PATCH /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/elements`
  - accepts operation list (add/move/delete/retag) plus the caller's current `version_etag`
  - applies the operation list against the current version, persists a new `layout_versions` row, and returns the new version metadata
  - rejects stale `version_etag` values with an optimistic-lock conflict instead of overwriting a newer saved version
- Validation and persistence:
  - validate geometry
  - write updated PAGE-XML
  - regenerate affected line crops, page thumbnail metadata, and context manifests for the edited page
  - when an edit changes page segmentation geometry, line membership, or inclusion of text-bearing elements, rerun the page-level missed-text recall check against the new active layout version and replace the page's `layout_recall_checks`, `layout_rescue_candidates`, and `page_recall_status` projections before the save is considered complete
  - if the edited page belongs to the active layout run, set `document_layout_projections.downstream_transcription_state = STALE` and persist `downstream_transcription_invalidated_at` plus a reason that later phases can surface to users
- Audit event:
  - `LAYOUT_EDIT_APPLIED` with edit metadata only
  - `LAYOUT_DOWNSTREAM_INVALIDATED` when an edit makes the current active transcription basis stale

### Tests and Gates (Iteration 3.3)
#### Unit
- Operation application tests for add/move/delete.
- Geometry validation rejects invalid polygons.
- Cross-page edit attempts are rejected.

#### Integration
- Edit applies and overlay cache updates.
- editing a page on the active layout run marks downstream transcription state as `STALE` until Phase 4 activates a transcription run against the updated layout generation
- PAGE-XML updates after successful save.
- Concurrent editing handled with optimistic locking.
- edited pages append version-scoped `layout_line_artifacts` rows instead of overwriting prior artifact rows, and the run's `run_snapshot_hash` changes when the active page-version set changes
- segmentation edits recompute recall-check outputs for the edited page, so `page_recall_status` and rescue candidates cannot stay pinned to a superseded page geometry

#### E2E
- Draw region, save, refresh, and verify persistence.
- Reassign line to region and verify inspector/canvas updates.

### Exit Criteria (Iteration 3.3)
Users can correct problematic pages while preserving provenance and version history.

## Iteration 3.4: Reading Order v1 (Auto + Manual + Uncertain Handling)

### Goal
Generate useful reading order when confident and safely withhold strict order when ambiguity is high.

### Backend Work
#### Auto reading-order algorithm (v1)
- build reading-order tree by layout groups
- detect dominant text orientation per page or region cluster and normalize sort axes before grouping
- detect likely columns from region geometry using x-overlap clustering in the normalized orientation
- isolate marginalia, inserts, stamps, or rotated side-notes into separate side groups unless they have an explicit parent anchor
- create ordered groups only within high-confidence columns
- sort regions within an ordered group by primary-flow axis first and secondary-flow axis second, rather than assuming a global top-to-bottom then left-to-right order
- compute `reading_order_ambiguity_score` from `column certainty`, `overlap conflict score`, normalized orphan-line count, and non-text complexity indicators
- use unordered groups when `0.35 <= reading_order_ambiguity_score < 0.60`
- leave reading order blank when `reading_order_ambiguity_score >= 0.60` or when mixed orientation cannot be normalized safely
- serialize reading order into PAGE-XML structures
- regenerate context-window manifests when reading-order changes affect neighboring line context

#### Confidence signals
- column certainty
- overlap conflict score
- orphan line count
- non-text complexity indicators
- ordered groups are allowed only when `column certainty >= 0.75` and `reading_order_ambiguity_score < 0.35`
- reading-order saves create a new `layout_versions` row rather than mutating prior PAGE-XML
- API:
  - `PATCH /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/reading-order`
  - accepts reorder operations plus the caller's current `version_etag`, persists a new layout version, and returns updated reading-order metadata
  - rejects stale `version_etag` values with an optimistic-lock conflict instead of overwriting a newer saved version
- Audit event:
  - `LAYOUT_READING_ORDER_UPDATED` with reading-order metadata only

### Web Client Work
In workspace inspector, add `Reading order` tab:

- tree view
- drag/drop reorder
- ordered/unordered group toggle

### Tests and Gates (Iteration 3.4)
#### Unit
- Reading-order tree validity:
  - no duplicate indices in ordered group
  - references only existing regions
- Uncertain-layout threshold triggers blank/unordered handling.
- mixed-orientation or marginalia fixtures route to side groups or blank order instead of being forced through a naive top-to-bottom sort.

#### E2E
- Manual reorder persists after save/refresh.
- PAGE-XML reflects updated reading order.

### Exit Criteria (Iteration 3.4)
Reading order is available when reliable and explicitly uncertain when confidence is low.

## Handoff to Later Phases
- Phase 4 consumes `document_layout_projections.active_layout_run_id` together with each page's active saved layout version, line crops, context-window artefacts, and recall-check/rescue-candidate status as transcription input.
- Phase 5 may reuse the same layout anchors for privacy highlighting, but layout correction remains owned by Phase 3.

## Phase 3 Definition of Done
Move to Phase 4 only when all are true:

1. Layout runs produce regions, lines, metrics, and surfaced failures across document pages.
2. Canonical outputs are stored as reproducible PAGE-XML artefacts.
3. Segmentation workspace supports read-only overlay review and minimal manual fixes without clutter.
4. Reading order supports ordered/unordered grouping and uncertainty-safe blank behavior.
5. Every page resolves explicit recall status (`COMPLETE | NEEDS_RESCUE | NEEDS_MANUAL_REVIEW`) before downstream activation.
6. Quality gates pass:
   - accessibility scans on layout surfaces
   - visual regression snapshots
   - ML regression against a layout gold set

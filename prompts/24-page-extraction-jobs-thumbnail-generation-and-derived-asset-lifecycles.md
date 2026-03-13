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
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-01-ingest-document-viewer-v1.md`
   - `/phases/phase-02-preprocessing-pipeline-v1.md` for future compatibility of derived page assets only
3. Then review the current repository generally — jobs framework, workers, document models, storage adapters, image/asset delivery, document routes, viewer route skeletons, contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second extraction pipeline, a second page model, or a second asset-delivery path.

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
- `/phases` wins for page-model semantics, derived-storage layout, append-only processing lineage, viewer API shape, controlled-asset posture, and acceptance logic.
- Official docs win only for implementation mechanics.
- Keep extraction and thumbnails inside the controlled environment. Do not introduce raw-original delivery, public asset buckets, or ad hoc page-generation shortcuts.

## Objective
Implement page extraction jobs, thumbnail generation, and derived-asset lifecycles for imported sources.

This prompt owns:
- the pages model
- extraction and thumbnail job types
- append-only document processing runs for upload/scan/extraction/thumbnail stages
- derived asset generation and storage
- authenticated page and thumbnail delivery
- document timeline extension for extraction lifecycle
- minimal viewer/data integration so the document family becomes genuinely alive
- status and cancellation handling for derived-asset work

This prompt does not own:
- the full viewer interaction model and polish
- advanced document-library UX
- resumable upload
- extraction retry UI and append-only retry lineage deepening
- later preprocessing/layout/transcription/privacy workflows

## Phase alignment you must preserve
From Phase 1 Iteration 1.3 and the Phase 0 jobs/storage backbone:

### Required pages model
Implement or reconcile:
- `pages`
  - `id`
  - `document_id`
  - `page_index` (0-based)
  - `width`
  - `height`
  - `dpi`
  - `status` (`PENDING | READY | FAILED | CANCELED`)
  - `derived_image_key`
  - `derived_image_sha256`
  - `thumbnail_key`
  - `thumbnail_sha256`
  - `failure_reason`
  - `canceled_by`
  - `canceled_at`
  - `viewer_rotation` (default `0`)
  - `created_at`
  - `updated_at`

### Required processing-run lineage
Implement or reconcile:
- `document_processing_runs`
  - `id`
  - `document_id`
  - `run_kind` (`UPLOAD | SCAN | EXTRACTION | THUMBNAIL_RENDER`)
  - `supersedes_processing_run_id`
  - `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
  - `created_by`
  - `created_at`
  - `started_at`
  - `finished_at`
  - `canceled_by`
  - `canceled_at`
  - `failure_reason`

Rules:
- document detail timelines read append-only upload, scan, extraction, and thumbnail attempts from `document_processing_runs`
- extraction and thumbnail work append new run rows rather than overloading `documents.status` alone
- later retry lineage deepening arrives in a later prompt; do not overbuild it now unless the current repo already has the right minimal shape

### Required job types
Use the existing canonical jobs system from the repo and reconcile:
- `EXTRACT_PAGES(document_id)`
- `RENDER_THUMBNAILS(document_id)`

### Required derived-storage layout
Write:
- `controlled/derived/{project_id}/{document_id}/pages/{page_index}.png`
- `controlled/derived/{project_id}/{document_id}/thumbs/{page_index}.jpg`

### Required viewer/data APIs
Implement or reconcile:
- `GET /projects/{projectId}/documents/{documentId}/pages`
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}`
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}/image?variant={variant}` where `variant` is `full` or `thumb`
- `PATCH /projects/{projectId}/documents/{documentId}/pages/{pageId}` for persisted viewer properties such as rotation

Rules:
- page metadata and page failure state come from page APIs, not from guessing based on image delivery
- image delivery must be authenticated same-origin streaming or an equivalent internal proxy path
- no raw original download endpoint

### Required audit events
Emit or reconcile:
- `DOCUMENT_PAGE_EXTRACTION_STARTED`
- `DOCUMENT_PAGE_EXTRACTION_COMPLETED`
- `DOCUMENT_PAGE_EXTRACTION_FAILED`
- `DOCUMENT_LIBRARY_VIEWED`
- `DOCUMENT_DETAIL_VIEWED`
- `DOCUMENT_TIMELINE_VIEWED`
- `PAGE_METADATA_VIEWED`
- `PAGE_IMAGE_VIEWED` (sampled if the repo already uses sampled view events)

## Implementation scope

### 1. Page and processing-run persistence
Implement or refine the page and processing-run persistence layer.

Requirements:
- one canonical `pages` model
- one canonical `document_processing_runs` model
- append-only run history
- no mutation of historical runs to pretend later outcomes happened earlier
- page rows created deterministically from extraction output
- page count kept consistent on the parent document
- cancellation and failure states remain explicit and accurate

If the repo already has partial processing-run lineage, reconcile it rather than replacing it wholesale.

### 2. Integrate with the existing jobs framework
Use the current repo's canonical jobs system if it already exists in the repository.

Requirements:
- enqueue `EXTRACT_PAGES` after scan acceptance or through the cleanest equivalent trigger in the current repo
- enqueue `RENDER_THUMBNAILS` after page extraction succeeds or through the cleanest equivalent trigger
- avoid duplicate execution
- preserve cancellation/failure behavior
- do not create a second worker queue
- document-processing runs and generic jobs may coexist, but their responsibilities must stay clear:
  - jobs = execution orchestration
  - document_processing_runs = document-scoped append-only attempt lineage

### 3. Extraction pipeline
Implement the real extraction logic for the phase-supported source types.

Requirements:
- PDF: rasterize pages to PNG
- multi-page TIFF: split frames
- single image: one page
- update page metadata and document state correctly
- produce safe failure reasons
- unfinished page rows become `CANCELED` if extraction is canceled mid-run
- derived image checksums are captured
- later phases can consume the produced page images as-is

Do not overbuild downstream preprocessing here.

### 4. Thumbnail generation
Implement or refine thumbnail generation.

Requirements:
- generate thumbnail assets for extracted pages
- capture thumbnail metadata and checksum
- keep thumbnail format and size consistent
- derived keys use the controlled derived-storage layout
- no public thumbnail path
- failures remain explicit and visible in metadata

### 5. Authenticated asset delivery
Implement or refine the same-origin asset-delivery path.

Requirements:
- `variant=full|thumb` image endpoint works
- page asset delivery is authenticated and project-scoped
- browser access does not expose raw storage directly
- caching is safe and consistent with the current repo's security model
- no original upload file delivery is introduced

### 6. Document timeline extension
Extend or reconcile:
- `GET /projects/{projectId}/documents/{documentId}/timeline`

Requirements:
- includes upload and scan attempts already present
- now also includes extraction and thumbnail attempts from append-only processing runs
- preserves accurate branch states for failure and cancellation
- does not imply a later stage succeeded if it did not

### 7. Minimal web integration
Wire the newly available data into the existing document family without overbuilding later work.

At minimum refine:
- document detail route so it shows page count and derived-asset readiness accurately
- viewer route so it can open a real page when pages are ready
- viewer route not-ready/failure states when pages are absent or failed
- page query handling remains 1-based in the browser and maps safely to 0-based `page_index`

Do not fully implement viewer zoom/pan/filmstrip polish here.
That belongs to later work.

### 8. Page metadata and viewer properties
Implement or refine:
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}`
- `PATCH /projects/{projectId}/documents/{documentId}/pages/{pageId}`

Requirements:
- expose page metadata needed for the right inspector and future viewer tooling
- allow persisted viewer properties such as rotation
- keep the contract typed and small
- do not infer page state from image presence alone

### 9. Documentation
Document:
- the extraction and thumbnail lifecycle
- the role of `pages`
- the role of `document_processing_runs`
- how generic jobs and document processing runs relate
- derived-storage layout
- asset-delivery rules
- what later work should add in the viewer and ingest-status UX

## Required deliverables

### Backend / workers / storage
- `pages` model/migration
- `document_processing_runs` model/migration
- extraction worker/handler
- thumbnail worker/handler
- timeline extension
- page metadata and image endpoints
- tests

### Web
- document detail integration for page/derived readiness
- minimal viewer alive-path integration
- safe processing/failure/not-ready states

### Docs
- extraction and derived-asset lifecycle doc
- authenticated asset-delivery doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**`
- `/web/**`
- storage adapters/config used by the repo
- `/packages/contracts/**`
- `/packages/ui/**` only if small viewer/detail/status refinements are needed
- root config/task files
- `README.md`
- `docs/**`
- `infra/**` only where needed for controlled derived-storage or worker/runtime coherence

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- full viewer polish such as zoom/pan/rotate UX refinement beyond the minimal alive path
- advanced document-library UX
- dedicated ingest-status route with retry workflows
- extraction retry lineage deepening
- preprocessing, layout segmentation, transcription, privacy, manifest, export, provenance, or discovery work
- raw original delivery

## Testing and validation
Before finishing:
1. Verify PDF extraction page count correctness.
2. Verify multi-page TIFF handling.
3. Verify single-image import becomes one page.
4. Verify derived page and thumbnail assets are created in the controlled derived-storage layout.
5. Verify page and thumbnail checksums are captured.
6. Verify upload -> extraction -> thumbnail flow becomes alive through the existing jobs framework.
7. Verify canceled extraction marks unfinished pages as `CANCELED`.
8. Verify page list, page detail, and image endpoints work and remain RBAC-protected.
9. Verify document timeline now includes extraction and thumbnail attempts accurately.
10. Verify the viewer route can open a real ready page or shows an accurate not-ready/failure state.
11. Verify no raw original download path was introduced.
12. Verify docs match the implemented lifecycle and endpoints.
13. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- pages are generated for supported inputs
- thumbnails are generated
- append-only document processing runs exist
- timeline now covers upload, scan, extraction, and thumbnail stages
- page and image APIs are real and secure
- document detail exposes extracted page count, thumbnail availability, and processing timeline from persisted records
- the controlled no-raw-original posture is preserved
- later viewer and preprocessing prompts have a stable page-asset foundation
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

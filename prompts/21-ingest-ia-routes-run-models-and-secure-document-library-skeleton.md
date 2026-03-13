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
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-01-ingest-document-viewer-v1.md`
3. Then review the current repository generally — code, routes, layouts, APIs, shared UI, contracts, tests, workers, storage adapters, docs, and any prior implementation artifacts — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second document shell, a second route family, or conflicting document-domain models.

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
- `/phases` wins for route ownership, document-domain semantics, shell composition, upload/viewer boundaries, controlled-storage posture, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the browser-native web-first translation. Do not drift into desktop-only assumptions, raw file access shortcuts, or consumer-style document UX.

## Objective
Stand up the ingest information architecture, routes, lifecycle models, and secure document-library skeleton.

This prompt owns:
- the canonical document route family under project scope
- the initial document-domain persistence and shared contracts
- the document library skeleton
- the import-route skeleton
- the document-detail skeleton
- the viewer-route skeleton
- baseline read APIs for document list, detail, and timeline
- route-safe empty/loading/error/not-found states for the document family
- secure controlled-only posture with no raw-original download affordances

This prompt does not own:
- the real multipart upload pipeline
- malware scanning implementation
- full immutable-source-record hardening
- page extraction jobs or thumbnail generation
- full document-library ergonomics such as advanced filtering, sorting, and bulk actions
- the full viewer interaction model such as zoom/pan/rotate polish

## Phase alignment you must preserve
From Phase 1 Iteration 1.0 and the early document route contract:

### Required route ownership
Create or reconcile the browser route family:
- `/projects/:projectId/documents`
- `/projects/:projectId/documents/import`
- `/projects/:projectId/documents/:documentId`
- `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`

Rules:
- the Documents library is the default primary workspace
- Import is a dedicated route and CTA from the Documents page header
- do not add nested side-nav structure for Library/Import
- the browser `page` query parameter is human-facing and 1-based

### Required shell and page composition
Preserve:
- the global authenticated shell
- the project-scoped shell
- one page header with one primary action
- list + details composition for the library family
- single-fold workspace composition for the viewer route, even if the viewer is not yet feature-complete

### Required document-domain posture
You need the domain skeleton now so later work can build on it.

At minimum reconcile the phase-compatible domain models for:
- `documents`
  - `id`
  - `project_id`
  - `original_filename`
  - `stored_filename`
  - `content_type_detected`
  - `bytes`
  - `sha256`
  - `page_count`
  - `status` (`UPLOADING | QUEUED | SCANNING | EXTRACTING | READY | FAILED | CANCELED`)
  - `created_by`
  - `created_at`
  - `updated_at`
- `document_imports`
  - `id`
  - `document_id`
  - `status` (`UPLOADING | QUEUED | SCANNING | ACCEPTED | REJECTED | FAILED | CANCELED`)
  - `failure_reason`
  - `created_by`
  - `accepted_at`
  - `rejected_at`
  - `canceled_by`
  - `canceled_at`
  - `created_at`
  - `updated_at`

Because later upload and lineage work deepens behavior in this area, fields that are only populated after real upload may remain nullable for now if needed, but the shape and enums must already be consistent and safe to extend.

### Required library skeleton contract
The library skeleton must already reflect the later product shape:
- page header with title and primary CTA `Import document`
- table-oriented primary surface
- columns prepared for:
  - Name
  - Status
  - Pages
  - Uploaded by
  - Date
- row selection path
- details surface or drawer path
- empty/loading/error states that feel calm and serious
- no raw-original download action anywhere

### Required document detail contract
The document detail route must already support:
- metadata region
- current ingest status region
- timeline region
- safe next-step actions
- future handoff to viewer
- future handoff to ingest-status timeline deepening

At this stage, it may remain a skeleton where underlying data is not yet complete, but it must not fake nonexistent extraction/viewer readiness.

### Required viewer skeleton contract
The viewer route must already exist and preserve:
- page query normalization
- single-fold workspace shell composition
- toolbar slot
- filmstrip slot
- canvas slot
- inspector slot or drawer path
- empty/loading/not-ready/error states
- no raw original file access
- no page-level vertical sprawl in the default shell state

Do not fully build viewer mechanics here. That belongs later.

## Implementation scope

### 1. Document-domain schema and shared contracts
Implement or reconcile the baseline persistence and contract layer for the document family.

Requirements:
- add or reconcile phase-compatible `documents` and `document_imports` models/migrations
- centralize status enums and DTOs in the shared contract layer where the repo already uses one
- keep the schema ready for upload, lineage, and extraction work
- do not invent a second competing schema for the same concepts
- avoid premature over-modeling that conflicts with the phase contract

If the repo already has a document model, migrate or refine it toward the phase shape instead of replacing it wholesale.

### 2. Baseline read APIs
Implement or refine consistent project-scoped read APIs for the document family.

At minimum support:
- `GET /projects/{projectId}/documents`
- `GET /projects/{projectId}/documents/{documentId}`
- `GET /projects/{projectId}/documents/{documentId}/timeline`

Requirements:
- all routes are project-RBAC protected
- response contracts are typed
- empty states are explicit and safe
- missing documents return safe not-found behavior
- the list endpoint is future-compatible with later filter/sort/search expansion
- timeline is a real surface, but it may accurately return an empty or pre-ingest placeholder state before later work deepens it

If appropriate, you may also reserve:
- `GET /projects/{projectId}/document-imports/{importId}`
but do not fake live upload behavior yet unless it already exists.

### 3. Documents library web surface
Implement or refine:
- `/web/app/(authenticated)/projects/[projectId]/documents/page.tsx`

Requirements:
- uses the canonical authenticated/project shell
- has a clear page title
- has one primary CTA: `Import document`
- presents a calm document table skeleton that can evolve later
- supports row selection or equivalent list->detail affordance
- uses shared state patterns for zero/empty/loading/error
- does not include advanced bulk action clutter yet
- does not include nested side-nav for import
- remains sleek, dark, minimal, and serious

If the repo already has a DataTable primitive, use it. Do not invent a second table pattern.

### 4. Import route skeleton
Implement or refine:
- `/web/app/(authenticated)/projects/[projectId]/documents/import/page.tsx`

Requirements:
- dedicated route, not modal
- uses the canonical wizard/page shell pattern
- clear stepper shell prepared for:
  1. select files
  2. confirm metadata and destination project
  3. upload and status
- keyboard-safe structure
- clear placeholder states before live upload is wired
- no fake success path
- calm, premium, operational UI tone

### 5. Document detail skeleton
Implement or refine:
- `/web/app/(authenticated)/projects/[projectId]/documents/[documentId]/page.tsx`

Requirements:
- metadata section
- ingest status section
- timeline section
- actions area prepared for:
  - `Open document`
  - `View ingest status`
- the actions must stay explicit:
  - if no pages exist yet, do not pretend the viewer is ready
  - if upload state is incomplete, show that cleanly
- detail page must feel like part of the same product shell, not an ad hoc placeholder

### 6. Viewer route skeleton
Implement or refine:
- `/web/app/(authenticated)/projects/[projectId]/documents/[documentId]/viewer/page.tsx`

Requirements:
- route exists and is deep-link-safe
- normalizes `page` query handling as 1-based in the URL
- preserves the future workspace structure:
  - toolbar
  - filmstrip
  - canvas
  - inspector/drawer
- bounded work-region layout only
- no full viewer implementation yet
- no raw-original access path
- safe processing/not-ready/error states

### 7. Breadcrumbs, route context, and shell integration
Integrate the document family into the current shell cleanly.

Requirements:
- breadcrumbs provide orientation only
- examples remain phase-compatible:
  - `Projects -> Project -> Documents`
  - `Projects -> Project -> Documents -> Document`
  - `Projects -> Project -> Documents -> Document -> Viewer -> Page N`
- nav highlight remains correct
- page headers remain consistent
- deep links are reload-safe

### 8. Security posture
Preserve the secure-environment posture for document routes from day one.

Requirements:
- no raw-original download controls in UI
- no original-object direct URL assumptions
- all document routes remain protected by project membership
- do not leak document metadata across projects
- do not introduce public asset paths

### 9. Audit and observability alignment
Where already supported by the repo with minimal disruption, emit or reconcile view events for:
- `DOCUMENT_LIBRARY_VIEWED`
- `DOCUMENT_DETAIL_VIEWED`
- `DOCUMENT_TIMELINE_VIEWED`

If the existing audit layer is already in place, use it.
Do not create a second audit path.

### 10. Documentation
Document:
- the document route family
- the baseline document-domain models
- the list/detail/viewer skeleton ownership
- what later work is expected to add
- the explicit no-raw-original posture for the document family

## Required deliverables

### Backend / contracts
- document and document-import models/migrations
- typed DTOs/contracts
- list/detail/timeline read APIs
- tests

### Web
- `/projects/:projectId/documents`
- `/projects/:projectId/documents/import`
- `/projects/:projectId/documents/:documentId`
- `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`
- shell/breadcrumb/page-header integration
- empty/loading/error/not-found states

### Docs
- document-route and information architecture contract doc
- document-domain baseline model doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/api/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small shell/table/drawer/viewer-shell refinements are needed
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- the real upload pipeline
- malware scanning
- quota enforcement
- immutable source-record hardening beyond baseline schema readiness
- extraction jobs
- thumbnail generation
- full document-library filtering, sorting, or bulk operations
- full viewer zoom/pan/rotate behavior
- any raw original file delivery path

## Testing and validation
Before finishing:
1. Verify all document routes exist and render inside the canonical shell.
2. Verify `/projects/:projectId/documents` behaves correctly for empty state and seeded state if fixtures exist.
3. Verify `/projects/:projectId/documents/import` exists as a dedicated route and is keyboard-safe.
4. Verify `/projects/:projectId/documents/:documentId` handles existing, missing, and unauthorized cases safely.
5. Verify `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}` normalizes the page query safely and remains bounded-layout.
6. Verify no raw-original download affordance or public asset path was introduced.
7. Verify breadcrumbs and route context are consistent.
8. Verify docs match the actual routes, models, and current non-goals.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the document route family is real
- the baseline document-domain schema is real
- the library, import, detail, and viewer routes exist as consistent shells
- library/import/detail/viewer routes mount under the canonical product shell with consistent header/breadcrumb contracts
- the no-raw-original posture is preserved
- document route params and baseline domain contracts are documented and validated by contract tests
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

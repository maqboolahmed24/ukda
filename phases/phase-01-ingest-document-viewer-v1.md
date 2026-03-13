# Phase 1: Ingest + Document Viewer v1 (Industry-Grade UI/UX + Secure Ingestion) - The Originals

> Status: ACTIVE
> Web Root: /web
> Active Phase Ceiling: 11
> Execution Policy: Phase 0 through Phase 11 are ACTIVE for this prompt program.
> Web Translation Overlay (ACTIVE): preserve existing workflow intent and phase semantics while translating any legacy desktop or WinUI terms into equivalent browser-native routes, layouts, and interaction patterns under /web.

## Phase Objective
A `RESEARCHER` can:

1. Import scans into a project (`PDF`, `TIFF`, `JPG`, `JPEG`, `PNG`).
2. Store originals in Controlled storage.
3. Extract pages and thumbnails.
4. Browse and view pages with zoom, pan, and rotate.
5. Operate with full auditability and no raw scan download path.

## Entry Criteria
Start Phase 1 only when all are true:
- Phase 0 authentication, RBAC, audit logging, jobs, and no-egress controls are active.
- Controlled object storage and authenticated asset-delivery patterns are available.
- Export-request endpoints remain stubbed; no external egress path is enabled yet.

## Scope Boundary
Phase 1 owns secure ingest, document inventory, page extraction, and controlled document viewing.

Out of scope for this phase:
- deterministic preprocessing derivatives and quality triage (Phase 2)
- layout segmentation and reading-order modelling (Phase 3)
- transcription, privacy review, manifests, policy authoring, and export release decisions (Phases 4 through 8)

## Phase 1 Non-Negotiables
- Secure web application is the active delivery target: preserve phase behavior and governance contracts while implementing browser-native interaction, routing, and layout patterns from first principles (no desktop-mechanics carryover).
- All workspace and page surfaces inherit the canonical `Obsidian Folio` experience contract (dark-first Fluent 2 tokens, app-window adaptive states, single-fold defaults, keyboard-first accessibility); see `ui-premium-dark-blueprint-obsidian-folio.md`.
1. Original uploads remain in Controlled storage and are never exposed through raw-download URLs.
2. Malware scanning, quota checks, and ingest validation block unsafe files before downstream processing.
3. All ingest, extraction, and viewing lifecycle events are auditable.
4. The viewer remains focused on document access and navigation, not later-phase review tooling.

## Iteration Model
Build Phase 1 as five iterations (`1.0` to `1.4`). Each iteration must ship a working, production-progressive system.

## Iteration 1.0: Web-First Premium Dark Baseline + Information Architecture

### Goal
Lock route hierarchy, layout composition patterns, navigation model, shared web component library, and accessibility standards before feature-heavy pages are built.

### Web Client Work
#### Product IA: Route Map and Hierarchy
Route notation contract:

- Browser URL examples use `:param` notation in this section.
- App Router filesystem examples later in this phase use `[param]` folder notation for the same URL contract.
- Browser `page` query parameters are human-facing 1-based page numbers; persisted `page_index` values remain 0-based unless a field is explicitly named `page_index`.

#### 1) Global route groups
Public/system routes:

- `/` (lightweight root route: redirect unauthenticated users to `/login` and authenticated users to `/projects`)
- `/login`
- `/auth/callback`
- `/logout`
- `/health` (optional diagnostic UI page backed by `/healthz`; API readiness remains `/readyz`)
- `/error` (safe error UX)

Authenticated routes:

- `/projects`
- `/admin` (`ADMIN` area with read-only `AUDITOR` governance screens and per-screen restrictions)

#### 2) Project-scoped routes
- `/projects/:projectId/overview`
- `/projects/:projectId/documents`
- `/projects/:projectId/documents/import`
- `/projects/:projectId/documents/:documentId`
- `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`
- `/projects/:projectId/jobs`
- `/projects/:projectId/activity`
- `/projects/:projectId/settings` (`PROJECT_LEAD` and `ADMIN` only)

`/projects/:projectId/activity` is a project-scoped activity/governance surface. It does not replace the optional current-user `/activity` route introduced in Phase 0.

#### 3) Breadcrumb hierarchy
Rules:

- Breadcrumbs provide orientation only.
- Breadcrumbs are not an action menu.

Examples:

- `Projects -> Project A -> Documents`
- `Projects -> Project A -> Documents -> Document: Diary_1871.pdf`
- `Projects -> Project A -> Documents -> Document -> Viewer -> Page 12`

#### Navigation Model
#### 1) Persistent UI shell
Use a consistent shell across project pages:

- top header
- left side navigation
- main content
- optional right panel/drawer

#### 2) Header bar behavior
Header contents:

- product identity (`UKDataExtraction (UKDE)`)
- project switcher
- deployment environment label (for example Development, Staging, Production)
- project access-tier badge (for example Controlled, Safeguarded, Open)
- help entry point
- user menu

Rules:

- No page primary CTA in the global header.
- Global utilities belong in header; workflow actions belong in page headers.

#### 3) Left side navigation behavior
Project scope nav items:

- Overview
- Documents
- Jobs
- Activity
- Settings (permission-based)

Rules:

- Side nav contains links only.
- No CTAs in side nav (for example `Import document` stays in Documents page header).
- Current section highlighted.
- Collapsible on smaller viewports.
- No deep nesting in Phase 1.

#### 4) Within-section navigation
For Documents:

- Library is default primary workspace.
- Import is a dedicated route and CTA from library.

Rules:

- Do not add nested side-nav structure for Library/Import in Phase 1.
- Use progressive disclosure for secondary tasks.

#### Page Composition Patterns
#### Pattern A: Web App Shell + Page Header
Used by:

- Overview
- Documents Library
- Jobs
- Activity
- Settings

Structure:

- sticky global header
- left side nav
- main content area
- page header (title, status, primary CTA)
- body sections/cards

Rules:

- One clear page title as visual anchor.
- Primary CTA at top-right of page header.
- Secondary actions in overflow menu.

#### Pattern B: List + Details (master-detail)
Used by:

- Documents Library

Structure:

- filter/search row
- data table primary canvas
- right details drawer on row selection

Rules:

- Table used for data, not layout.
- Sorting and pagination supported.

#### Pattern C: Wizard flow
Used by:

- Import flow

Structure:

- page header
- stepper (3-4 steps max)
- form content card
- optional guidance panel (limits, allowed formats)

#### Pattern D: Single-Fold Workspace Composition
Used by:

- Viewer
- Later high-density workspaces that inherit the Phase 1 workspace contract

Goal:

- Present the primary task surface inside one fold with no routine page-level vertical scrolling in the default state.

Single-fold rules:

- The workspace resolves to one client-area fold: global header + page header + workspace body = available viewport height.
- Bind layout to the available app-window and browser viewport client area; prefer dynamic viewport sizing (`100dvh`) with `100vh` fallback where needed.
- The page shell does not grow vertically to reveal more primary-task UI; overflow is absorbed through state changes, drawers, flyouts, or bounded secondary regions.
- Vertical scrolling is reserved for clearly bounded high-density regions (for example virtualized tables, transcript lists, findings lists, or filmstrips), not the entire workspace.
- Accessibility override: when zoom, text-spacing, or assistive settings require reflow, controlled scrolling is allowed rather than clipping, overlapping, or obscuring content.

State model:

- `Expanded`: left rail, center canvas, and right inspector are all visible.
- `Balanced`: rail narrows and inspector compresses to summary content.
- `Compact`: inspector becomes a flyout or drawer and the rail reduces to a compact strip.
- `Focus`: the active work surface takes priority and secondary panes become on-demand overlays.
- Transitions between states are driven by available window size and task context, not by fixed device labels.

Adaptive spatial architecture:

- Use a modular grid with wide, balanced, compact, and focus states rather than one static composition.
- Side rails collapse before the center work surface gives up functional space.
- Toolbar remains a single row; low-frequency commands move into overflow or contextual command surfaces.
- Panels use resize limits, snap points, and remembered widths.
- Tables, lists, and filmstrips are virtualized or paged rather than extending total page height.

Minimalist visual language:

- Use a restrained, low-noise backdrop with deliberate negative space and thin separators.
- Long-lived frame surfaces use a subtle premium backdrop treatment; transient drawers, menus, and contextual command surfaces may use a lighter glass treatment.
- Limit the visible type system to page title, section label, body strong, and body.
- Use one accent family, a tightly controlled neutral palette, and no more than three elevation tiers.
- The document canvas remains the focal plane; chrome recedes until hovered, focused, or invoked.

Workflow friction reduction:

- Command hierarchy is explicit: shell navigation -> page header -> contextual command bar -> right-click or overflow menu.
- Keep one primary action visible per surface; secondary and destructive actions live in labeled overflow or contextual menus.
- Use progressive disclosure for advanced options, diagnostics, and low-frequency metadata.
- Every contextual command must also be reachable from a non-context-menu path.
- Keyboard-first behavior is required: roving focus in toolbars, stable shortcut registration, panel-toggle shortcuts, predictable escape behavior, and zero keyboard traps.

Micro-interactions and depth:

- Motion is functional, never decorative; it confirms causality, preserves orientation, and reinforces hierarchy.
- Use short transitions for hover, press, selection, panel reveal, save confirmation, and state change feedback.
- Prefer subtle scale, opacity, blur, and elevation shifts over long-distance movement.
- Preserve spatial continuity when moving from list -> document -> page workspace or from finding -> detail.
- Respect reduced-motion and reduced-transparency preferences automatically.

Accessibility:

- Toolbar follows ARIA toolbar interaction model.
- Focus indicators remain obvious against tinted or glass surfaces.
- Sticky headers, drawers, and flyouts must never fully obscure the current keyboard focus target.
- The single-fold principle must not break WCAG reflow, focus visibility, or keyboard usability requirements.

#### Obsidian Folio Experience Foundations (Browser-Native)
#### 1) Token system and theme contracts
Use shared `/packages/ui` tokens and typed theme contracts (no desktop resource inheritance). Required token families:

- `colors`: dark-first neutral and accent ramps plus semantic status colors
- `typography`: page title, section label, body strong, and body scales aligned to Fluent 2 guidance
- `spacing`: 4px/8px rhythm for layout and control spacing
- `shape`: corner radii, border thickness, and divider styles
- `elevation`: capped depth tiers (`0..3`) for clear hierarchy
- `motion`: duration/easing presets and state-transition timing

#### 2) Theme modes
- dark (required default)
- light (supported)
- browser high-contrast or forced-colors support (required)

#### 3) Material and backdrop policy
- Long-lived shell or frame surfaces use restrained layered backdrops and subtle separation, not ornamental chrome.
- Transient contextual surfaces may use limited translucency or blur when supported, but only when it improves hierarchy and respects user preferences.
- Reduced-transparency preferences automatically disable non-essential translucent effects.

#### 4) Accessibility baseline
Phase 1.0 targets WCAG 2.2 AA on shell and core flows.

Minimum required:

- keyboard-accessible interactions
- no keyboard traps
- focus visible and not obscured
- robust focus styling in all key components
- semantic roles, accessible names, and state announcements exposed for core controls and command surfaces

### Component Inventory (Phase 1.0 Deliverables)
#### Layout and navigation
1. Web app shell root
2. `HeaderBar`
3. `SideNav`
4. `Breadcrumbs`
5. `PageHeader`

#### Data display
6. `DataTable`
7. `DetailsDrawer`
8. `StatusChip`

#### Forms and flows
9. `WizardShell`
10. `FileUpload`

#### Feedback and overlays
11. `Toast`
12. `InlineAlert` / `Banner`
13. `ModalDialog`

#### Workspace stubs
14. `Toolbar` (single tab stop with roving focus)
15. `CommandBarOverflow` (labeled flyout for low-frequency actions)
16. `WorkspacePaneController` (resize limits, snap points, remembered widths)
17. `ViewerWorkspaceLayout` (single-fold state model placeholder in 1.0, full behavior in 1.3)
18. `ThemeController` (`Dark | Light | System` + contrast-aware or forced-colors support + user preference persistence)
19. `WebComponentGallery` (internal route for component and interaction validation)

#### web-surface Architecture and Rules
#### Routing/layout baseline (Next.js App Router example)
- `/web/app/layout.tsx` (global providers, theme service, startup composition)
- `/web/app/(authenticated)/layout.tsx` (header, nav rail, content host, environment banner)
- `/web/app/(public)/login/page.tsx`
- `/web/app/(authenticated)/projects/page.tsx`
- `/web/app/(authenticated)/projects/[projectId]/layout.tsx` (project context + side nav)
- `/web/app/(authenticated)/projects/[projectId]/documents/page.tsx`
- `/web/app/(authenticated)/projects/[projectId]/documents/import/page.tsx`
- `/web/app/(authenticated)/projects/[projectId]/documents/[documentId]/page.tsx`
- `/web/app/(authenticated)/projects/[projectId]/documents/[documentId]/viewer/page.tsx`
- `/web/app/(authenticated)/admin/design-system/page.tsx` (internal component gallery)

#### Data fetching rules
- Single API client.
- Standard query-key conventions.
- Prefer skeleton loading over spinner-only patterns.

#### No-clutter rules
- One primary CTA per page.
- Secondary actions in overflow menus.
- Details shown in drawers or secondary routes.

### Backend Work
- `GET /me` for user profile and role context.
- Optional `GET /projects/{projectId}/navigation` (or computed client-side).
- Ensure fonts/icons/assets are bundled locally.

### Tests and Gates (Iteration 1.0)
#### Visual regression
Option A:

- browser screenshot diff with `toHaveScreenshot()`.

Option B (optional):

- web component gallery snapshot harness using mock/stub data only.

#### Accessibility gate
- browser accessibility auditing plus browser automation on key routes.
- Keyboard-flow tests for shell, nav, dialogs, and toolbar components.
- Focus-visibility and focus-not-obscured checks on dark and high-contrast themes.

#### Navigation consistency gate
- Web app shell frame is visible on every project workspace surface.
- SideNav items match spec.
- Breadcrumb present where applicable.
- PageHeader includes exactly one primary CTA.

#### Keyboard interaction gate
- Modal dialog focus trap and focus return behavior.
- Toolbar arrow-key navigation behavior.

#### Single-fold workspace gate
- Viewer workspace satisfies one-fold shell composition at supported app-window sizes with no routine page-level vertical scrolling in the default state.
- `Expanded`, `Balanced`, `Compact`, and `Focus` transitions preserve active tool context and keyboard focus.
- Overflow commands remain reachable by keyboard through labeled flyouts and non-context-menu paths.
- Accessibility override allows controlled scrolling under zoom, text-spacing, or assistive reflow conditions instead of clipping.

#### Test architecture
- Use reusable fixtures and Page Object Models as suite scales.

### Exit Criteria (Iteration 1.0)
Design system and IA deliverables:

- Web app shell frame, header bar, and side navigation are used consistently across project workflows.
- Token system implemented via shared web theme contracts with dark default.
- Core components built and documented (web component gallery recommended).
- No external CDN dependencies for UI assets.

UX/layout deliverables:

- Pattern A (web app shell default) implemented.
- Pattern B (List + Details) implemented.
- Pattern C (Wizard) implemented.
- Pattern D (single-fold workspace contract + adaptive state model) implemented.

Quality gates:

- Accessibility scans pass on key pages.
- Visual regression is enabled and green.
- Navigation consistency checks pass.
- Single-fold workspace gate passes for supported app-window sizes and controlled reflow scenarios.
- WCAG 2.2 baseline checks pass on targeted flows.

## Iteration 1.1: Secure Import v1 (Wizard Flow)

### Goal
Upload a file and produce:

- Document record in database.
- Raw object in Controlled storage.
- Audit event.
- Status visible in dedicated import flow and document details.

### Web Client Work
#### Import wizard (dedicated route, not modal)
Route:

- `/projects/:projectId/documents/import`

Steps:

1. Select files.
2. Confirm metadata and destination project.
3. Upload and status.

UX requirements:

- Clear stepper at top.
- Primary action: `Upload`.
- Secondary action: `Cancel`.
- `Cancel` is available while the import is `UPLOADING` or `QUEUED`; once `SCANNING` begins, the wizard becomes read-only and status follow-up moves to document details.
- Status progression inside the wizard: `UPLOADING -> QUEUED -> SCANNING`.
- On success, navigate to document details, where the current ingest status is visible immediately; a dedicated ingest-status surface arrives later once append-only attempt history exists.

### Backend Work
#### 1) Database changes
Add or extend:

- `documents`
  - `id (uuid)`
  - `project_id`
  - `original_filename`
  - `stored_filename` (generated)
  - `content_type_detected`
  - `bytes`
  - `sha256`
  - `page_count` (nullable)
  - `status`: `UPLOADING | QUEUED | SCANNING | EXTRACTING | READY | FAILED | CANCELED`
  - `current_import_id` (nullable)
  - `created_by`
  - `created_at`
  - `updated_at`
- `document_imports`
  - `id`
  - `document_id`
  - `attempt_number`
  - `status`: `UPLOADING | QUEUED | SCANNING | ACCEPTED | DUPLICATE | REJECTED | FAILED | CANCELED`
  - `failure_reason` (nullable)
  - `duplicate_of_document_id` (nullable)
  - `duplicate_of_import_id` (nullable)
  - `created_by`
  - `accepted_at` (nullable)
  - `duplicated_at` (nullable)
  - `rejected_at` (nullable)
  - `canceled_by` (nullable)
  - `canceled_at` (nullable)
  - `created_at`
  - `updated_at`

Authority rules:

- `document_imports` is the authoritative record for each upload and scan attempt while the import wizard is active.
- `documents.status` is the current availability projection for the canonical document record; it is derived from `current_import_id` plus later `document_processing_runs` and is not the historical source of truth.
- once Phase 1.3 append-only processing runs exist, document detail and ingest-status timelines read `document_processing_runs` only; `document_imports` remains the wizard-facing import projection rather than a second historical ledger.
- `document_imports.attempt_number` is assigned when the upload attempt is created so `/documents/{documentId}/timeline` can expose a stable `attemptNumber` before Phase 1.3 backfills those same upload or scan attempts into `document_processing_runs`.

#### 2) Controlled storage layout
- `controlled/raw/{project_id}/{document_id}/original.bin`
- `controlled/raw/{project_id}/{document_id}/source-meta.json` (optional)

Rules:

- Generate storage filenames server-side.
- Never use user-provided names as object keys.

#### 3) Import APIs
- `POST /projects/{projectId}/documents/import`
  - accepts multipart upload
  - computes `sha256` while streaming
  - performs server-side magic-byte detection
  - does not trust client `Content-Type`
  - enforces extension/type allowlist and size/quota limits
  - detects same-project duplicates by `(project_id, sha256, content_type_detected)` before committing a second raw object
  - when a matching non-terminal or ready document already exists, creates a `document_imports` row with `status = DUPLICATE`, populates `duplicate_of_document_id` and `duplicate_of_import_id` when known, returns the existing `documentId`, and does not store a second copy of the raw bytes
  - returns `documentId`, `importId`, and current processing status
- `GET /projects/{projectId}/document-imports/{importId}`
  - returns wizard-safe import status transitions and any failure reason while the import is still active
- `POST /projects/{projectId}/document-imports/{importId}/cancel`
  - allowed only while the import is `UPLOADING` or `QUEUED`
  - transitions both the import and its document record to `CANCELED` when scanning has not yet started
- `GET /projects/{projectId}/documents`
- `GET /projects/{projectId}/documents/{documentId}`
- `GET /projects/{projectId}/documents/{documentId}/timeline`
  - returns a stable append-only attempt list with `runKind`, `attemptNumber`, `status`, `createdAt`, `startedAt`, `finishedAt`, and `failureReason`
  - upload and scan history is exposed through that same response shape from the first release, and Phase 1.3 extends the same list with extraction and thumbnail attempts from append-only `document_processing_runs` rows rather than changing endpoint semantics later

#### 4) Security controls
- Allowlist: `PDF`, `TIFF`, `PNG`, `JPG`, `JPEG`.
- Server-side type detection.
- Max file size and per-project quota checks.
- RBAC for `PROJECT_LEAD`, `RESEARCHER`, and `REVIEWER` upload.
- Non-executable object storage policy.

#### 5) Audit events
- `DOCUMENT_UPLOAD_STARTED`
- `DOCUMENT_STORED`
- `DOCUMENT_SCAN_STARTED`
- `DOCUMENT_UPLOAD_CANCELED`
- `DOCUMENT_SCAN_PASSED`
- `DOCUMENT_SCAN_REJECTED`
- `DOCUMENT_DUPLICATE_DETECTED`
- `DOCUMENT_IMPORT_FAILED`

### Tests and Gates (Iteration 1.1)
#### Unit
- Unsupported extension rejected.
- Mismatched detected type rejected.
- Size limit enforced.
- `sha256` correctness.
- Generated filenames do not use user input.
- RBAC upload guard enforced.
- Upload audit events emitted.

#### Integration
- Upload stores object in `controlled/raw/...`.
- `GET /projects/{projectId}/document-imports/{importId}` reflects `UPLOADING -> QUEUED -> SCANNING` while the wizard is active.
- DB document row includes checksum and transitions to `SCANNING` after upload handoff.
- Non-member upload denied.
- Canceled import never transitions into scan or extraction jobs.

#### E2E
- Complete `/documents/import` flow and land on document details page.

#### UI quality gates
- Keyboard-only wizard completion works.
- Visual regression for wizard empty/uploading/error states.

### Exit Criteria (Iteration 1.1)
Secure upload is reliable, auditable, and delivered through a dedicated, accessible wizard flow.

## Iteration 1.2: Document Library (Table + Filters + Details Drawer)

### Goal
Ship a full document management experience instead of a basic list.

### Web Client Work
Route:

- `/projects/:projectId/documents`

Library requirements:

- `DataTable` columns:
  - Name
  - Status
  - Pages
  - Uploaded by
  - Date
- Filter bar:
  - status
  - uploader
  - date range
- Search input.
- Right-side `DetailsDrawer` on row selection with:
  - metadata
  - processing timeline
  - primary CTA `Open document`
  - secondary action `View ingest status`
    - opens `/projects/:projectId/documents/:documentId` in Iteration 1.2; Iteration 1.4 adds a dedicated ingest-status route backed by append-only processing attempts

### Backend Work
- Upgrade list endpoint:
  - `GET /projects/{projectId}/documents?search={search}&status={status}&uploader={uploader}&from={from}&to={to}&sort={sort}&cursor={cursor}`
- Server-side pagination and sorting.
- Cursor-based paging for large datasets.

### Tests and Gates (Iteration 1.2)
#### Unit
- Pagination behavior.
- Filtering behavior.
- Sorting behavior.

#### Integration
- Search/filter/sort combinations return expected dataset slices.

#### E2E
- Filters update results.
- Row selection opens details drawer.
- `Open document` deep-links correctly.

#### UI quality gates
- Table row focus behavior is keyboard-safe.
- Drawer focus trap and return focus behavior work.
- Visual regression for empty/loading/filtered states.

### Exit Criteria (Iteration 1.2)
Document discovery and management are efficient and scalable for growing project collections.

## Iteration 1.3: Page Extraction + Viewer Workspace v1

### Goal
Convert uploaded files into page assets and provide a dedicated viewer workspace.

### Backend Work
#### 1) Pages model
Add `pages`:

- `id`
- `document_id`
- `page_index` (0-based)
- `width`
- `height`
- `dpi` (optional)
- `status`: `PENDING | READY | FAILED | CANCELED`
- `active_extraction_run_id` (nullable until a successful extraction attempt materializes the current page image)
- `active_thumbnail_run_id` (nullable until a successful thumbnail attempt materializes the current page thumbnail)
- `derived_image_key` (nullable until extraction succeeds)
- `derived_image_sha256` (nullable until extraction succeeds)
- `thumbnail_key` (nullable until thumbnail rendering succeeds)
- `thumbnail_sha256` (nullable until thumbnail rendering succeeds)
- `failure_reason` (nullable)
- `canceled_by` (nullable)
- `canceled_at` (nullable)
- `created_at`
- `updated_at`

Add `page_viewer_preferences`:

- `page_id`
- `document_id`
- `project_id`
- `user_id`
- `rotation_degrees` (default `0`)
- `updated_at`

Viewer-state rule:

- one logical `page_viewer_preferences` row exists per `(page_id, user_id)` pair; viewer-state writes are idempotent upserts rather than append-only duplicates

#### 2) Jobs and extraction pipeline
Create jobs:

- `EXTRACT_PAGES(document_id)`
- `RENDER_THUMBNAILS(document_id)`

Flow:

1. Read raw object from `controlled/raw/...`.
2. PDF: rasterize pages to `PNG`.
3. Multi-page TIFF: split frames.
4. Single image: one page.
5. Write extracted page images:
   - `controlled/derived/{project_id}/{document_id}/pages/{page_index}.png`
6. `RENDER_THUMBNAILS(document_id)` reads those persisted page images and writes:
   - `controlled/derived/{project_id}/{document_id}/thumbs/{page_index}.jpg`
7. Update page/document status.
8. If extraction is canceled mid-run, any unfinished `pages` rows transition to `CANCELED` instead of remaining indefinitely `PENDING`.

Add `document_processing_runs`:

- `id`
- `document_id`
- `run_kind` (`UPLOAD | SCAN | EXTRACTION | THUMBNAIL_RENDER`)
- `attempt_number`
- `supersedes_processing_run_id` (nullable)
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `created_by`
- `created_at`
- `started_at`
- `finished_at`
- `canceled_by` (nullable)
- `canceled_at` (nullable)
- `failure_reason` (nullable)

Rules:

- Phase 1.3 backfills or records `UPLOAD` and `SCAN` attempts in `document_processing_runs` so `/documents/{documentId}/timeline` and `/processing-runs` share one canonical history shape
- upload and scan backfill preserves the originating `document_imports.attempt_number`, while later extraction, thumbnail, and retry attempts continue the same append-only `attempt_number` sequence per `(document_id, run_kind)` lineage
- document detail timelines in Phase 1 read append-only upload, scan, extraction, and thumbnail attempts from `document_processing_runs`
- extraction and thumbnail jobs append new `document_processing_runs` rows instead of encoding later-stage progress only on the `documents.status` field
- `document_imports` remains the active import-attempt projection for wizard UX, while `document_processing_runs` is the authoritative append-only ledger after handoff
- `EXTRACT_PAGES` owns `derived_image_key` and `derived_image_sha256`; `RENDER_THUMBNAILS` owns `thumbnail_key` and `thumbnail_sha256`. The two jobs must not both write thumbnail artefacts for the same page lineage.
- `pages.active_extraction_run_id` and `pages.active_thumbnail_run_id` pin which successful `document_processing_runs` attempt produced the currently projected page image and thumbnail. Retries append new processing-run rows, but the page projection updates those active run IDs only when a replacement extraction or thumbnail attempt succeeds.

#### 3) Viewer APIs
- `GET /projects/{projectId}/documents/{documentId}/pages`
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}`
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}/image?variant={variant}` where `variant` is `full` or `thumb`
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}/viewer-state`
- `PATCH /projects/{projectId}/documents/{documentId}/pages/{pageId}/viewer-state` for user-scoped viewer preferences (for example rotation)

Rules:

- Serve page assets through authenticated streaming or same-origin asset proxy endpoints.
- No raw original download endpoint.
- Page metadata and failure state for the right inspector come from `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}` rather than being inferred from image reads.
- rotation changes update `page_viewer_preferences` for the current authenticated user only; they do not mutate shared `pages` rows or alter another user's viewer state
- `PATCH /viewer-state` is an upsert keyed by `(page_id, user_id)` and must not create multiple current preference rows for the same viewer on the same page

#### 4) Audit events
- `DOCUMENT_PAGE_EXTRACTION_STARTED`
- `DOCUMENT_PAGE_EXTRACTION_COMPLETED`
- `DOCUMENT_PAGE_EXTRACTION_FAILED`
- `DOCUMENT_LIBRARY_VIEWED`
- `DOCUMENT_DETAIL_VIEWED`
- `DOCUMENT_TIMELINE_VIEWED`
- `PAGE_METADATA_VIEWED`
- `PAGE_IMAGE_VIEWED` for every authenticated `variant=full` page-image response
- `PAGE_THUMBNAIL_VIEWED` may be sampled for high-volume filmstrip access because thumbnails are navigational hints rather than the auditable evidence view

### Web Client Work
Routes:

- `/projects/:projectId/documents/:documentId`
- `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`

Viewer workspace layout:

- Inherits Iteration 1.0 Pattern D single-fold contract and adaptive states (`Expanded | Balanced | Compact | Focus`).
- Top toolbar: zoom, fit width, rotate, previous/next page.
- Left rail: thumbnail filmstrip (collapsible first before canvas reduction).
- Center canvas: page image as the priority surface across all states.
- Right inspector drawer (v1 optional): page metadata/status; on narrow windows this moves to a flyout or drawer without expanding overall page height.

Viewer behavior rules:

- State transitions are driven by available browser-window size and task context, not device labels.
- Vertical scrolling remains bounded to high-density regions (for example filmstrip) rather than the full workspace in default conditions.
- Panels retain resize constraints, snap points, and remembered widths where supported.

Keyboard support:

- left/right arrows: page navigation when the canvas or filmstrip owns focus; when the toolbar owns focus, those keys stay inside the roving-focus toolbar model
- `+` / `-`: zoom
- `R`: rotate
- toolbar arrow-key navigation pattern for controls

### Tests and Gates (Iteration 1.3)
#### Unit
- PDF extraction page count correctness.
- TIFF multipage handling.
- Thumbnail dimensions/format checks.
- Derived key prefix checks.
- Viewer state transitions (zoom/rotate/navigation).

#### Integration
- Upload -> extraction -> page/thumb assets created.
- Page list and image endpoints return expected resources.
- Asset proxy re-auth or token refresh path works.
- Canceled extraction marks unfinished page rows as `CANCELED` and does not leave the viewer to infer whether a missing asset is still pending or permanently abandoned.

#### E2E
- Open viewer workspace.
- Navigate with thumbnails.
- Zoom/rotate/page nav work via mouse and keyboard.

#### UI quality gates
- Toolbar interaction follows ARIA keyboard behavior.
- Visual regression for viewer states (loading, ready, error).
- State transitions preserve focus visibility and respect reduced-motion or reduced-transparency preferences.
- Accessibility reflow scenarios allow controlled scrolling instead of clipping.

#### Performance gate
- First page render meets pilot target.
- Thumbnail strip loads within pilot target.

### Exit Criteria (Iteration 1.3)
Researchers can reliably browse long documents in a dedicated workspace.

## Iteration 1.4: Hardening + Polished Feedback

### Goal
Make ingest resilient and secure while keeping system feedback clear and usable.

### Backend Work
- Malware scanning stage before accept/extract.
- Quota enforcement:
  - max total bytes per project
  - max documents
  - max pages
- Resumable/chunk upload support for large-file deployments.
- Extend existing `document_processing_runs`:
  - retain the existing `attempt_number` field as the stable per-lineage attempt counter
  - add retry lineage through `supersedes_processing_run_id`
  - add forward retry lineage through `superseded_by_processing_run_id`
  - keep `run_kind` values `UPLOAD | SCAN | EXTRACTION | THUMBNAIL_RENDER`
  - preserve append-only attempts for timeline and retry views
- Controlled-only actions to re-run failed or canceled `SCAN`, `EXTRACTION`, or `THUMBNAIL_RENDER` attempts for `PROJECT_LEAD` and `ADMIN`.
- `POST /projects/{projectId}/documents/{documentId}/processing-runs/{runId}/retry`
  - restricted to `PROJECT_LEAD` and `ADMIN`
  - creates a new attempt with the same `run_kind` as the superseded run without changing historical upload records, appends a new `document_processing_runs` row, increments `attempt_number`, links backward through `supersedes_processing_run_id`, and records the forward link on the replaced run through `superseded_by_processing_run_id`
  - rejects retries unless the superseded run is `SCAN`, `EXTRACTION`, or `THUMBNAIL_RENDER`, so retry cannot silently fork unrelated lineage
- `POST /projects/{projectId}/documents/{documentId}/retry-extraction`
  - convenience alias for `POST /projects/{projectId}/documents/{documentId}/processing-runs/{runId}/retry` when the targeted run is the latest failed or canceled `EXTRACTION` attempt
- `GET /projects/{projectId}/documents/{documentId}/processing-runs`
- `GET /projects/{projectId}/documents/{documentId}/processing-runs/{runId}`
- `GET /projects/{projectId}/documents/{documentId}/processing-runs/{runId}/status`
- Audit events:
  - `DOCUMENT_PAGE_EXTRACTION_RETRY_REQUESTED`
  - `DOCUMENT_PROCESSING_RUN_VIEWED`
  - `DOCUMENT_PROCESSING_RUN_STATUS_VIEWED`
- Internal failure capture with safe user-facing errors.

### Web Client Work
- Dedicated ingest-status route:
  - `/projects/:projectId/documents/:documentId/ingest-status`
- Document processing timeline component:
  - reads append-only upload, scan, extraction, and thumbnail attempts from `GET /projects/{projectId}/documents/{documentId}/processing-runs`
  - `Uploaded -> Queued -> Scanning -> Extracting -> Ready`
  - failure and canceled branches preserve the last reached stage instead of implying later stages succeeded
  - active attempts poll `GET /projects/{projectId}/documents/{documentId}/processing-runs/{runId}/status` instead of repeatedly reloading the full run-detail payload
- Retry actions for allowed roles (`PROJECT_LEAD` and `ADMIN`).
- Quota and validation errors shown inline and actionable.
- Network interruption UX for upload resume.

### Tests and Gates (Iteration 1.4)
#### Unit
- Quota enforcement tests.
- Scan failure routing (reject and prevent extraction).
- Chunk assembly + final checksum validation.

#### Integration
- Simulated malware sample rejected.
- No page generation for rejected uploads.
- Interrupted upload resume succeeds.
- retrying failed `SCAN`, `EXTRACTION`, or `THUMBNAIL_RENDER` runs creates a new same-kind attempt instead of mutating the failed run
- processing-run retries increment `attempt_number` and preserve both `supersedes_processing_run_id` and `superseded_by_processing_run_id`
- full page-image reads emit unsampled `PAGE_IMAGE_VIEWED` audit events

#### E2E
- Large upload with connection drop and resume.
- Retry path for failed scan, extraction, and thumbnail runs by `PROJECT_LEAD` or `ADMIN`.

#### Security gates
- Upload validation controls remain enforced.
- Scan failure blocks downstream processing.
- No direct export or raw-download bypass introduced.

#### UI quality gates
- Visual regression for hard-failure and retry states.
- Accessibility checks still pass on timeline and error surfaces.

### Exit Criteria (Iteration 1.4)
Ingest is resilient, scanned, quota-controlled, and operationally clear for users.

## Handoff to Later Phases
- Phase 2 consumes Phase 1 page assets and viewer shells to build deterministic preprocessing and quality comparison.
- No later phase may add a raw-original download path or bypass the Controlled asset-delivery rules established here.

## Phase 1 Definition of Done

### Functional
- A `RESEARCHER` can import scans (`PDF`, `TIFF`, `JPG`, `JPEG`, `PNG`).
- Originals stored in Controlled storage.
- Pages and thumbnails are generated and viewable.
- Document library, details, and viewer workspace are fully functional.
- Viewer supports zoom, pan, rotate, and keyboard navigation.

### Security and governance
- No raw original scan download endpoint.
- All routes are protected by project RBAC.
- Audit events cover upload, scan acceptance/rejection, extraction, and view lifecycle.
- Architecture remains aligned with controlled-environment behavior.

### UI/UX quality gates
- Visual regression suites for core Phase 1 flows are green.
- Accessibility gates pass for keyboard and focus behavior.
- Navigation and layout remain consistent across project routes.
- Design-system shell, route map, and composition patterns from Iteration 1.0 remain the foundation for all Phase 1 surfaces.

### Engineering quality gates
- Unit, integration, and E2E suites are green.
- Upload security controls and hardening checks are enforced.
- Pilot performance targets for extraction and viewer responsiveness are met.

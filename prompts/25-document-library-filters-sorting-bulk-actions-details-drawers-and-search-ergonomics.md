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
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-01-ingest-document-viewer-v1.md`
3. Then review the current repository generally — document routes, table primitives, drawer primitives, typed API client/contracts, document APIs, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second document-library UI, a second table system, or conflicting list/detail patterns.

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
- `/phases` wins for document-library route ownership, filters, details-drawer behavior, shell composition, keyboard rules, and acceptance logic.
- Official docs win only for implementation mechanics.
- Keep the library calm, dense, minimal, and operational. Do not drift into noisy admin-grid aesthetics or consumer-style file-manager clutter.

## Objective
Build the document library with filters, sorting, bulk actions, details drawers, and crisp search ergonomics.

This prompt owns:
- the real Phase 1.2 document library experience
- server-side search, filters, sorting, and cursor paging
- a production-grade document table
- row selection and details-drawer flow
- restrained bulk-selection and bulk-action infrastructure
- URL-driven filter/search/sort state
- crisp empty/loading/error/no-results states
- keyboard-safe list/detail behavior

This prompt does not own:
- upload workflow implementation
- extraction generation
- full viewer feature work
- a dedicated ingest-status route if it does not yet exist
- destructive bulk actions not yet backed by safe server capabilities
- raw original download

## Phase alignment you must preserve
From Phase 1 Iteration 1.2:

### Required route
- `/projects/:projectId/documents`

### Required library table
The primary surface is a `DataTable` with columns:
- Name
- Status
- Pages
- Uploaded by
- Date

### Required filter/search contract
- Search input
- Filter bar:
  - status
  - uploader
  - date range
- Server-side sorting
- Cursor-based paging for large datasets

### Required details-drawer contract
Right-side `DetailsDrawer` on row selection with:
- metadata
- processing timeline
- primary CTA `Open document`
- secondary action `View ingest status`
  - in Phase 1.2 this may open `/projects/:projectId/documents/:documentId`
  - if the dedicated ingest-status route already exists in the repo, use it instead of inventing a parallel path

### Required quality gates
- table row focus behavior is keyboard-safe
- drawer focus trap and return focus behavior work
- visual regression for empty/loading/filtered states

### Bulk-action rule for this prompt
The backlog title calls for bulk actions, but the phase text does not yet define broad cross-document destructive mutations.
Therefore:
- implement real multi-row selection and a restrained bulk-action rail
- only enable actions that already have safe, consistent backing in the current repo
- do not invent unsupported destructive semantics just to fill the toolbar
- if no safe bulk mutation exists yet, still ship:
  - multi-select
  - selection count
  - clear selection
  - keyboard-safe bulk-action affordance structure
  - role-aware hidden/disabled action slots prepared for later work

## Implementation scope

### 1. Upgrade the document list API
Implement or refine:
- `GET /projects/{projectId}/documents?search={search}&status={status}&uploader={uploader}&from={from}&to={to}&sort={sort}&cursor={cursor}`

Requirements:
- project-RBAC protected
- typed response contract
- server-side filtering
- server-side sorting
- cursor-based pagination
- safe defaults and bounded page sizes
- search and filter combinations behave predictably
- result metadata is sufficient for paging and UI state

Do not break existing document list consumers; reconcile them.

### 2. Canonical URL-state behavior for the library
Implement explicit URL-state ownership for:
- `search`
- `status`
- `uploader`
- `from`
- `to`
- `sort`
- `cursor`

Requirements:
- reload-safe
- back/forward-safe
- shareable internal URLs
- malformed params degrade safely
- filter resets behave predictably
- no hidden client-only filter state that conflicts with the URL

### 3. Document table experience
Implement or refine the `/projects/:projectId/documents` table surface.

Requirements:
- use the canonical shell and page-header pattern
- page title is clear
- one primary CTA remains `Import document`
- table uses the shared DataTable primitive if present
- strong row focus
- selection model supports:
  - single-row selection for drawer open
  - multi-row selection for the bulk-action rail
- sorting controls are clear and restrained
- empty/loading/error/no-results states use the shared state language
- the UI remains calm, dark, minimal, and high-trust

### 4. Search and filter ergonomics
Implement crisp, efficient document search/filter UX.

Requirements:
- search input feels immediate but not noisy
- filter bar is compact and clear
- active filters are legible
- no giant advanced-search wall
- keyboard-safe tab order
- filter changes update results predictably
- search/filter interactions do not collapse the overall page layout
- state survives refresh and deep links

### 5. Details drawer
Implement or refine a real right-side details drawer on row selection.

Requirements:
- metadata section
- processing timeline section
- primary CTA `Open document`
- secondary action `View ingest status`
- clear loading/error handling for drawer data
- bounded internal scrolling
- focus trap and return-focus behavior
- does not expand total page height
- narrow-window behavior remains consistent with the shell's adaptive-state model

Do not turn the drawer into a second full detail page. Keep it sharp and useful.

### 6. Bulk-selection and bulk-action rail
Implement restrained bulk-action behavior.

Requirements:
- multi-select checkboxes or equivalent accessible selection affordance
- selection count
- clear selection
- role-aware bulk-action rail
- bulk actions only appear when selection is non-empty
- actions are hidden or disabled if the repo does not yet support them safely
- no unsupported destructive behavior is invented

If the current repo already exposes safe document-level bulk actions, wire them in.
If not, ship the bulk-action infrastructure with only safe currently backed actions enabled.

### 7. Performance and list scaling
Make the library feel scalable.

Requirements:
- server-driven paging
- no giant unbounded client-side dataset
- table remains responsive for larger document sets
- loading state preserves table rhythm
- search/filter interaction avoids obvious layout jank

Use virtualization only if appropriate and if it does not add unnecessary complexity. Cursor paging is the primary scalability contract.

### 8. Drawer/data integration
The drawer should not force duplicate data-fetch chaos.

Requirements:
- list summary and drawer detail use the canonical typed data layer
- row selection and drawer hydration are predictable
- opening and closing the drawer does not corrupt selection state
- back/forward or explicit route-driven row state is acceptable if appropriate
- keep the implementation consistent with the route and URL-state contracts already established

### 9. Audit alignment
Where the audit layer already exists, emit or reconcile:
- `DOCUMENT_LIBRARY_VIEWED`
- `DOCUMENT_DETAIL_VIEWED`
- `DOCUMENT_TIMELINE_VIEWED`

Do not create a second audit path.

### 10. Documentation
Document:
- document-library route ownership
- search/filter/sort URL-state rules
- drawer behavior
- selection and bulk-action rules
- which bulk actions are intentionally deferred until backed by safe server semantics

## Required deliverables

### Backend / contracts
- upgraded list endpoint
- typed filter/sort/paging contracts
- tests

### Web
- `/projects/:projectId/documents`
- filter bar
- search input
- server-sorted/paged table
- right details drawer
- multi-select and bulk-action rail
- empty/loading/error/no-results states

### Docs
- document-library UX and API contract doc
- filter/sort/search URL-state doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/api/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small table/drawer/filter refinements are needed
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- upload or extraction internals
- raw original delivery
- unrelated feature routes
- destructive bulk actions without safe backend support
- a second table or drawer system
- flashy file-manager aesthetics

## Testing and validation
Before finishing:
1. Verify pagination behavior.
2. Verify filtering behavior.
3. Verify sorting behavior.
4. Verify search/filter/sort combinations return expected slices.
5. Verify row selection opens the details drawer.
6. Verify `Open document` deep-links correctly.
7. Verify table row focus behavior is keyboard-safe.
8. Verify drawer focus trap and return focus behavior work.
9. Verify empty/loading/filtered/no-results states render correctly.
10. Verify docs match actual routes, params, and enabled bulk actions.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the document library is a real management surface, not a placeholder
- search, filters, sorting, and cursor paging are real
- the details drawer is real and useful
- selection and bulk-action infrastructure are real and restrained
- the library uses canonical table/filter/drawer primitives with bounded layout and keyboard-accessible interactions
- search/filter/sort/paging behavior is validated against the documented benchmark fixture set for this phase
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

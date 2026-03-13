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
   - `/phases/phase-01-ingest-document-viewer-v1.md` for the route map, breadcrumb hierarchy, App Router baseline, page query-parameter rules, and loading/error guidance
3. Then review the current repository generally — routes, layouts, loading/error boundaries, URL/search-param handling, shell integration, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second route hierarchy, duplicate layout tree, or conflicting URL-state model.

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
- `/phases` wins for route ownership, navigation model, breadcrumb semantics, adaptive shell behavior, deep-link expectations, and acceptance logic.
- Official docs win only for nested-layout mechanics, suspense/loading/error boundary mechanics, and implementation details of the current frontend stack.
- Keep the route contract browser-native and stable. Do not regress into route chaos or implicit client-only state.

## Objective
Lock the route-layout contract with nested layouts, deep links, URL state, suspense boundaries, and error boundaries.

This prompt owns:
- the canonical nested route-layout structure for the web app
- stable deep-link behavior
- URL-state rules and search-param discipline
- route-group organization
- loading, error, and not-found boundary patterns
- page-level and workspace-level suspense composition
- route helpers and path/query normalization where useful
- shell integration for current and near-term project routes

This prompt does not own:
- full data-fetching architecture beyond what is needed to make route contracts consistent
- feature-heavy document, preprocessing, layout, transcription, or privacy implementations
- a second state layer that hides essential route state outside the URL
- broad visual redesign beyond what is needed for consistency

## Phase alignment you must preserve
From Phase 1.0 route and information architecture baseline:

### Public/system route contract
- `/` redirects unauthenticated users to `/login` and authenticated users to `/projects`
- `/login`
- `/auth/callback`
- `/logout`
- `/health` is an optional safe diagnostic UI page backed by health data
- `/error` is a safe error UX route

### Authenticated route contract
- `/projects`
- `/admin`

### Project-scoped route contract
- `/projects/:projectId/overview`
- `/projects/:projectId/documents`
- `/projects/:projectId/documents/import`
- `/projects/:projectId/documents/:documentId`
- `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`
- `/projects/:projectId/jobs`
- `/projects/:projectId/activity`
- `/projects/:projectId/settings`

### Query-parameter rule
- browser `page` query parameters are human-facing 1-based page numbers
- persisted `page_index` values remain 0-based unless a field is explicitly named `page_index`

### Breadcrumb rule
Breadcrumbs provide orientation only.
Breadcrumbs are not an action menu.

### Composition rule
- use nested layouts for shell and project context
- loading boundaries prefer skeletons over spinner-only patterns
- route-level failures use safe error UX
- current and future workspaces must remain deep-linkable and restorable

## Implementation scope

### 1. Canonical route tree and nested layouts
Implement or refine the web route tree so it is explicit, stable, and future-proof.

Requirements:
- one consistent route-group structure
- one canonical authenticated shell path
- one canonical project-scoped layout path
- one canonical admin path
- nested layouts carry shell, project context, and page-header composition consistently
- current routes do not fracture into competing layout systems

- root/global layout
- public route group
- authenticated route group
- project-scoped layout
- admin route group/layout
- route-level loading and error boundaries where appropriate

### 2. Deep-link contract and path stability
Define and enforce deep-link behavior.

Requirements:
- current pages are directly addressable and reload-safe
- browser back/forward works predictably
- detail routes, viewer routes, and route transitions preserve context appropriately
- URLs are stable and meaningful
- no hidden state is required just to reopen a meaningful surface
- future document and viewer routes can plug into this contract

If route helpers or typed route builders simplify the contract, add them.
Do not overbuild a routing framework.

### 3. URL-state discipline
Implement a consistent URL-state model.

Requirements:
- query params are used only for state that should survive refresh/share/back-forward
- ephemeral local-only UI state is not indiscriminately dumped into the URL
- page number normalization follows the phase contract
- list/search/filter/sort/cursor states use predictable encoding
- detail/viewer state is canonical where it matters
- invalid or malformed params degrade safely and predictably

This contract must be documented, not merely implied.

### 4. Loading boundaries and suspense composition
Implement or refine loading composition across current route families.

Requirements:
- prefer skeletons over spinner-only patterns
- loading boundaries are placed where they preserve shell continuity and reduce jarring full-page resets
- route transitions feel calm and exact
- long-running feature routes can later plug into this pattern
- the shell stays mounted while child content suspends where appropriate

Do not wrap everything in one giant loading boundary.

### 5. Error and not-found boundaries
Implement or refine route-safe failure handling.

Requirements:
- safe route-level error boundaries
- project-scoped failures stay inside the product shell when appropriate
- auth failures and unauthorized states remain clear and serious
- not-found behavior is consistent
- `/error` exists or is reconciled if the current repo has an equivalent safe route
- no stack traces or unsafe internals leak into browser-facing error states

### 6. Breadcrumb and page-context consistency
Integrate the breadcrumb and page-context contract into the route structure.

Requirements:
- breadcrumbs derive from the route hierarchy
- breadcrumbs are orientation only
- project and document route ancestry is consistent
- no page invents a contradictory local navigation tree
- page headers and breadcrumbs do not compete visually

### 7. Current and near-term route reconciliation
Reconcile the existing app to the locked route contract.

At minimum ensure route consistency for:
- `/`
- `/login`
- `/projects`
- current admin routes
- `/projects/:projectId/overview`
- `/projects/:projectId/jobs`
- `/projects/:projectId/activity`
- `/projects/:projectId/settings`

Where appropriate, also scaffold or normalize the route contract for:
- `/projects/:projectId/documents`
- `/projects/:projectId/documents/import`
- `/projects/:projectId/documents/:documentId`
- `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`
- `/health`
- `/error`

Do not fake heavy feature content.
Do make the route ownership real and ready.

### 8. Documentation
Document:
- route hierarchy
- route-group ownership
- which state belongs in the URL
- how loading/error boundaries are placed
- page query normalization rules
- breadcrumb rules
- what later work must follow when adding routes

## Required deliverables

### Web
- nested route layouts
- project-scoped layout contract
- admin route-layout contract
- route-level loading boundaries
- route-level error boundaries
- not-found handling
- URL-state helpers / normalization utilities if useful
- breadcrumb/path-context wiring

### Docs
- route-layout and URL-state contract doc
- loading/error boundary placement doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/packages/ui/**` only if small breadcrumb/layout helpers are needed
- `/packages/contracts/**` only if small route/query enums or shared types help consistency
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- full feature pages for documents/import/viewer
- a giant client-side router abstraction
- hidden state machines that bypass the URL
- a second shell layout path
- feature-specific workflow logic for later phases
- flashy navigation tricks that weaken clarity

## Testing and validation
Before finishing:
1. Verify nested layouts render consistently across the current authenticated route family.
2. Verify deep links reload correctly.
3. Verify back/forward navigation remains consistent.
4. Verify malformed or missing query params degrade safely.
5. Verify the `page` query follows the human-facing 1-based rule.
6. Verify loading boundaries prefer skeletons and preserve shell continuity.
7. Verify route-level errors are safely contained and user-facing.
8. Verify breadcrumbs reflect the route contract without acting as action menus.
9. Verify docs match actual routes and URL-state behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the app has one locked route-layout contract
- nested layouts are real and consistent
- deep links are stable
- URL-state rules are explicit and implemented
- loading and error boundaries are consistent and safe
- breadcrumb behavior is consistent
- route-extension rules are documented with at least one concrete nested-route example
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

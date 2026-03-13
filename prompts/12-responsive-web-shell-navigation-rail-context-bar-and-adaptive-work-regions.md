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
3. Then review the current repository generally — layouts, routes, styles, shell code, auth/project/admin pages, tests, docs, and packages — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second shell, a second route-layout hierarchy, or parallel navigation systems.

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
- `/phases` wins for shell philosophy, route ownership, adaptive-state model, single-fold rule, keyboard/focus behavior, and UI acceptance logic.
- Official docs win only for browser layout mechanics, routing mechanics, and accessibility semantics.
- Preserve the browser-native translation of the Obsidian blueprint; do not drift back into desktop-first assumptions.

## Objective
Build the responsive web shell with navigation rail, context bar, page header, and adaptive work regions.

This prompt owns:
- the global authenticated shell
- project-scoped shell layout
- navigation rail and top/context chrome
- page-header contract
- adaptive state model (`Expanded | Balanced | Compact | Focus`)
- bounded work-region scrolling and single-fold behavior
- route-level shell integration for current authenticated/admin/project surfaces
- shell-level keyboard and reflow behavior
- deep-link-safe page composition

This prompt does not own:
- the full component primitive library
- global command bar / omnibox power features
- viewer-specific dense workspace implementation
- feature-specific workflows for ingest/preprocessing/layout/transcription/privacy
- route-contract fine tuning beyond what is necessary to make the shell real and consistent

## Phase alignment you must preserve
From the Obsidian Folio blueprint and Phase 1 route/layout baseline:

### Canonical shell
The shell must support:
- title bar with app identity, project context, deployment-environment signal, and project access-tier signal
- primary navigation rail
- main content host with page header + body regions
- optional contextual right region depending on workspace state

### Adaptive state model
All high-density workspaces inherit:
- `Expanded`: left rail + center work surface + right inspector visible
- `Balanced`: rail narrows, inspector compresses to summary
- `Compact`: inspector becomes drawer/flyout; rail becomes compact strip
- `Focus`: active work surface dominates; secondary panes become on-demand overlays

State transitions are driven by current app-window client area and task context.
They are never keyed only to device labels.

### Single-fold rule
- default behavior for supported window sizes keeps shell header + page header + workspace body within one client-area fold
- vertical page-level scrolling is avoided in default state
- dense content scrolls within bounded regions
- accessibility fallback allows controlled scrolling under zoom/reflow/text-spacing scenarios

### Current route ownership to preserve
The authenticated shell must fit and not break the existing authenticated route family, including:
- `/projects`
- `/admin`
- `/projects/:projectId/overview`
- `/projects/:projectId/jobs`
- `/projects/:projectId/activity`
- `/projects/:projectId/settings`

The root route `/` remains an entry resolver, and `/health` remains a diagnostic route rather than a primary authenticated workspace surface.

And it must remain compatible with the broader Phase 1 path:
- `/projects/:projectId/documents`
- `/projects/:projectId/documents/import`
- `/projects/:projectId/documents/:documentId`
- `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`

### Header/page-header behavior
- one clear page title
- one primary action per surface
- secondary/destructive actions move to labeled overflow
- no CTA stuffing in the global header
- keyboard and focus behavior remain predictable

## Implementation scope

### 1. Global authenticated shell
Implement or refine the global authenticated shell so it becomes the real product frame, not a placeholder.

Requirements:
- app identity placement
- environment signal
- user/menu area
- project-context region
- left nav rail
- main content host
- page-header slot
- optional right/context region slot
- dark, restrained, serious visual tone
- no fake desktop chrome
- no splash-page feel
- no “AI assistant” visual tropes

Use the design system from `/packages/ui` as the canonical styling source.

### 2. Adaptive-state engine
Implement a real, testable shell state model for:
- `Expanded`
- `Balanced`
- `Compact`
- `Focus`

Requirements:
- explicit state logic, not vague responsive CSS guesswork
- current state is inferable/testable
- state transitions are based on app-window/client area and task context
- the shell does not collapse into chaos at intermediate widths
- bounded fallback behavior under zoom/reflow remains safe

Use the least disruptive correct implementation for the current stack:
- CSS/container-query-first where possible
- minimal JS where genuinely needed
- no device-class branching

### 3. Navigation rail and route-group integration
Implement or refine the primary navigation rail and project-scoped navigation structure.

Requirements:
- link-only primary nav
- shallow, permission-aware navigation
- current-route highlighting
- stable route ownership
- project switcher placement that feels like an internal tool, not a consumer dropdown
- environment badge and access-tier badge visible and useful
- settings visibility remains permission-based
- navigation does not tease inaccessible surfaces unnecessarily

Do not turn this into a mega-sidebar.
Keep it calm and sharply prioritized.

### 4. Page-header contract
Implement a reusable page-header region that supports:
- page title
- subtitle/status/meta slot where useful
- one primary action slot
- secondary actions / overflow slot
- breadcrumb or context support only if it fits the current route structure cleanly

Requirements:
- consistent spacing and hierarchy
- no noisy per-page custom chrome
- predictable keyboard order
- stable header/body relationship across routes

### 5. Bounded work regions and scrolling model
Implement the shell's scrolling philosophy properly.

Requirements:
- app window and shell occupy the viewport with `100dvh`-style logic or equivalent browser-safe fallback
- page-level vertical sprawl is avoided by default
- tables/lists/detail panes/side inspectors scroll inside bounded regions where appropriate
- sticky shell chrome does not hide focused elements
- reflow/zoom fallback remains accessible

This is critical. Do not allow the shell to degrade into endless full-page scroll just because it is easier.

### 6. Integrate current authenticated surfaces
Move the existing authenticated routes into the consistent shell.

At minimum reconcile:
- `/projects`
- `/projects/:projectId/overview`
- `/projects/:projectId/jobs`
- `/projects/:projectId/activity`
- `/projects/:projectId/settings`
- current admin surfaces such as audit, operations, security, and design-system routes if they already exist

Requirements:
- consistent shell structure
- consistent page-header usage
- current pages feel like one product, not stitched demos
- empty states remain calm and useful
- loading/error boundaries fit the shell cleanly

Do not build the full document viewer or later workspaces here.
Do make the shell ready for them.

### 7. Focus, keyboard, and accessibility behavior
Implement shell-level accessibility behavior rigorously.

Requirements:
- strong visible focus
- skip/link or equivalent fast path if useful
- keyboard-safe rail navigation
- keyboard-safe project switching path
- no focus traps
- focus remains visible during route transitions, overflow, and bounded-scroll cases
- shell works in dark, light, and high-contrast modes

### 8. Docs and diagnostics
Document:
- shell layout contract
- adaptive-state rules
- scroll-region rules
- page-header contract
- how future pages should plug into the shell
- what not to do in feature routes

If appropriate, expose a small internal diagnostic on the design-system route or shell dev tools showing the current adaptive state.

## Required deliverables

### Web shell / routes
- authenticated root shell layout
- project-scoped layout
- admin shell integration
- nav rail
- page-header primitive/slot pattern
- adaptive-state plumbing
- bounded-region layout primitives or shell wrappers

### Shared UI
- any additional shell primitives needed in `/packages/ui` for the frame, regions, or scroll containers

### Docs
- shell contract / adaptive-layout doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/packages/ui/**`
- `/packages/contracts/**` only if small route/shell enums or shared types help coherence
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- global omnibox / command palette
- the full dialog/drawer/menu/table primitive suite
- feature-specific ingest/document/viewer workflows
- viewer-specific multi-pane operational layouts
- a consumer-style landing page shell
- a noisy admin-console aesthetic
- a second shell path beside the canonical authenticated shell

## Testing and validation
Before finishing:
1. Verify the authenticated shell renders consistently across the current authenticated route family.
2. Verify the nav rail and page header behave consistently.
3. Verify adaptive states are real and testable.
4. Verify bounded work-region scrolling works and page-level scroll sprawl is reduced.
5. Verify focus remains visible and keyboard navigation works across shell chrome.
6. Verify dark/light/high-contrast behavior is not broken.
7. Verify key current routes do not regress functionally while being integrated into the shell.
8. Verify docs match the actual shell contract and route structure.
9. Confirm `/phases/**` is untouched.

Include browser-level checks where practical for:
- reflow / zoom safety
- keyboard-only shell traversal
- current-route highlighting
- shell behavior at multiple window sizes

## Acceptance criteria
This prompt is complete only if all are true:
- the app has one consistent authenticated shell
- the nav rail is real and usable
- the page-header contract is real and reusable
- adaptive shell states are implemented and testable
- bounded work-region behavior is real
- current authenticated/admin/project routes feel unified
- shell navigation, header, and work-region behavior are consistent across authenticated, admin, and project routes
- route transitions keep nav rail and page header mounted while only the work region content changes
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

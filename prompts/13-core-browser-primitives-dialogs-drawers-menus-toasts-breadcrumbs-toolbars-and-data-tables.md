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
   - `/phases/phase-01-ingest-document-viewer-v1.md` for the Phase 1.0 component inventory, route/layout baseline, and keyboard/focus quality gates
3. Then review the current repository generally — code, components, packages, styles, routes, tests, docs, and existing primitives — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second primitive library, duplicate overlay system, or conflicting interaction model.

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
- `/phases` wins for command hierarchy, shell behavior, focus rules, adaptive-state expectations, component inventory, and acceptance logic.
- Official docs win only for browser accessibility semantics, overlay mechanics, keyboard interaction patterns, and implementation details of the current frontend stack.
- Preserve the browser-native Obsidian contract. Do not drift into consumer-app, desktop-chrome, or flashy dashboard behavior.

## Objective
Create the core browser primitives: dialogs, drawers, menus, toasts, breadcrumbs, toolbars, and data tables.

This prompt owns:
- the canonical reusable primitive layer in `/packages/ui`
- overlay mechanics and focus return behavior
- table + details-drawer composition
- toolbar and command-overflow behavior
- feedback primitives such as toast and inline/banner alerts
- breadcrumbs and status chips
- integration of these primitives into the current shell and internal gallery
- primitive-level accessibility and interaction tests

This prompt does not own:
- the full feature-specific component library
- full form systems
- full viewer-specific dense workspace tools
- feature implementations for ingest, preprocessing, layout, transcription, or privacy
- a second ad hoc primitive set inside feature routes

## Phase alignment you must preserve
From the Obsidian blueprint and Phase 1.0 component inventory:

### Command hierarchy
The interaction stack remains:
- shell navigation
- page header primary action
- contextual command bar / toolbar
- labeled overflow / flyout
- item context menu

Every contextual command must also be reachable without relying on right-click context menus.

### Required component inventory foundation
The web primitive layer must support and/or reconcile:
- `Breadcrumbs`
- `PageHeader`
- `DataTable`
- `DetailsDrawer`
- `StatusChip`
- `Toast`
- `InlineAlert` / `Banner`
- `ModalDialog`
- `Toolbar`
- `CommandBarOverflow`
- any minimal supporting overlay/focus primitives required to make those real

### Interaction rules
- keyboard-first operation is required
- toolbar is a single tab stop with roving focus
- escape behavior is predictable
- no keyboard traps
- sticky headers, drawers, and flyouts must not obscure the active focus target
- details belong in drawers or secondary routes, not in noisy inline expansion stacks
- tables are for data display, not page layout

### Visual and UX tone
- sleek dark tone
- minimal, serious, calm surfaces
- strong hierarchy and visible focus
- restrained overlays, not giant floating glass toys
- no AI-assistant aesthetic
- no marketing-style empty gloss

## Implementation scope

### 1. Canonical primitive ownership in `/packages/ui`
Build or refine the primitive layer so `/packages/ui` is the canonical source for the browser primitives introduced here.

At minimum create or reconcile consistent primitives for:
- dialog
- drawer / side panel
- menu / flyout / overflow surface
- toast / transient notification
- inline alert / banner
- breadcrumbs
- toolbar
- data table
- details drawer pattern
- status chip / status pill

Use the least disruptive structure the repository already supports, but do not scatter new primitives ad hoc across `/web`.

### 2. Overlay and layer-management foundation
Implement a real shared overlay system.

Requirements:
- predictable layering and stacking order
- focus trap where appropriate
- focus return on close
- escape key handling
- outside-click behavior only where appropriate
- portal/root management if needed
- scroll locking only when needed and without breaking accessibility
- reduced-motion-safe open/close behavior
- dark/light/high-contrast-safe rendering

Do not let every route invent its own modal, drawer, or flyout logic.

### 3. Dialog primitive
Implement or refine a reusable dialog primitive.

Requirements:
- accessible title/description semantics
- focus trap
- initial focus behavior
- return focus on close
- predictable escape behavior
- safe destructive-action confirmation affordances
- no giant wizard framework here; just a clean, reusable modal baseline

Use it for at least one real route interaction if the repo already has a fitting use case.

### 4. Drawer primitive and details-drawer composition
Implement or refine a reusable drawer primitive and a details-drawer composition pattern.

Requirements:
- right-side by default unless the repo has a stronger existing convention
- keyboard-safe close and focus return
- bounded internal scrolling
- does not increase total page height in default shell use
- suitable for list/detail workflows
- compact/focus-state aware behavior

Use it to support at least one real details pattern in the current repo where it simplifies the implementation.

### 5. Menu / overflow / flyout primitives
Implement labeled overflow and flyout/menu primitives for low-frequency actions.

Requirements:
- every action reachable by keyboard
- no unlabeled mystery meat icon menus
- focus handling is correct
- placement is stable
- command labels are clear
- contextual actions still have at least one non-context-menu path
- no giant nested action labyrinths

### 6. Toolbar primitive
Implement a real toolbar primitive that follows the required keyboard model.

Requirements:
- single tab stop
- roving focus for arrow-key navigation
- predictable home/end behavior if appropriate
- stable disabled/pressed/selected states
- command overflow integration for lower-frequency actions
- compatible with dense work surfaces and page-header command regions

Demonstrate it in the design-system gallery and at least one real app surface if the current repo has a fitting location.

### 7. DataTable primitive
Implement or refine a reusable data table baseline.

Requirements:
- semantic table-first approach unless interaction complexity truly requires richer semantics
- sorting support
- pagination or bounded loading support
- row selection
- current-row highlight/focus visibility
- optional actions column or row-level action affordance
- stable empty/loading/error hooks
- keyboard-safe row interaction
- no misuse of the table as a layout grid

This table baseline must be fit for later document library and jobs surfaces without pretending those features are complete here.

### 8. Breadcrumbs, status chips, alerts, and toasts
Implement the remaining primitive foundation:

#### Breadcrumbs
- orientation only
- not an action menu
- compatible with project/document/viewer route hierarchies

#### Status chips
- environment, access tier, and status-safe visual language
- clear semantics
- not overly loud

#### Inline alerts / banners
- actionable, calm, and exact
- used for route-level or section-level feedback
- not toast spam

#### Toasts
- restrained transient feedback
- accessible announcement behavior
- suitable for low-risk confirmations only
- do not replace important inline or page-level state explanation

### 9. Internal gallery integration
Upgrade `/admin/design-system` so the primitive system is demonstrated there as a real engineering surface.

The gallery must visibly and accurately cover:
- dialogs
- drawers
- menus / overflow
- breadcrumbs
- toolbars
- tables
- status chips
- alerts
- toasts
- focus behavior
- dark/light/high-contrast behavior

The gallery must use the real shared primitives, not fake examples disconnected from app usage.

### 10. Migration of current app surfaces
Where appropriate, replace ad hoc shell/admin/auth/project primitives with the shared versions introduced here.

Requirements:
- reduce duplication
- keep the repo easier to extend
- do not rewrite unrelated feature screens just for style purity
- do make the current shell and admin surfaces more consistent

### 11. Documentation and guardrails
Document:
- which primitives are canonical
- what belongs in `/packages/ui`
- how overlay/focus behavior works
- how tables, drawers, toolbars, and toasts should be used
- what feature routes must not implement ad hoc anymore

## Required deliverables

### Shared UI
- canonical dialog primitive
- canonical drawer primitive
- canonical menu / overflow primitive
- canonical toast + inline alert primitives
- canonical breadcrumbs primitive
- canonical toolbar primitive
- canonical data-table baseline
- canonical status-chip primitive
- any small support utilities required for focus/layer management

### Web
- `/admin/design-system` updated to demonstrate the real primitives
- least-disruptive migration of at least the current shell/admin/project surfaces that clearly benefit

### Docs
- primitive library / interaction contract doc
- overlay and focus-management doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/packages/ui/**`
- `/web/**`
- `/packages/contracts/**` only if small shared enums/types help status and table consistency
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- the complete advanced component library
- huge form-builder systems
- feature-specific ingest, preprocessing, layout, transcription, privacy, or export workflows
- a public Storybook replacing the internal route
- flashy transition systems
- a second primitive set hidden inside feature folders

## Testing and validation
Before finishing:
1. Verify dialog focus trap and focus return.
2. Verify drawer keyboard behavior and focus return.
3. Verify toolbar roving-focus behavior.
4. Verify menus/overflow are keyboard-reachable and labeled.
5. Verify toast announcement behavior is accessible and restrained.
6. Verify the table baseline supports sorting, selection, and safe empty/loading/error hooks.
7. Verify dark/light/high-contrast behavior is not broken.
8. Verify `/admin/design-system` is using the real primitives.
9. Verify at least one current app surface now consumes the shared primitives without regression.
10. Verify docs match actual primitive ownership and usage.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- one canonical primitive layer exists
- dialogs, drawers, menus, toasts, breadcrumbs, toolbars, and tables are real and reusable
- overlays trap focus on open, restore focus on close, and honor keyboard dismissal rules
- the internal gallery proves the primitives are real
- current app surfaces are more consistent, not less
- current app surfaces consume canonical primitives without route-specific duplicate primitive implementations
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

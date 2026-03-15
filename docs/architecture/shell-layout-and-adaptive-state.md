# Shell Layout And Adaptive State (Phase 0.2 / Prompt 12)

This document defines the canonical authenticated shell contract for current web routes.

## Scope

The canonical authenticated shell is implemented in:

- `web/app/(authenticated)/layout.tsx`
- `web/components/authenticated-shell.tsx`
- `web/components/page-header.tsx`
- `web/app/globals.css`

Project-scoped shell composition is implemented in:

- `web/app/(authenticated)/projects/[projectId]/layout.tsx`
- `web/components/project-section-header.tsx`

## Canonical Shell Structure

The authenticated shell has one shared frame for all authenticated routes:

1. Shell header (identity, project switcher, environment and tier badges, theme control, user menu).
2. Primary navigation rail (link-only, shallow route ownership).
3. Context navigation bar for project routes.
4. Bounded work region where route content renders.
5. Optional contextual right region for adaptive-state diagnostics in larger states.

No route should render a second global workspace header.

## Adaptive State Model

Shared state resolution is implemented in `@ukde/contracts` via:

- `resolveAdaptiveShellState(...)`
- `ResolveAdaptiveShellStateInput`
- `ShellTaskContext` (`standard | dense`)

Supported states:

- `Expanded`
- `Balanced`
- `Compact`
- `Focus`

Current default width breakpoints:

- `Expanded`: `>= 1360`
- `Balanced`: `>= 1080`
- `Compact`: `>= 820`
- `Focus`: `< 820`

Additional adaptive rules:

- `forceFocus` always returns `Focus`.
- Reduced viewport height steps state down to preserve single-fold behavior.
- Dense contexts (for example viewer paths) bias toward `Focus` at narrower widths.

State is reflected on the shell root as `data-shell-state` for deterministic styling and diagnostics.

## Navigation Contract

Primary rail rules:

- link-only
- shallow
- current-route highlighting with `aria-current="page"`
- admin entry visible only for users with platform roles

Context bar rules:

- project context links are permission-aware
- settings link appears only when settings access is allowed
- focus state uses an on-demand drawer (`details`) for context links

Admin route note:

- `/admin/**` route navigation is owned by `web/app/(authenticated)/admin/layout.tsx` through the admin console shell, not by the shared authenticated context bar.

## Page-Header Contract

Feature routes should use the shared `PageHeader` primitive for top-of-page chrome.

Supported slots:

- `eyebrow`
- `title`
- `summary`
- `meta`
- `primaryAction`
- `secondaryActions`
- `overflowActions`

Rules:

- one clear page title
- no CTA stuffing in shell header
- route-specific actions belong in page header, not shell header

## Scroll And Single-Fold Behavior

The shell targets one client-area fold by default:

- shell root uses viewport-tied height (`100dvh`-style behavior)
- shell chrome remains outside route-content scroll
- route content scrolls in `.authenticatedShellWorkRegion`
- context region and rail have independent bounded scroll

Fallback behavior:

- narrow-width and low-height conditions relax layout while preserving keyboard reachability and visible focus.

## Layout Stability Baseline (90% Type Scale)

The UI uses a reduced base type scale (`90%`) while keeping shell geometry stable.

Stability contract:

- keep shell header actions on a single row in desktop states to avoid route-to-route vertical jump
- truncate long shell titles/subtitles with ellipsis instead of allowing header-height expansion
- keep page-header actions in one row on desktop; allow wrap only at narrow mobile breakpoints
- reserve stable width for shell status chips and top-bar controls so changing labels do not shift neighboring controls
- switch to stacked header layout earlier on medium widths to avoid overflow-driven reflow
- keep shell/workspace max widths in font-independent units so reducing base typography scale does not introduce side gutters

Verification baseline:

- browser reflow tests in `web/tests/browser/shell-regression.spec.ts`
- test case: `header chrome remains stable across authenticated route transitions @reflow`
- existing single-fold checks remain required for viewport-bounded shell behavior

## Accessibility And Keyboard Behavior

- skip link: `Skip to work region`
- visible focus is preserved through shell chrome, context links, and bounded-scroll regions
- navigation and context bars are keyboard reachable without focus traps
- shell remains functional in dark/light and forced-colors/high-contrast modes

## Route Integration Baseline

The unified shell currently covers:

- `/projects`
- `/activity`
- `/admin/**`
- `/projects/:projectId/{overview,documents,jobs,activity,settings,export-*}`
- `/projects/:projectId/documents/import`
- `/projects/:projectId/documents/:documentId`
- `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`

Project routes receive a shared project header and context bar through nested layout ownership.

## Guardrails For Future Routes

Do:

- render feature content inside the work region
- use `PageHeader` for route title and actions
- keep dense tables and panes inside bounded containers

Do not:

- add a second global header in feature pages
- add route-local sidebars that duplicate shell navigation ownership
- rely on full-page vertical sprawl when bounded scrolling is appropriate

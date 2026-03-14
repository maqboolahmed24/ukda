# Project Switcher Behavior Contract

> Status: Active baseline (Prompt 17)
> Scope: shell header project-switch control, command integration, and route preservation

This contract defines how project switching works in the authenticated shell.

## Shell placement and ownership

The project switcher is a first-class global header control in:

- `web/components/authenticated-shell.tsx`
- `web/components/global-command-bar.tsx`

It is implemented through the same command system, not a separate route-level switcher.

## Data source and eligibility

- Source list: authenticated user's project memberships already loaded for shell context.
- Switch targets include only projects the current user can access.
- Project metadata shown in switch commands includes tier and role context.

No cross-project or non-member project leakage is allowed.

## Route preservation rules

When switching projects from an existing project route:

- preserve nearest matching section when safe:
  - `overview`
  - `documents`
  - `documents/import`
  - `jobs`
  - `activity`
  - `settings` (only when target allows settings)
  - export review sections (`export-candidates`, `export-requests`, `export-review`)
- fall back to `overview` when the target project cannot support the current section (for example settings access denied)

When outside project scope, switch target defaults to project overview.

Canonical resolver:

- `resolveProjectSwitchHref(...)` in `web/lib/command-registry.ts`

## Interaction contract

- Header button opens switcher-focused command mode.
- Filter supports project name, role, and tier keywords.
- Keyboard-safe open, traversal, select, and escape behavior follow the global command-bar model.
- Selecting a project executes deterministic navigation to the resolved target route.

## Regression coverage

- `web/lib/command-registry.test.ts` (route preservation and fallback)
- `web/components/global-command-bar.test.tsx` (switch mode + execution)

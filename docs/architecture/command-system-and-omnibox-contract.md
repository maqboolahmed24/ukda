# Command System and Omnibox Contract

> Status: Active baseline (Prompt 17)
> Scope: global command bar, typed command registration, role/route filtering, and keyboard behavior

This contract defines the canonical command system for authenticated routes.

## Ownership

Canonical implementation lives in:

- `web/components/global-command-bar.tsx`
- `web/lib/command-registry.ts`
- `web/lib/command-events.ts`

Shell integration lives in:

- `web/components/authenticated-shell.tsx`

No route should create a second global command palette.

## Command hierarchy alignment

The command bar sits under the shell in the product command hierarchy:

`shell navigation -> page header primary action -> contextual command bar -> overflow/flyout -> item context menu`

The global command bar must not replace page-local workflow command surfaces.

## Registration model

Commands are registered through typed definitions with:

- stable `id`
- `label`
- `keywords`
- `group`
- `scope`
- route target `href`

Scope values:

- `global`
- `authenticated`
- `project`
- `admin`
- `workspace`

Groups are used for dense, predictable result sections in the command bar.

## Filtering and visibility

Role and route context are applied before filtering:

- admin commands require platform-role eligibility
- project workspace commands require current project context and membership
- settings commands require `canAccessSettings`
- project-switch commands are generated only from the caller's accessible projects

Unauthorized routes are hidden, not teased.

## Interaction contract

- Entry points:
  - keyboard shortcut `Meta+K` (macOS) and `Ctrl+K` fallback
  - header trigger button
- Overlay behavior:
  - opens in a modal command surface
  - type-to-filter
  - grouped results
  - loading and no-result states
- Keyboard model:
  - input accepts query
  - `ArrowDown/ArrowUp/Home/End` navigates options
  - `Enter` executes selected command
  - `Escape` closes and returns focus safely

## Diagnostics and extension rules

- `/admin/design-system` must expose real command-bar diagnostics.
- Later work may add commands through the shared registry only.
- Later work must not hardcode ad hoc global command lists in feature routes.

## Regression coverage

Primary tests:

- `web/components/global-command-bar.test.tsx`
- `web/lib/command-registry.test.ts`
- `web/components/authenticated-shell.a11y.test.tsx`

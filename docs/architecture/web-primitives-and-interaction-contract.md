# Web Primitives and Interaction Contract (Phase 0.2 / Prompt 13)

This document defines the canonical browser primitive layer for UKDE.

## Canonical Ownership

All reusable primitives owned by this contract live in `/packages/ui`:

- [packages/ui/src/primitives.tsx](/Users/test/Code/UKDA/packages/ui/src/primitives.tsx)
- [packages/ui/src/primitives-logic.ts](/Users/test/Code/UKDA/packages/ui/src/primitives-logic.ts)
- [packages/ui/src/styles.css](/Users/test/Code/UKDA/packages/ui/src/styles.css)

Import path:

- `@ukde/ui/primitives`

Supporting interaction logic tests:

- [packages/ui/src/primitives-logic.test.ts](/Users/test/Code/UKDA/packages/ui/src/primitives-logic.test.ts)

## Primitive Inventory

The canonical primitive set now includes:

- `ModalDialog`
- `Drawer`
- `DetailsDrawer`
- `MenuFlyout`
- `CommandBarOverflow`
- `ToastProvider` + `useToast`
- `InlineAlert`
- `BannerAlert`
- `Breadcrumbs`
- `Toolbar` (single tab stop, roving focus)
- `DataTable` (sorting, paging, row selection, actions slot)
- `StatusChip`
- `FeedbackState` + `PageState` + `SectionState` + `InlineState`
- `SkeletonLines`

## Command Hierarchy

Product command priority remains:

1. Shell navigation
2. Page-header primary action
3. Toolbar/context commands
4. Labeled overflow/menu actions
5. Item-level contextual actions

Low-frequency and destructive actions should move to labeled overflow surfaces instead of crowding default command bars.

## Composition Rules

### Dialog and drawer

- Use `ModalDialog` for blocking confirmations.
- Use `Drawer` or `DetailsDrawer` for list/detail context and secondary metadata.
- Do not implement route-local modal/drawer stacks with custom focus and escape behavior.

### Menus and overflow

- Use `MenuFlyout` or `CommandBarOverflow` for lower-frequency actions.
- Menus must remain keyboard reachable and labeled.
- Commands available through context menus must also have a non-context-menu path.

### Toolbars

- Use `Toolbar` for dense command strips.
- Toolbar implements roving focus and arrow-key navigation.
- Overflow actions should use `overflowActions` on `Toolbar`.

### Data tables

- Use `DataTable` for tabular data, not layout.
- Keep selection and detail inspection in a `DetailsDrawer` where needed.
- Prefer bounded pagination over page-height sprawl.

### Feedback

- Use `InlineAlert` or `BannerAlert` for durable route-level feedback.
- Use toasts only for low-risk confirmations.
- Use `StatusChip` for concise environment/access/status signals.
- Use shared state primitives (`PageState`, `SectionState`, `InlineState`) for
  zero/empty/loading/error/success/degraded/disabled/not-found/unauthorized
  handling.
- Keep feedback priority aligned with
  [`state-feedback-language-and-priority.md`](./state-feedback-language-and-priority.md).
- Apply copy rules from
  [`state-copy-guidelines.md`](./state-copy-guidelines.md).

## Current Route Adoption

Shared primitives are actively consumed in:

- `/admin/design-system` (live primitive demos)
- `/admin/audit` (`DataTable` + `DetailsDrawer`)
- project section chrome (`Breadcrumbs` in project page header)
- authenticated shell badges (`StatusChip`)
- page-header overflow actions (`CommandBarOverflow`)

## Guardrails

Feature routes should not:

- introduce ad hoc dialog, drawer, or flyout implementations
- implement independent roving-focus logic for command bars
- build route-local table primitives with incompatible behavior
- replace inline error/status states with toast-only feedback

All new primitive changes must first be validated on `/admin/design-system`.

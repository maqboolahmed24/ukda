# Shell Accessibility and Keyboard Contract

> Status: Active baseline (Prompts 16 and 20)
> Scope: keyboard-first behavior, focus rules, and overlay interaction across shell routes

This contract defines the canonical accessibility posture for the authenticated shell and shared primitives.

## Keyboard-first baseline

- Every core path is reachable without pointer input.
- `Tab` order remains logical: skip link -> shell header -> nav/context -> work region.
- No keyboard traps in dialogs, drawers, menus, toolbars, or shell sections.
- `Escape` closes active overlays and expandable shell menus predictably.

## Focus rules

- Focus indicators must remain visible in dark, light, and forced-colors modes.
- Focus should not be obscured by sticky shell chrome.
- Route transitions may intentionally move focus to the work region when navigation is initiated from shell chrome.
- Dialogs/drawers/flyouts must restore focus to the trigger or previous focus target on close.

## Overlay and toolbar rules

- Shared primitives own overlay behavior:
  - `ModalDialog`
  - `Drawer` / `DetailsDrawer`
  - `MenuFlyout` / `CommandBarOverflow`
- Toolbar follows roving-focus arrow-key behavior (`ArrowLeft`, `ArrowRight`, `Home`, `End`).
- Flyouts expose `role="menu"` and keyboard navigation (`ArrowUp`, `ArrowDown`, `Home`, `End`, `Escape`).

## Preference-aware behavior

- Reduced motion disables non-essential motion effects.
- Reduced transparency disables non-essential blur/translucency.
- Forced-colors mode keeps controls, status chips, and selected states distinguishable.

## Diagnostics route

- `/admin/design-system` is the internal verification surface for:
  - focus visibility
  - keyboard traversal
  - overlay behavior
  - reduced motion/transparency
  - forced-colors safety

## Regression coverage

Core keyboard and focus interactions are tested in:

- `packages/ui/src/primitives-logic.test.ts`
- `packages/ui/src/primitives.a11y.test.tsx`
- `web/components/authenticated-shell.a11y.test.tsx`
- `web/components/route-states.a11y.test.tsx`
- `web/tests/browser/shell-regression.spec.ts`
- `web/tests/browser/primitives-interaction.spec.ts`

The browser suite is the canonical gate for shell and primitive keyboard/focus behavior, accessibility scans, and forced-colors/reduced-motion checks.

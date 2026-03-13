# Overlay and Focus Management Contract (Phase 0.2 / Prompt 13)

This document defines shared overlay behavior for modal, drawer, and flyout primitives.

## Canonical Implementation

Overlay and focus behavior is centralized in:

- [packages/ui/src/primitives.tsx](/Users/test/Code/UKDA/packages/ui/src/primitives.tsx)
  - shared layer stack
  - focus trapping
  - escape dismissal
  - outside-click handling
  - focus return
  - scroll-lock policy

No route should implement its own incompatible focus-trap or overlay-dismiss logic.

## Layering and Stacking

- Overlays are registered in a shared layer stack.
- Keyboard dismissal and outside-click dismissal are handled only by the topmost layer.
- Overlay rendering uses one portal root (`#ukde-overlay-root`) attached to `document.body`.

## Focus Lifecycle

On open:

- Store the previously focused element.
- Move focus to the first focusable control in the overlay, or overlay container fallback.

While open:

- `Tab` and `Shift+Tab` are trapped in modal and drawer surfaces.
- `Escape` closes the active overlay.
- Focus remains visible and keyboard reachable.

On close:

- Restore focus to explicit return target if provided.
- Otherwise restore to previously focused trigger when still connected.

## Dismissal Rules

- Dialogs and drawers use escape dismissal by default.
- Outside-click dismissal is enabled for modal/drawer/flyout surfaces unless explicitly overridden.
- Scroll-lock is enabled only for modal blocking overlays and uses a shared lock counter to avoid unlock races.

## Accessibility Semantics

- Dialog and drawer overlays render `role="dialog"` with `aria-modal="true"`.
- Dialog and drawer titles are wired via `aria-labelledby`.
- Optional descriptions are wired via `aria-describedby`.
- Toast viewport uses `aria-live="polite"` for non-blocking confirmations.

## Browser Preference Safety

Overlay visuals inherit shared token and preference behavior from `/packages/ui/src/styles.css`, including:

- dark/light mode support
- forced-colors and high-contrast compatibility
- reduced-motion and reduced-transparency-safe transitions/materials

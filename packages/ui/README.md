# @ukde/ui Design-System Contract

`/packages/ui` is the canonical visual system source for UKDE web surfaces.

## What This Package Owns

- semantic theme tokens (color, surfaces, borders, focus, status signals)
- typography, spacing, radius, elevation, and motion scales
- dark/light mode contracts with dark default
- browser preference-aware theme runtime (`prefers-color-scheme`, contrast, forced-colors, reduced-motion, reduced-transparency)
- canonical browser primitives for overlays, navigation context, tabular data, and feedback:
  - `ModalDialog`
  - `Drawer` and `DetailsDrawer`
  - `MenuFlyout` and `CommandBarOverflow`
  - `Toolbar` with roving focus behavior
  - `DataTable`
  - `Breadcrumbs`
  - `InlineAlert` and `BannerAlert`
  - `ToastProvider` / `useToast`
  - `StatusChip`
- foundational CSS primitives for buttons, fields, badges, surfaces, layout, focus visibility, and overlay treatment

## Module Map

- `src/tokens.ts`
  - typed token families
  - dark and light semantic color sets
  - CSS variable maps used by the shared stylesheet
- `src/theme.ts`
  - theme preference persistence helpers
  - runtime media preference readers
  - DOM synchronization helpers and media-subscription utilities
- `src/styles.css`
  - token-backed CSS custom properties
  - theme and accessibility preference behavior
  - low-level shared primitives consumed by `/web`
- `src/primitives.tsx`
  - canonical interactive browser primitives and overlay/focus lifecycle behavior
- `src/primitives-logic.ts`
  - deterministic pure interaction helpers (toolbar roving, stable sort, paging)

## Usage Rules

1. Import `@ukde/ui/styles.css` once at app root.
2. Use semantic classes and variables from this package instead of route-local color literals.
3. Add token changes in `src/tokens.ts` first, then wire CSS variables in `src/styles.css`.
4. Import browser primitives from `@ukde/ui/primitives` rather than implementing route-local alternatives.
5. Validate new primitives on `/admin/design-system` before broad route adoption.
6. Keep route CSS focused on composition and layout, not new token islands.

## Guardrail

Repository lint includes `scripts/check-design-token-literals.mjs`, which flags raw hex/rgb/hsl literals in core web shell paths. Add new visual values as shared tokens instead of hardcoding route-local colors.

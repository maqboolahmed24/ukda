# Theming and Preference Behavior

## Theme Strategy

- Dark mode is the default product theme.
- Light mode is fully supported.
- System preference mode remains available and follows browser settings.

Theme logic is implemented in `/packages/ui/src/theme.ts`.

## Persistence Model

- Preference key: `ukde.theme.preference`
- Stored values: `system | dark | light`
- Runtime sync writes mode and accessibility preference state onto document dataset attributes:
  - `data-theme`
  - `data-theme-preference`
  - `data-theme-contrast`
  - `data-theme-motion`
  - `data-theme-transparency`
  - `data-theme-forced-colors`

## Browser Preference Inputs

The runtime uses these media features:

- `prefers-color-scheme`
- `prefers-contrast`
- `forced-colors`
- `prefers-reduced-motion`
- `prefers-reduced-transparency` (with unsupported fallback)

## Web Integration

- `web/components/theme-runtime-sync.tsx` keeps root document attributes synchronized with stored preference and media changes.
- `web/components/theme-preference-control.tsx` is the shared preference selector used on login and workspace shell surfaces.
- `/admin/design-system` exposes live runtime diagnostics for verification.

## Reduced Motion and Transparency

- Transition duration tokens collapse to `0ms` when reduced motion is requested.
- Blur/translucent surface treatment is disabled when reduced transparency is requested or when forced-colors is active.

## High Contrast and Forced Colors

- Token variables are remapped to system colors under forced-colors mode.
- Focus indicators remain visible via explicit outline rules.
- Border and text tokens avoid low-contrast blending in high-contrast scenarios.

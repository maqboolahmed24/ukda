# Motion, Transparency, and Contrast Behavior

> Status: Active baseline (Prompt 16)
> Scope: runtime preference behavior for motion/transparency/contrast and forced-colors safety

This document describes how the shared UI layer reacts to browser accessibility preferences.

## Inputs

Runtime preference state is derived from:

- `prefers-reduced-motion`
- `prefers-reduced-transparency` (with unsupported fallback)
- `prefers-contrast`
- `forced-colors`

Theme runtime sync writes state onto `document.documentElement` dataset attributes:

- `data-theme-motion`
- `data-theme-transparency`
- `data-theme-contrast`
- `data-theme-forced-colors`

## Reduced motion

- Transition tokens collapse to zero-duration behavior.
- Skeleton shimmer animation is disabled.
- Interaction remains functionally equivalent with less visual movement.

## Reduced transparency

- Shared surfaces remove non-essential blur/translucency.
- Overlay and panel surfaces remain readable without glass effects.

## High contrast and forced colors

- Token values map to system colors.
- Focus ring stays visible.
- Selected controls and status chips remain distinguishable with border/selection cues.
- Critical interactive controls keep operable borders and text contrast.

## Verification

Use `/admin/design-system` diagnostics sections to verify active runtime posture and interaction safety across:

- keyboard traversal
- focus visibility
- reduced motion
- reduced transparency
- forced-colors rendering

Regression guardrails for runtime preference behavior live in:

- `packages/ui/src/theme-runtime.test.ts`
- `web/lib/styles-accessibility-contract.test.ts`

# Design-System Token Architecture

## Canonical Source

`/packages/ui` is the canonical source for UKDE web visual tokens and foundational primitives.

No feature route should create a second token system.

## Token Families

The shared token model is defined in `/packages/ui/src/tokens.ts` and grouped by purpose:

- semantic colors
  - background, surfaces, borders, text, accent, focus
  - status and signal colors (environment and access-tier badges)
- typography
  - shell title, page title, section title, body, metadata, microcopy
  - sans, serif, mono families
- spacing
  - dense 4px/8px rhythm with a bounded scale
- shape
  - radius scale from `xs` to `xl` and `pill`
- elevation
  - constrained depth levels (`0..3`)
- motion
  - duration and easing tokens for functional transitions
- focus
  - explicit ring width/offset/spread values

## CSS Variable Contract

`/packages/ui/src/styles.css` maps token values into CSS variables.

Primary semantic variables:

- `--ukde-color-*` for theme-aware colors
- `--ukde-type-*` for typographic scale
- `--ukde-space-*` for spacing rhythm
- `--ukde-radius-*`, `--ukde-shadow-*`, `--ukde-motion-*`, `--ukde-focus-*`

Legacy aliases (`--ukde-bg`, `--ukde-surface`, `--ukde-text`, etc.) remain only as migration bridges for earlier route classes.

## Route-Level Usage

- Use shared primitive classes (`ukde-button`, `ukde-field`, `ukde-panel`, `ukde-badge`, etc.) where possible.
- Keep route CSS for composition/layout concerns.
- Avoid hardcoded color literals in shell-level files; add new visual values in `/packages/ui/src/tokens.ts`.

## Change Workflow

1. Add or adjust token values in `tokens.ts`.
2. Wire token variables and component primitive behavior in `styles.css`.
3. Validate on `/admin/design-system`.
4. Migrate route styles to the shared primitives.
5. Run lint/typecheck/tests before merge.

## Guardrails

- `scripts/check-design-token-literals.mjs` blocks raw color literals in core shell paths.
- `/admin/design-system` is the internal QA surface for token and state behavior across dark/light/contrast/motion preference variants.

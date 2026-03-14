# Layout Segmentation Workspace UX Contract

> Status: Active (Prompt 47)
> Scope: Dense, minimal, keyboard-safe workspace choreography for inspect, reading-order, and edit flows

This contract defines the canonical interaction model for
`/projects/:projectId/documents/:documentId/layout/workspace`.

## Canonical Mode Model

Modes are one deterministic product surface:

- `Inspect` (default): read-only geometry and metrics review.
- `Reading order`: reading-order controls and group/region ordering.
- `Edit`: explicit manual geometry correction mode.

Rules:

- Mode switches are explicit and available from the top toolbar mode group.
- `Edit` mode uses distinct workspace treatment and tool row.
- Inspector tab state follows mode transitions and does not branch into a second workspace.

## Toolbar Hierarchy

Top-row priority stays stable:

1. run selector
2. mode switch group
3. overlay toggles
4. overlay opacity
5. primary save/discard and `Open triage`

Low-frequency controls live in labeled overflow (`Workspace tools`):

- zoom controls
- filmstrip/inspector drawer toggles
- pane width presets

This preserves keyboard-safe density without ribbon sprawl at medium widths.

## Pane Sizing And Adaptive State Rules

Workspace remains single-fold and bounded (`Expanded | Balanced | Compact | Focus`).

- Filmstrip and inspector widths are bounded and persisted per document.
- CSS variables drive pane widths:
  - `--viewer-filmstrip-width`
  - `--viewer-inspector-width`
- Focus/compact states continue using drawer paths for secondary panes.

No default full-page vertical sprawl is allowed; dense areas scroll internally.

## Inspector And Canvas Cohesion

- Hover/select sync remains bidirectional between canvas and inspector lists.
- Reading-order controls stay in inspector context and do not fork route ownership.
- Edit tools mutate staged state only; persisted changes happen only on explicit save.

## Accessibility And Keyboard Guarantees

- Overlay toolbar remains roving-focus and keyboard operable.
- Mode switching, save/discard, and overflow controls are keyboard reachable.
- Focus-visible states remain unobscured in bounded panes.
- Reduced-motion and reduced-transparency behavior from the global contract remains preserved.

## Extension Guardrails

Future prompts may add layout/transcription interactions only if they preserve:

- one workspace shell
- deterministic mode choreography
- bounded pane behavior and single-fold defaults
- explicit save/discard semantics with conflict-safe outcomes

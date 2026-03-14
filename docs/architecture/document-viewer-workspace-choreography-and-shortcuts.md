# Document Viewer Workspace Choreography And Shortcuts

> Status: Active (Prompt 29)
> Scope: Viewer adaptive workspace states, panel behavior, shortcut discoverability, and failure recovery handoff

This document defines the current viewer choreography contract for dense, bounded, browser-native work.

## Adaptive Workspace States

Viewer layout follows shell state (`Expanded | Balanced | Compact | Focus`):

- `Expanded`
  - filmstrip + canvas + inspector all visible
- `Balanced`
  - narrower filmstrip and compressed inspector while preserving canvas priority
- `Compact`
  - filmstrip remains visible in compact width
  - inspector moves to drawer path
- `Focus`
  - canvas dominates
  - filmstrip and inspector move to on-demand drawers

Collapse order remains stable:

1. inspector leaves persistent layout before canvas compression
2. filmstrip collapses to drawer in focus state
3. canvas remains primary surface

## Panel Width Memory And Snap Presets

Viewer supports bounded panel presets via overflow controls:

- filmstrip widths: `narrow | default | wide`
- inspector widths: `narrow | default | wide`

Presets are persisted per project in local storage:

- key: `ukde.viewer.panel-presets:{projectId}`

The viewer applies bounded width adjustments per shell state rather than free-form unbounded panel growth.

## Shortcut Contract

Stable shortcuts:

- `ArrowLeft` / `ArrowRight`: page navigation when focus is in canvas or filmstrip regions
- `+` / `-`: zoom
- `R`: rotate

Toolbar roving focus remains authoritative while focus is in the toolbar.
Shortcuts do not override toolbar arrow-key navigation semantics.

Discoverability remains compact:

- inline hint in viewer toolbar
- no large command-sheet modal

## Recovery And Handoff

Viewer canvas failures expose in-place recovery actions:

- `View ingest status`
- `Open document`
- `Back to documents`

Failure messages distinguish:

- session-style auth loss
- RBAC denial
- missing derived image
- generic asset delivery failure

Viewer-to-ingest-status handoff preserves current viewer context (`page`, `zoom`) for return navigation where available.

## Motion And Accessibility Notes

- Viewer layout transitions remain bounded and avoid default full-page vertical sprawl.
- Reduced-motion preference disables non-essential image/skeleton animation.
- Drawer and toolbar interactions preserve keyboard access and visible focus.

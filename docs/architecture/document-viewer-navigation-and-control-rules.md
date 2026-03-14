# Document Viewer Navigation And Control Rules

> Status: Active baseline (Prompt 26)
> Scope: Toolbar, keyboard/mouse controls, page navigation, and inspector/filmstrip behavior

This document defines interaction rules for the Phase 1 viewer baseline and Prompt 29 polish pass.

## Workspace Choreography

Viewer composition remains single-fold and shell-state aware:

- `Expanded`: filmstrip + canvas + inspector.
- `Balanced`: narrower filmstrip and compressed inspector.
- `Compact`: inspector drawer fallback while filmstrip remains compact.
- `Focus`: canvas-first mode with filmstrip and inspector as on-demand drawers.

Panel width presets are bounded and remembered per project.

## Toolbar Behavior

The viewer toolbar owns:

- Previous page
- Next page
- Zoom out
- Zoom in
- Fit width
- Rotate
- Inspector drawer toggle
- Page jump form (`Page`, numeric input, `Go`)

Rules:

- Uses the shared `Toolbar` primitive with ARIA toolbar roving focus.
- Buttons disable at natural boundaries (for example previous on page 1).
- Zoom percentage remains visible in the toolbar row.
- Compact shortcut hint is visible in the toolbar region.
- Page jump clamps to valid page bounds and does not navigate outside valid range.

## Page Navigation Rules

Navigation entry points:

- Previous/next toolbar buttons
- Filmstrip thumbnail links
- Page jump form
- Keyboard arrows in specific focus contexts

Rules:

- Browser query parameter `page` remains 1-based.
- Left/right arrows navigate pages only when focus is inside the canvas or filmstrip regions.
- Toolbar arrow keys keep toolbar roving focus behavior and do not trigger page navigation.
- Current page highlight appears in both URL state and filmstrip (`aria-current="page"`).

## Zoom, Pan, Rotate Baseline

Zoom:

- Baseline zoom range: `25%` to `400%`.
- Zoom controls: toolbar buttons plus `+` and `-` keyboard shortcuts.
- Fit width computes a bounded zoom target from viewport width.

Pan:

- Pan is pointer-drag based in canvas image frame.
- Pan is enabled only when scaled content exceeds viewport bounds.
- Pan offsets are clamped to prevent uncontrolled drift.

Rotate:

- Triggered from toolbar and `R` shortcut.
- Rotation persists through `PATCH /projects/{projectId}/documents/{documentId}/pages/{pageId}`.
- Rotation remains page-scoped viewer metadata.

## Filmstrip Rules

- Filmstrip uses authenticated thumbnail delivery (`variant=thumb`).
- Current page is visually highlighted and announced by `aria-current`.
- Filmstrip scroll is locally bounded to the filmstrip region.
- If a thumbnail is not ready, the filmstrip shows explicit placeholder status.

## Inspector Rules

- Inspector baseline surfaces:
  - document identity
  - current page and total pages
  - page status
  - dimensions and DPI (when available)
  - current rotation
  - document status chip
- Narrow layouts use the drawer fallback via toolbar toggle.
- Inspector never displaces the canvas as the primary work surface.

## Loading/Error Rules

- Viewer shell remains mounted across loading/ready/error states.
- Not-ready and failure messages are explicit and action-safe.
- Missing page metadata renders a safe, non-crashing error state in the canvas region.
- Canvas failure states expose recovery CTAs:
  - `View ingest status`
  - `Open document`
  - `Back to documents`

## URL-State Contract (Current)

Viewer shareable URL state currently includes:

- `page` (required, 1-based)
- `zoom` (optional, bounded numeric percent, omitted when default)

See:

- [`/docs/architecture/document-viewer-url-state-contract.md`](./document-viewer-url-state-contract.md)

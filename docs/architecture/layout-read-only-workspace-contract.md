# Layout Read-Only Workspace Contract

> Status: Active (Prompt 42)
> Scope: Canonical browser workspace for read-only layout inspection

This contract defines the Phase 3 Iteration 3.2 workspace at:

- `/projects/:projectId/documents/:documentId/layout/workspace?page={pageNumber}&runId={runId}`

The route is the single canonical surface for read-only segmentation inspection.
It is not an edit canvas and does not replace the general document viewer route.

## Ownership

- Server route loads canonical document/run/page/overlay context.
- Client workspace shell owns read-only geometry interaction and responsive pane behavior.
- Overlay geometry is rendered from canonical `DocumentLayoutPageOverlay` payloads only.

## Toolbar Contract

Top toolbar includes:

- explicit run selector
- overlay toggles:
  - regions
  - lines
  - baselines (when present)
  - reading-order arrows (when present)
- overlay opacity control
- `Open triage`
- bounded zoom controls for inspection snapshots

Keyboard behavior:

- overlay toggles use the canonical toolbar primitive with roving focus and arrow-key navigation.
- no keyboard traps are allowed.

## Workspace Composition

The workspace keeps single-fold defaults and bounded internal scrollers:

- collapsible left filmstrip (with drawer fallback in `Focus`)
- center canvas (page image + SVG geometry overlays)
- right inspector (with drawer fallback in `Compact` and `Focus`)

Adaptive state follows shell state (`Expanded | Balanced | Compact | Focus`) and never creates a second workspace shell.

## Run And Page Switching

- `runId` is explicit in URL state.
- run changes navigate to the same workspace route with updated query state.
- page selection uses the same route and query state.
- no "latest successful" guessing is permitted.
- inspector and overlay summaries always reflect the selected run/page payload.

## Non-Goals In This Contract

Not allowed here:

- manual correction tools
- reading-order editing
- crop/context-window generation
- recall/rescue tooling
- transcription tooling

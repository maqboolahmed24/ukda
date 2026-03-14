# Document Viewer Contract

> Status: Active (Prompt 34)
> Scope: Viewer route ownership, compare-mode behavior, run selection, and metrics inspector boundaries

This document defines the current browser viewer contract after preprocessing compare integration.

## Canonical Route Ownership

- Route: `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}&mode={mode}&runId={runId}&zoom={zoom}`
- URL-owned query state:
  - `page` (required canonical, human-facing 1-based)
  - `mode` (`original | preprocessed | compare`, omitted for `original`)
  - `runId` (optional explicit preprocess run, ignored when `mode=original`)
  - `zoom` (optional non-default zoom)

Normalization rules:

- missing/invalid page values normalize to canonical values through redirect
- out-of-range page values normalize to nearest valid page through redirect
- `mode=original` strips run context from canonical URL ownership
- `runId` is trimmed; blank values are removed from canonical URL ownership

## Workspace Contract

The viewer keeps Pattern D single-fold behavior with bounded panes:

- top toolbar with one ARIA-safe toolbar system
- left filmstrip (collapsible first)
- center canvas (always primary visual surface)
- right inspector (aside in wider states, drawer fallback in compact/focus states)

### Viewer Compare Ownership

- Viewer compare is an in-context reading aid.
- `/preprocessing/compare` remains the canonical diagnostics surface for full run-to-run analysis.
- Viewer compare must keep deep links into `/preprocessing/compare` and preserve return context.

## Mode Selector And Run Selector

- Toolbar mode selector owns:
  - `Original`
  - `Preprocessed`
  - `Compare`
- Run selector appears in `Preprocessed` and `Compare` modes only.
- Run resolution behavior:
  - explicit `runId` uses that run
  - omitted `runId` defaults to active preprocess projection
  - no active run and no explicit run must fail explicitly and safely

## Compare Rendering And Inspector

- Compare rendering (v1): side-by-side split (`Original` vs `Preprocessed`).
- Inspector content ownership:
  - page metrics
  - warning chips
  - resolved run context
  - deep link to quality table
  - deep link to canonical `/preprocessing/compare`

## Canonical Data Surfaces

- `GET /projects/{projectId}/documents/{documentId}`
- `GET /projects/{projectId}/documents/{documentId}/pages`
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}`
- `PATCH /projects/{projectId}/documents/{documentId}/pages/{pageId}`
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}/variants?runId={runId}`
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}/image?variant={variant}&runId={runId}`

## Accessibility And Interaction Gates

- Toolbar keyboard model stays predictable (roving-focus semantics preserved in shared toolbar primitive).
- No keyboard traps across toolbar, canvas, and drawer flows.
- Focus visibility remains explicit in toolbar and inspector flows.
- Reflow/zoom scenarios use controlled region scrolling rather than clipping full-page layout.

## Security Posture

- No raw-original download path is exposed by the viewer.
- All image bytes remain authenticated and same-origin proxied.
- No storage keys or public object URLs are exposed in viewer links or route payloads.

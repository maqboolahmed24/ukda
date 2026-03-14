# Layout Reading Order: Inference, Uncertainty, and Override

This document defines how reading order is inferred, surfaced, and reviewer-overridden in Phase 3.

## Canonical Model

Reading order remains part of canonical layout artefacts:

- `PAGE-XML` serializes reading order edges plus ordered/unordered groups.
- Overlay JSON exposes:
  - `readingOrder`
  - `readingOrderGroups`
  - `readingOrderMeta`

`readingOrderMeta` carries confidence and ambiguity signals:

- `mode`: `ORDERED` | `UNORDERED` | `WITHHELD`
- `columnCertainty`
- `overlapConflictScore`
- `orphanLineCount`
- `nonTextComplexityScore`
- `ambiguityScore`
- `orderWithheld`
- `source` (`AUTO_INFERRED` or `MANUAL_OVERRIDE`)

## Inference Rules (v1)

Inference runs during layout segmentation:

1. Regions are clustered into likely columns from geometry.
2. Column certainty and conflict signals are computed.
3. Output mode is selected:
   - high confidence: `ORDERED`
   - medium confidence: `UNORDERED`
   - high ambiguity: `WITHHELD`
4. Groups and edges are generated deterministically from the canonical layout graph.

The same input layout/runtime produces the same inferred reading-order output.

## Reviewer Override Path

Reviewer-capable roles (`PROJECT_LEAD`, `REVIEWER`, `ADMIN`) can save reading-order overrides via:

- `PATCH /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/reading-order`

Request includes:

- current `versionEtag` (optimistic lock)
- `mode`
- replacement `groups` (tree/group order)

Behavior:

- stale `versionEtag` returns `409 Conflict`
- references are validated against existing persisted regions
- no duplicate region assignment across groups
- mode/group compatibility is enforced (`WITHHELD` allows empty groups)

## Append-Only Versioning

Each saved reading-order override appends a new `layout_versions` row:

- prior versions stay immutable
- `base_version_id` links lineage
- superseded version gets `superseded_by_version_id`
- `page_layout_results.active_layout_version_id` points to the latest saved page version

The baseline (auto-generated) page state is bootstrapped into `layout_versions` before first manual override.

## Context Window Regeneration

Reading-order edits can change neighboring-line context.

For the edited page only:

- line context-window payloads are recomputed from canonical reading-order edges
- only changed context windows are rewritten
- unchanged line/region crops remain intact
- stable line IDs remain unchanged

## Audit

Reading-order saves emit:

- `LAYOUT_READING_ORDER_UPDATED`

Audit metadata is limited to reading-order version/mode/signals, not full page content.

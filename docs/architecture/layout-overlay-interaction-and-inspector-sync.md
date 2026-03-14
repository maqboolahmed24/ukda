# Layout Overlay Interaction And Inspector Sync

> Status: Active (Prompt 42)
> Scope: Read-only geometry interaction semantics in the layout workspace

This document defines interaction semantics for canonical read-only overlays rendered from `DocumentLayoutPageOverlay`.

## Overlay Layers

Canvas overlay layers are controlled independently:

- region polygons
- line polygons
- baselines (line-level, optional)
- reading-order arrows (optional)

Opacity applies to the overlay layer as a whole and never mutates source geometry.

## Selection Model

The workspace uses explicit read-only selection states:

- hover: transient highlight on pointer enter
- selected: pinned highlight on click
- clear selection: explicit action in inspector or canvas background click

Selection is ID-based and mapped to canonical overlay IDs (`region_id` and `line_id` equivalents in payload `elements[].id`).

## Canvas <-> Inspector Synchronization

Required sync rules:

- canvas region click selects the same region row in inspector
- canvas line click selects the same line row in inspector
- inspector region/line click highlights the same geometry in canvas
- line list is filtered by selected region when region context exists

This keeps geometry inspection deterministic and avoids stale cross-pane state.

## Reading-Order Rendering

Reading-order arrows are drawn from canonical `readingOrder` edges:

- edge source/target IDs must resolve to existing overlay elements
- arrows are suppressed when their referenced layer is hidden
- no editing affordance is exposed in this phase

## State Accuracy And Not-Ready Behavior

When overlay output is not available:

- show explicit `not ready` or `unavailable` state in canvas
- keep page/result metadata visible in inspector
- do not fabricate geometry placeholders as canonical output

## Accessibility Expectations

- toolbar is keyboard-operable via roving focus
- inspector drawer and filmstrip drawer use focus-safe overlay primitives
- focus visibility must remain unobscured across pane and drawer transitions

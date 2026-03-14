# Layout Segmentation Metrics, Warnings, and Recall-State Accuracy Contract

This document defines canonical Prompt 41-44 metrics/warnings semantics and page recall-state behavior.

## Required Metrics

Each successful `page_layout_results` row persists:

- `num_regions`
- `num_lines`
- `region_coverage_percent`
- `line_coverage_percent`
- `recall_check_version`
- `missed_text_risk_score`
- `rescue_candidate_count`
- `accepted_rescue_candidate_count`

The implementation also records deterministic diagnostics (`region_overlap_score`, `line_overlap_score`, `column_count`, threshold metadata, rescue-candidate quality) for triage and regression analysis.

## Warning Semantics

Warnings are deterministic string codes:

- `LOW_LINES`
  - emitted when detected line count is below a page-height-adjusted floor
- `OVERLAPS`
  - emitted when region or line overlap score crosses configured overlap thresholds
- `COMPLEX_LAYOUT`
  - emitted for high structural complexity (for example, many regions or multi-column complexity)

Warnings are persisted on `page_layout_results.warnings_json` and surfaced in overview/triage APIs.

## Recall-Status Semantics (Prompt 44)

Layout segmentation is followed by a second-stage recall check (`layout-recall-v1`) that persists:

- `layout_recall_checks.recall_check_version`
- `layout_recall_checks.missed_text_risk_score`
- `layout_recall_checks.signals_json`

Every successful page resolves to one explicit class:

- `COMPLETE`
- `NEEDS_RESCUE`
- `NEEDS_MANUAL_REVIEW`

Rules:

- pages are not auto-promoted to `COMPLETE` by geometry existence alone
- sparse or structurally risky pages can still be `NEEDS_RESCUE` even when no faint components are found
- suspicious faint/noisy components can produce persisted rescue candidates (`LINE_EXPANSION` or `PAGE_WINDOW`)
- merged faint components hidden in anomalously tall line envelopes are treated as rescue signals, not silently dropped

## Run and Page Accuracy Rules

- page failures stay persisted (`FAILED`) and are not overwritten by finalize
- canceled pages remain explicit (`CANCELED`)
- run finalization is computed from actual page outcomes; it does not infer success from job completion alone
- PAGE-XML/overlay key+SHA fields (`page_xml_key`, `overlay_json_key`, `page_xml_sha256`, `overlay_json_sha256`) are populated only on successful materialization
- recall-check and rescue-candidate rows are persisted as part of page materialization, so downstream activation checks are auditably queryable

## Gold-Set Regression Coverage

Regression gates enforce:

- structural floors (line recall and region overlap)
- recall-check versioning
- recall-floor behavior on handwritten/faint fixtures
- rescue-candidate quality expectations on curated fixtures

This complements polygon-validity and line-to-region association tests to reduce silent segmentation drift.

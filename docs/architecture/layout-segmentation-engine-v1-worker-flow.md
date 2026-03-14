# Layout Segmentation Engine v1 Worker Flow

This document defines the implemented worker pipeline for Phase 3 Prompt 41.

## Job Types

- `LAYOUT_ANALYZE_DOCUMENT`
- `LAYOUT_ANALYZE_PAGE`
- `FINALIZE_LAYOUT_RUN`

All three job types execute through the canonical `jobs` framework and worker runtime. No secondary queue is introduced.

## Input Selection

Each layout run resolves input from the run row:

- `layout_runs.input_preprocess_run_id` is the authoritative preprocess basis.
- Per page, workers read `page_preprocess_results` for that exact preprocess run and page.
- Only `SUCCEEDED` preprocess page results with `output_object_key_gray` are valid layout inputs.

This keeps layout analysis tied to explicit preprocess lineage, not implicit latest-successful heuristics.

## Per-Page Pipeline

For each page job:

1. claim page input from the selected preprocess run
2. decode the preprocessed grayscale page
3. run deterministic region/line segmentation heuristics
4. convert geometry to canonical polygons and simplify
5. associate lines to regions deterministically
6. compute layout metrics and warnings
7. write canonical PAGE-XML and overlay JSON through the existing storage contract
8. persist page-result keys/hashes/metrics/warnings
9. keep recall status explicit and non-promotable (`NEEDS_RESCUE` or `NEEDS_MANUAL_REVIEW`)

PAGE-XML + overlay writes reuse:

- `DocumentService.materialize_layout_page_outputs`
- `DocumentStorage.write_layout_page_xml`
- `DocumentStorage.write_layout_page_overlay`
- `DocumentStorage.write_layout_manifest`

## Run/Page State Transitions

Implemented store transitions:

- `mark_layout_run_running`
- `mark_layout_page_running`
- `complete_layout_page_result`
- `fail_layout_page_result`
- `finalize_layout_run`

Finalization computes run status from page outcomes:

- any page `FAILED` -> run `FAILED`
- queued/running pages remain -> run `RUNNING`
- all pages `SUCCEEDED` -> run `SUCCEEDED`
- canceled mix -> run `CANCELED`

Canceled runs stop page scheduling and remain explicit in persisted state.

## Idempotency and Retry

- Page jobs dedupe on `(run_id, page_id)` through canonical job dedupe keys.
- Retry of already-succeeded page jobs is idempotent (`SUCCEEDED` row is reused).
- Page result rows are not duplicated.

## Audit Events

Worker flow uses canonical layout audit events:

- `LAYOUT_RUN_STARTED`
- `LAYOUT_RUN_FINISHED`
- `LAYOUT_RUN_FAILED`
- `LAYOUT_RUN_CANCELED`

`LAYOUT_RUN_CREATED` remains emitted on run creation.

## Security Posture

- Internal-only execution.
- No public model downloads.
- No external inference calls.
- Controlled derived storage only.
- No bypass around existing outbound policy boundaries.

## What This Prompt Intentionally Defers

- read-only overlay UX polish
- stable line-crop/context-window artifact materialization
- deeper recall-check and rescue-candidate workflows
- manual layout edit tools

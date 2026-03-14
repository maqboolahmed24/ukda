# Transcription Run And Projection Model

Status: Implemented foundation + primary execution + governed fallback/compare (Prompts 49, 51, and 52)
Scope: Run lineage, worker execution, fallback invocation gates, compare snapshots, compare decisions, governed artefact storage, projection activation, and downstream invalidation hooks

## Canonical tables

Transcription state is modeled with:

- `transcription_runs`
- `page_transcription_results`
- `line_transcription_results`
- `token_transcription_results`
- `transcript_versions`
- `document_transcription_projections`
- `transcription_output_projections`
- `transcription_compare_decisions`
- `transcription_compare_decision_events`

`approved_models` remains the FK-ready source for run `model_id`.

## Primary + fallback execution path

The jobs runtime executes:

- `TRANSCRIBE_DOCUMENT(run_id)`
- `TRANSCRIBE_PAGE(run_id, page_id)`
- `FINALIZE_TRANSCRIPTION_RUN(run_id)`

Primary runs use `VLM_LINE_CONTEXT` through the approved internal service path. Fallback runs use the same run family with governed fallback engines (`KRAKEN_LINE`, optional `TROCR_LINE` and `DAN_PAGE` only when governance requirements are met).

Fallback runs are created through `POST /transcription-runs/fallback` and are gated by explicit reasons:

- `SCHEMA_VALIDATION_FAILED`
- `ANCHOR_RESOLUTION_FAILED`
- `CONFIDENCE_BELOW_THRESHOLD`

Fallback invocation metadata is persisted in run `params_json.fallback_invocation` and `fallback_source_run_id`.

## Immutable source-run rule

Fallback and compare flows are append-only:

- fallback execution creates a new candidate run
- base run outputs remain immutable
- compare decisions persist in dedicated decision tables
- no compare decision mutates base/candidate source run rows directly

There is no automatic merge or silent promotion path.

## Compare snapshot + decision model

`GET /transcription-runs/compare` returns a typed compare snapshot:

- base/candidate run metadata
- page-level output availability
- line-level diffs
- token-level diffs
- changed-confidence summaries
- current decision projections (when present)

`POST /transcription-runs/compare/decisions` writes explicit `KEEP_BASE` or `PROMOTE_CANDIDATE` outcomes:

- one current projection row per compare target tuple
- optimistic-concurrency writes via `decision_etag`
- full append-only chronology in `transcription_compare_decision_events`

## Governed storage contract

Transcription outputs are controlled-only:

- `controlled/derived/{project_id}/{document_id}/transcription/{run_id}/page/{page_index}.xml`
- `controlled/derived/{project_id}/{document_id}/transcription/{run_id}/page/{page_index}.response.json`
- `controlled/derived/{project_id}/{document_id}/transcription/{run_id}/page/{page_index}.hocr` (fallback-owned)

`page_id` always resolves through canonical document page metadata before deriving `{page_index}`.

Browser-facing APIs expose status and checksums, not controlled raw-response keys.

## Run lineage and activation

`transcription_runs` remains append-only with supersession pointers:

- `supersedes_transcription_run_id`
- `superseded_by_transcription_run_id`
- `attempt_number`

Activation requires:

1. run status `SUCCEEDED`
2. basis match with active layout projection
3. token-anchor prerequisites (`token_anchor_status == CURRENT` for eligible lines/pages)

## Related contracts

- [`/docs/architecture/transcription-diplomatic-normalised-versioning-contract.md`](./transcription-diplomatic-normalised-versioning-contract.md)
- [`/docs/architecture/transcription-fallback-and-compare-governance-contract.md`](./transcription-fallback-and-compare-governance-contract.md)
- [`/docs/architecture/transcription-compare-decision-contract.md`](./transcription-compare-decision-contract.md)

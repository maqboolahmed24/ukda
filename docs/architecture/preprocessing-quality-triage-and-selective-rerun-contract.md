# Preprocessing Quality Triage And Selective Rerun Contract

> Status: Active (Prompt 35)
> Scope: Document quality tab ownership, hotspot filters, selective reruns, and compare delta contract

This contract defines the Phase 2 triage workflow for difficult pages inside a single document.

## Quality Tab Ownership

Canonical route:

- `/projects/:projectId/documents/:documentId/preprocessing/quality`

This route owns:

- table-first page-quality triage
- hotspot filtering (`warning`, `skewMin`, `skewMax`, `blurMax`, `failedOnly`)
- bulk page selection
- per-page details drawer (before/after mini previews, metrics, warnings, status)
- selective rerun wizard
- compare handoff to canonical compare route

## Queue And Filter Semantics

Table columns:

- page number
- warnings
- skew
- blur score
- DPI
- status

Filter semantics:

- `warning`: row contains selected warning token
- `skewMin` / `skewMax`: row `metricsJson.skew_angle_deg` falls in requested range
- `blurMax`: row `metricsJson.blur_score <= blurMax`
- `failedOnly`: row is non-succeeded or quality-gate blocked

`runId` is URL-owned and selects which run populates the queue rows.

## Selective Rerun API Contract

Endpoint:

- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/rerun`

Request body additions:

- `profileId` (`CONSERVATIVE | BALANCED | AGGRESSIVE | BLEED_THROUGH`, optional)
- `targetPageIds` (optional page subset)
- `advancedRiskConfirmed` (optional; required for full-document advanced reruns)
- `advancedRiskAcknowledgement` (optional confirmation note, max 400 chars)

Persistence rules:

- rerun always appends a new run row
- source run is immutable
- expanded params are persisted with a recomputed params hash
- subset reruns persist:
  - `runScope = PAGE_SUBSET`
  - `targetPageIdsJson = [...]`
  - `paramsJson.target_page_ids = [...]`
- whole-document reruns persist:
  - `runScope = FULL_DOCUMENT`
  - `targetPageIdsJson = null`

Risk posture rules:

- full-document `AGGRESSIVE` and `BLEED_THROUGH` reruns require explicit confirmation
- `PAGE_SUBSET` reruns do not require advanced risk confirmation
- run metadata stores risk posture + confirmation details for audit and reproducibility

Execution rule:

- subset reruns enqueue page tasks only for selected page IDs

## Compare API Delta Contract

Endpoint:

- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`

Per-page payload now includes:

- `warningDelta`
- `addedWarnings`
- `removedWarnings`
- `metricDeltas`
- `outputAvailability` (`baseGray`, `baseBin`, `candidateGray`, `candidateBin`)

Viewer compare options remain bounded to one pair at a time:

- `Original vs Gray`
- `Original vs Binary`
- `Gray vs Binary`

Audit rule:

- compare reads emit `PREPROCESS_COMPARE_VIEWED`

## Role Boundaries

- view triage/compare/runs: `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, `ADMIN`
- create/rerun/cancel/activate runs: `PROJECT_LEAD`, `REVIEWER`, `ADMIN`

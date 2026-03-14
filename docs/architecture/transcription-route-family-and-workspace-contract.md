# Transcription Route Family And Workspace Contract

Status: Implemented baseline + primary + fallback/compare + editable workspace surfaces (Prompts 49, 51, 52, and 56)
Scope: Canonical document-scoped transcription IA, queue views, run detail, deep-link workspace, fallback lifecycle APIs, compare shell, and worker-backed status progression

## Route ownership

Transcription is owned under a single document-scoped family:

- `/projects/:projectId/documents/:documentId/transcription`
- `/projects/:projectId/documents/:documentId/transcription/runs/:runId`
- `/projects/:projectId/documents/:documentId/transcription/workspace?page={page}&runId={runId}&mode={mode}&lineId={lineId}&tokenId={tokenId}&sourceKind={sourceKind}&sourceRefId={sourceRefId}`
- `/projects/:projectId/documents/:documentId/transcription/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}&page={page}&lineId={lineId}&tokenId={tokenId}`

No parallel transcription route family is allowed.

## Information architecture

`/transcription` resolves internal navigation by `tab` query:

- `overview` (default): projection, active/latest run, progress and confidence summary
- `triage`: page-first queue for low-confidence and anchor-refresh hotspots
- `runs`: run lineage, status, and role-gated actions
- `artefacts`: run-page output/provenance availability

Run focus is optional and URL-driven via `runId`.

## Workspace deep-link contract

Workspace state must be fully URL-restorable:

- `page` (1-based, required for deterministic focus)
- `runId` (required for deterministic run focus)
- `mode` (`reading-order` or `as-on-page`; optional, defaults to reading-order)
- `lineId` (optional line highlight)
- `tokenId` (optional token highlight when anchors exist)
- `sourceKind` and `sourceRefId` (optional provenance fallback when no stable line anchor exists)

Reloading the URL must restore selected run/page and optional line/token/source context without hidden local state.

Workspace is editable for reviewer-capable roles and must preserve optimistic-concurrency conflict handling for diplomatic corrections.

## Role boundaries

View routes (`overview`, `triage`, `runs`, `artefacts`, `workspace`) are available to:

- `PROJECT_LEAD`
- `RESEARCHER`
- `REVIEWER`
- `ADMIN`

Run and compare reads are available to:

- `PROJECT_LEAD`
- `RESEARCHER`
- `REVIEWER`
- `ADMIN`

Run mutations (`create`, `cancel`, `activate`, `fallback`) are limited to:

- `PROJECT_LEAD`
- `REVIEWER`
- `ADMIN`

Compare decision writes are limited to:

- `PROJECT_LEAD`
- `REVIEWER`
- `ADMIN`

## API alignment

Route surfaces consume typed APIs:

- `GET /transcription/overview`
- `GET /transcription/triage`
- `POST /transcription-runs`
- `POST /transcription-runs/fallback`
- `GET /transcription-runs`
- `GET /transcription-runs/active`
- `GET /transcription-runs/{runId}`
- `GET /transcription-runs/{runId}/status`
- `GET /transcription-runs/{runId}/pages`
- `POST /transcription-runs/{runId}/activate`
- `POST /transcription-runs/{runId}/cancel`
- `GET /transcription-runs/{runId}/pages/{pageId}/lines`
- `PATCH /transcription-runs/{runId}/pages/{pageId}/lines/{lineId}`
- `GET /transcription-runs/{runId}/pages/{pageId}/tokens`
- `GET /transcription-runs/{runId}/pages/{pageId}/variant-layers?variantKind=NORMALISED`
- `POST /transcription-runs/{runId}/pages/{pageId}/variant-layers/NORMALISED/suggestions/{suggestionId}/decision`
- `GET /transcription-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`
- `POST /transcription-runs/compare/decisions`

Run status polling uses the dedicated status endpoint, not full run-detail refresh.

## Compare shell behavior

The compare route is intentionally minimal but explicit:

- base/candidate context is URL-addressable and deep-link-safe
- page/line/token diff shells are shown without hidden merge behavior
- decision controls are only shown for `PROJECT_LEAD`, `REVIEWER`, and `ADMIN`
- empty/not-ready/error states remain explicit and non-destructive
- no automatic merge or silent promotion path exists in the route shell

## Artefact exposure policy

Run page APIs expose PAGE-XML availability and raw-response checksums, but do not expose controlled raw-response storage keys to browser callers.

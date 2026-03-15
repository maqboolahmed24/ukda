# Transcription Route Family And Workspace Contract

Status: Updated in Prompt 57
Scope: Canonical document-scoped transcription IA, deep-link workspace, compare/history route refinements, and immutable composed-run finalization

## Route ownership

Transcription is owned under a single document-scoped family:

- `/projects/:projectId/documents/:documentId/transcription`
- `/projects/:projectId/documents/:documentId/transcription/runs/:runId`
- `/projects/:projectId/documents/:documentId/transcription/workspace?page={page}&runId={runId}&mode={mode}&lineId={lineId}&tokenId={tokenId}&sourceKind={sourceKind}&sourceRefId={sourceRefId}`
- `/projects/:projectId/documents/:documentId/transcription/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}&page={page}&lineId={lineId}&tokenId={tokenId}`
- `/projects/:projectId/documents/:documentId/transcription-runs/:runId/pages/:pageId/lines/:lineId/versions`
- `/projects/:projectId/documents/:documentId/transcription-runs/:runId/pages/:pageId/lines/:lineId/versions/:versionId`

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

Compare decision writes and compare finalize are limited to:

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
- `GET /transcription-runs/{runId}/rescue-status`
- `GET /transcription-runs/{runId}/pages`
- `GET /transcription-runs/{runId}/pages/{pageId}/rescue-sources`
- `POST /transcription-runs/{runId}/activate`
- `PATCH /transcription-runs/{runId}/pages/{pageId}/rescue-resolution`
- `POST /transcription-runs/{runId}/cancel`
- `GET /transcription-runs/{runId}/pages/{pageId}/lines`
- `GET /transcription-runs/{runId}/pages/{pageId}/lines/{lineId}/versions`
- `GET /transcription-runs/{runId}/pages/{pageId}/lines/{lineId}/versions/{versionId}`
- `PATCH /transcription-runs/{runId}/pages/{pageId}/lines/{lineId}`
- `GET /transcription-runs/{runId}/pages/{pageId}/tokens`
- `GET /transcription-runs/{runId}/pages/{pageId}/variant-layers?variantKind=NORMALISED`
- `POST /transcription-runs/{runId}/pages/{pageId}/variant-layers/NORMALISED/suggestions/{suggestionId}/decision`
- `GET /transcription-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}&page={page}&lineId={lineId}&tokenId={tokenId}`
- `POST /transcription-runs/compare/decisions`
- `POST /transcription-runs/compare/finalize`

Run status polling uses the dedicated status endpoint, not full run-detail refresh.

Rescue readiness and manual-resolution state are exposed via dedicated typed endpoints; activation must not infer recall safety from raw rows alone.

## Compare shell behavior

The compare route is explicit, review-safe, and lineage-aware:

- base/candidate context is URL-addressable and deep-link-safe
- page/line/token diff shells are shown without hidden merge behavior
- response includes `compareDecisionSnapshotHash`, decision counts, and decision-event counts
- decision controls are only shown for `PROJECT_LEAD`, `REVIEWER`, and `ADMIN`
- finalize is guarded by explicit decisions and optional expected snapshot hash
- finalize creates a new immutable `REVIEW_COMPOSED` run and never mutates source runs
- empty/not-ready/error states remain explicit and non-destructive
- no automatic merge or silent promotion path exists in the route shell

## Lineage and workspace integration

Workspace and run-detail surfaces preserve provenance context:

- compare can deep-link into workspace via `page`, `runId`, `lineId`, and `tokenId`
- workspace can open immutable line-version history drawer per selected line
- run detail shows composed lineage fields (`baseRunId`, `candidateRunId`, `compareDecisionSnapshotHash`, `finalizedBy`, `finalizedAt`)
- diplomatic and normalised layers remain separate; normalised suggestions are auditable through variant-layer events

## Artefact exposure policy

Run page APIs expose PAGE-XML availability and raw-response checksums, but do not expose controlled raw-response storage keys to browser callers.

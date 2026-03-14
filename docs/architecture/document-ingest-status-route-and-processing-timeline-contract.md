# Document Ingest-Status Route And Processing Timeline Contract

> Status: Active (Prompts 29-30)
> Scope: `/projects/:projectId/documents/:documentId/ingest-status`, timeline reuse, polling behavior, and recovery actions

This contract defines the first-class ingest-status route and the canonical timeline behavior shared with document detail surfaces.

## Canonical Route

- `/projects/:projectId/documents/:documentId/ingest-status`

Optional query context may be carried from the viewer handoff path:

- `page` (1-based viewer page hint)
- `zoom` (bounded viewer zoom hint)

These keys are used only for recovery handoff links back into the viewer.

## Surface Ownership

The ingest-status route:

- stays inside the authenticated project shell
- uses project-scoped header/breadcrumb patterns
- presents dense operational timeline detail without page-level sprawl
- keeps safe recovery actions visible in one section:
  - `Open viewer`
  - `Open document`
  - `Back to documents`
- exposes retry extraction control only when the latest unsuperseded extraction attempt is `FAILED` or `CANCELED`
- routes retry through `POST /projects/{projectId}/documents/{documentId}/retry-extraction`

## Canonical Timeline Component

One shared component powers document-detail and ingest-status timeline rendering.

Primary behavior:

- append-only event list from `GET /projects/{projectId}/documents/{documentId}/processing-runs`
- explicit stage ordering:
  - `UPLOAD`
  - `SCAN`
  - `EXTRACTION`
  - `THUMBNAIL_RENDER`
- failure/canceled branches stop at real reached stages
- no implied success for later stages that never ran
- run detail drilldown available from:
  - `GET /projects/{projectId}/documents/{documentId}/processing-runs/{runId}`

## Active Polling Contract

When any run is active (`QUEUED` or `RUNNING`), the timeline polls:

- `GET /projects/{projectId}/documents/{documentId}/processing-runs/{runId}/status`

Polling updates only status-facing fields for active runs.
When a run settles into a terminal state, the timeline performs a single refresh of the processing-runs list to sync final event payload details.

This avoids repeatedly reloading full run collections while active status is changing.

## Recovery Language And Action Rules

The ingest-status and viewer recovery paths maintain explicit distinctions:

- still processing
- failed
- canceled
- missing page/image asset
- access denied
- session-expired-style asset failure

Routes must expose concrete next actions instead of vague generic errors when state is known.

## Retry Visibility Gate

- Retry action visibility is data-gated by processing-run lineage (`supersededByProcessingRunId === null`) and run terminal status.
- Unauthorized retry requests fail closed with `403`.
- Conflict responses (`409`) are surfaced when retry preconditions are not met.

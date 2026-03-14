# Document Route Family And Ingest IA Contract

> Status: Active baseline, Prompt 25 extension, and Prompt 30 hardening
> Scope: Project-scoped document library, resumable import workflow, detail/viewer routing, page-asset API integration, and library URL/filter interaction contract

This document defines the implemented information architecture for the project document family.
It is intentionally scoped to route ownership, shell composition, and non-goals for the baseline ingest skeleton.

## Canonical Routes

All routes are project-scoped and mounted under the authenticated shell:

- `/projects/:projectId/documents`
- `/projects/:projectId/documents/import`
- `/projects/:projectId/documents/:documentId`
- `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`
- `/projects/:projectId/documents/:documentId/ingest-status`
- `/projects/:projectId/documents/:documentId/preprocessing`
- `/projects/:projectId/documents/:documentId/preprocessing/quality`
- `/projects/:projectId/documents/:documentId/preprocessing/runs/:runId`
- `/projects/:projectId/documents/:documentId/preprocessing/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`

Rules:

- Documents library is the default project document workspace.
- Import is a dedicated route reached from the documents page header primary action (`Import document`).
- Import is not represented as nested side navigation.
- Viewer `page` query is human-facing and 1-based.
- Preprocessing compare selection is URL-owned by `baseRunId` and `candidateRunId`.

Preprocessing route ownership and diagnostics IA are documented in:

- [`/docs/architecture/preprocessing-route-family-and-review-ia-contract.md`](./preprocessing-route-family-and-review-ia-contract.md)

## Shell And Header Composition

- Route family inherits the canonical authenticated shell and project workspace header.
- Breadcrumbs are orientation-only:
  - `Projects -> Project -> Documents`
  - `Projects -> Project -> Documents -> Document`
  - `Projects -> Project -> Documents -> Document -> Viewer -> Page N`
- Documents route surfaces one primary page-header action only: `Import document`.

## Route-Level Surface Contracts

### `/documents`

- Table-oriented primary surface using the shared `DataTable` primitive.
- Required baseline columns: Name, Status, Pages, Uploaded by, Date.
- Row selection opens a details drawer path.
- Search and filter bar (`search`, `status`, `uploader`, `from`, `to`) is URL-owned.
- Server-side sort and cursor paging (`sort`, `direction`, `cursor`) are URL-owned.
- Multi-select and restrained bulk-action rail are available without destructive mutations.
- Empty/no-results/error states are explicit and route-safe.

### `/documents/import`

- Dedicated wizard-like shell with three staged steps:
  1. Select files
  2. Confirm metadata and destination project
  3. Upload and status
- Resumable upload flow with explicit session handoff:
  - session create/read/chunk/complete/cancel under `/documents/import-sessions`
  - resume position driven by backend `nextChunkIndex`
  - session completion remains server-controlled
- Import status polling:
  - active progression: `UPLOADING -> QUEUED -> SCANNING`
  - post-scan terminals: `ACCEPTED | REJECTED | FAILED | CANCELED`
  - cancel allowed only while `UPLOADING` or `QUEUED`

### `/documents/:documentId`

- Metadata section.
- Current ingest status section.
- Processing-run timeline section.
- Derived readiness section (ready/pending/failed page counts).
- Actions section prepared for:
  - `Open document`
  - `View ingest status`
- Viewer action stays disabled until status/page readiness is real.
- `View ingest status` links to dedicated ingest-status route (with optional viewer context hints).

### `/documents/:documentId/ingest-status`

- Dense, route-owned processing timeline surface.
- Uses canonical timeline component shared with document detail.
- Shows explicit ordered stage model plus append-only event list.
- Polls per-run status endpoints while runs are active.
- Exposes extraction retry control only when latest extraction attempt is retry-eligible.
- Exposes safe recovery actions back to viewer/detail/library routes.

### `/documents/:documentId/viewer`

- Canonical `page` query normalization and safe redirects.
- Bounded single-fold workspace scaffold with slots for:
  - toolbar
  - filmstrip
  - canvas
  - inspector (plus drawer path)
- Detailed baseline behavior is defined in:
  - [`/docs/architecture/document-viewer-baseline-contract.md`](./document-viewer-baseline-contract.md)
  - [`/docs/architecture/document-viewer-navigation-and-control-rules.md`](./document-viewer-navigation-and-control-rules.md)
- Not-ready/error states are explicit and sourced from page metadata/status.
- No raw-original file link or direct asset URL path.

## Baseline APIs Used By The Web Routes

- `GET /projects/{projectId}/documents`
- `GET /projects/{projectId}/documents/{documentId}`
- `GET /projects/{projectId}/documents/{documentId}/timeline`
- `GET /projects/{projectId}/documents/{documentId}/processing-runs`
- `GET /projects/{projectId}/documents/{documentId}/processing-runs/{runId}`
- `GET /projects/{projectId}/documents/{documentId}/processing-runs/{runId}/status`
- `POST /projects/{projectId}/documents/{documentId}/retry-extraction`
- `GET /projects/{projectId}/documents/{documentId}/pages`
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}`
- `PATCH /projects/{projectId}/documents/{documentId}/pages/{pageId}`
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}/image?variant=full|thumb`
- `POST /projects/{projectId}/documents/import`
- `POST /projects/{projectId}/documents/import-sessions`
- `GET /projects/{projectId}/documents/import-sessions/{sessionId}`
- `POST /projects/{projectId}/documents/import-sessions/{sessionId}/chunks?chunkIndex={chunkIndex}`
- `POST /projects/{projectId}/documents/import-sessions/{sessionId}/complete`
- `POST /projects/{projectId}/documents/import-sessions/{sessionId}/cancel`
- `GET /projects/{projectId}/document-imports/{importId}`
- `POST /projects/{projectId}/document-imports/{importId}/cancel`

All are project-membership protected.

## Security Posture

- Document metadata access is project-RBAC scoped.
- No cross-project metadata leakage.
- No public asset route assumptions.
- No raw-original download affordance in the document-family UI.

## Non-Goals (Deferred)

- Shareable multi-parameter viewer URL-state restoration beyond `page`.

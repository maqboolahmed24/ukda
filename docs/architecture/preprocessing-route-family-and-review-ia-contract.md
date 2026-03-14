# Preprocessing Route Family And Review IA Contract

> Status: Active (Prompt 35)
> Scope: Document-scoped preprocessing routes, compare-route ownership, quality triage, and viewer handoff contract

This document defines the canonical preprocessing information architecture implemented for Phase 2 iteration `2.0`.
It is scoped to route ownership, shell integration, and API-route alignment.

## Canonical Routes

All preprocessing routes are document-scoped and mounted under the authenticated project shell:

- `/projects/:projectId/documents/:documentId/preprocessing`
- `/projects/:projectId/documents/:documentId/preprocessing/quality`
- `/projects/:projectId/documents/:documentId/preprocessing/runs/:runId`
- `/projects/:projectId/documents/:documentId/preprocessing/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}&page={page}&viewerMode={viewerMode}&viewerComparePair={viewerComparePair}&viewerRunId={viewerRunId}`

Rules:

- `/preprocessing` is the entry route and supports internal navigation for:
  - `Pages`
  - `Quality`
  - `Processing runs`
  - `Metadata`
- `quality` and `runs/:runId` are deep-linkable companion routes, not a second route family.
- `compare` is the canonical diagnostics surface.
- `compare` supports two states:
  - two-run diagnostics (`baseRunId` + `candidateRunId`)
  - single-run diagnostics (`candidateRunId` only) when only one run is available

## Ownership And Viewer Boundary

- `/preprocessing/compare` is the canonical preprocessing diagnostics surface for run-to-run analysis.
- `/viewer` compare affordances are contextual reading aids.
- Viewer compare entry points must provide a route-safe handoff to `/preprocessing/compare` when deeper diagnostics are needed.
- Compare routes preserve viewer return context through:
  - `page`
  - `viewerMode`
  - `viewerComparePair`
  - `viewerRunId`

This keeps reading workflows in the viewer while preserving one authoritative analysis workspace for preprocessing.

## URL-State Contract

- Browser-facing `page` remains 1-based on viewer routes.
- Preprocessing compare selection is URL-owned via `baseRunId` and `candidateRunId`.
- Viewer return choreography from compare is URL-owned via `page`, `viewerMode`, and `viewerRunId`.
- Viewer compare pair (`viewerComparePair`) is URL-owned and bounded to:
  - `original_gray`
  - `original_binary`
  - `gray_binary`
- Quality route triage filters are URL-owned and typed (`runId`, `warning`, `skewMin`, `skewMax`, `blurMax`, `failedOnly`, `compareBaseRunId`).
- Route reload restores selected run/compare/filter context without hidden local state.

## Quality Triage Ownership

The canonical `Quality` tab is table-first and operator-dense:

- columns:
  - page number
  - warnings
  - skew
  - blur score
  - DPI
  - status
- filters:
  - warning type
  - skew range
  - blur threshold
  - failed only
- queue ergonomics:
  - bulk selection of filtered pages
  - clear selection
  - selection count visibility
- actions:
  - primary: `Re-run preprocessing` (wizard)
  - secondary: `Compare runs` (canonical `/preprocessing/compare`)
- advanced profiles and risk confirmation are progressive-disclosure controls, collapsed by default
- details drawer:
  - before/after mini previews
  - metrics breakdown
  - warning/status context
  - `Open in viewer`

## Backend API Alignment

Canonical preprocessing APIs:

- `GET /projects/{projectId}/documents/{documentId}/preprocessing/overview`
- `GET /projects/{projectId}/documents/{documentId}/preprocessing/quality`
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/active`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/status`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/pages`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/pages/{pageId}`
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/rerun`
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/cancel`
- `POST /projects/{projectId}/documents/{documentId}/preprocess-runs/{runId}/activate`
- `GET /projects/{projectId}/documents/{documentId}/preprocess-runs/compare`

Web route handlers under `web/app/(authenticated)/projects/[projectId]/documents/[documentId]/preprocess-runs/**` proxy this API family and preserve project/document scope.

Canonical response contract refinements:

- preprocess run payloads expose explicit run-state flags:
  - `isActiveProjection`
  - `isSuperseded`
  - `isCurrentAttempt`
  - `isHistoricalAttempt`
- projection and run payloads expose downstream basis impact:
  - `layoutBasisState` + basis run reference
  - `transcriptionBasisState` + basis run reference
- state values are explicit (`NOT_STARTED | CURRENT | STALE`) and are emitted server-side so clients do not infer staleness from ad hoc row inspection

## Shell Integration

- Preprocessing routes inherit the same project shell, page-header composition, and breadcrumb orientation contract as the document/viewer family.
- Document detail, ingest status, and viewer surfaces provide entry links into preprocessing routes.
- Preprocessing navigation never detaches users from the current project/document context.

## Current Scope And Deferred Depth

Implemented in Prompt 31:

- overview, quality, runs, compare, and metadata route surfaces
- typed API scaffolding and RBAC/audit wiring
- active-run projection reads for default quality/overview behavior

Deferred to later prompts:

- deterministic image-transform execution engine and real grayscale artefact generation
- advanced compare visualization beyond triage-focused deltas and availability flags

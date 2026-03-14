# Layout Analysis Route Family And Segmentation Workspace Contract

> Status: Active (Prompts 39-44)
> Scope: Document-scoped layout-analysis IA, run surfaces, triage/workspace route ownership, canonical overlay/PAGE-XML access paths, and recall-first read surfaces

This document defines the canonical Phase 3 Iteration 3.0 layout-analysis route family.
It covers route ownership, shell composition, and API alignment for overview/run management plus canonical per-page overlay/PAGE-XML retrieval.

## Canonical Routes

All layout routes are document-scoped and mounted inside the authenticated project shell:

- `/projects/:projectId/documents/:documentId/layout`
- `/projects/:projectId/documents/:documentId/layout/runs/:runId`
- `/projects/:projectId/documents/:documentId/layout/workspace?page={pageNumber}&runId={runId}`

Rules:

- `/layout` is the entry route with internal navigation for:
  - `Layout overview`
  - `Page triage`
  - `Runs`
- `runs/:runId` is the canonical run detail surface.
- `workspace` is the canonical segmentation workspace route for page-level inspection.
- no second layout route family is allowed outside this project/document scope.

## Information Architecture Ownership

- `Layout overview` is the summary surface for active projection state and run health.
- `Page triage` is table-first and document-scoped to one run selection.
- `Runs` is the lineage and operation surface for create/cancel/activate actions.
- `Run detail` is a focused route for one run's status and per-page summary.
- `Workspace` is a dedicated segmentation shell; advanced tooling does not appear in generic document routes.

## URL-State Contract

- Browser `page` query remains human-facing and 1-based.
- `runId` is explicit in `workspace` query state and optional in `/layout` for run-focused navigation.
- `/layout` defaults to `document_layout_projections.active_layout_run_id` where available.
- no route infers active/default run by "latest successful" guessing.

## Workspace Shell Contract (Read-Only In Prompt 42)

The workspace preserves the single-fold adaptive shell composition:

- top toolbar:
  - run selector
  - overlay toggles (regions, lines, baselines, reading-order arrows when present)
  - overlay opacity control
  - `Open triage`
- left rail:
  - page filmstrip
- center:
  - page canvas
- right inspector:
  - page metrics
  - warning chips
  - region tree
  - line list filtered by selected region

Prompt 42 behavior:

- read-only workspace shell with canonical overlay rendering
- hover/select synchronization between canvas and inspector
- explicit not-ready/error messaging when overlay payloads are absent
- bounded internal scrolling and keyboard-safe controls
- drawer fallback for filmstrip and inspector in constrained shell states

## Backend API Alignment

Canonical APIs for this route family:

- `GET /projects/{projectId}/documents/{documentId}/layout/overview`
- `POST /projects/{projectId}/documents/{documentId}/layout-runs`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/active`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/status`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/recall-status`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/rescue-candidates`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/overlay`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/pagexml`
- `POST /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/cancel`
- `POST /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/activate`

Next.js route handlers under
`web/app/(authenticated)/projects/[projectId]/documents/[documentId]/layout/**`
and
`web/app/(authenticated)/projects/[projectId]/documents/[documentId]/layout-runs/**`
proxy this canonical API family.

## RBAC And Audit Surface

Role boundaries:

- view layout routes and artefacts:
  - `PROJECT_LEAD`
  - `RESEARCHER`
  - `REVIEWER`
  - `ADMIN`
- mutate layout runs (create/cancel/activate):
  - `PROJECT_LEAD`
  - `REVIEWER`
  - `ADMIN`

Audit events:

- `LAYOUT_OVERVIEW_VIEWED`
- `LAYOUT_TRIAGE_VIEWED`
- `LAYOUT_RUNS_VIEWED`
- `LAYOUT_ACTIVE_RUN_VIEWED`
- `LAYOUT_RUN_CREATED`
- `LAYOUT_RUN_ACTIVATED`
- `LAYOUT_RUN_STARTED`
- `LAYOUT_RUN_FINISHED`
- `LAYOUT_RUN_FAILED`
- `LAYOUT_RUN_CANCELED`
- `LAYOUT_ACTIVATION_BLOCKED`
- `LAYOUT_RECALL_STATUS_VIEWED`
- `LAYOUT_RESCUE_CANDIDATES_VIEWED`
- `LAYOUT_OVERLAY_ACCESSED`
- `LAYOUT_PAGEXML_ACCESSED`

## Explicitly Deferred From Prompt 44

Deferred to later prompts:

- manual geometry correction and reading-order editing tooling
- full manual rescue-transcription execution
- token-anchor materialization
- downstream invalidation orchestration hard gates owned by Prompt 48

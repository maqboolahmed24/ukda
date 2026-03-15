# Privacy Route Family And Workspace Contract

Status: Updated through Prompt 76
Scope: Canonical document-scoped privacy information architecture, run detail/events, compare workspace, dual-control review gating, reviewed-output readiness, and safeguarded preview access rules

## Route ownership

Privacy review is owned under one document-scoped route family:

- `/projects/:projectId/documents/:documentId/privacy`
- `/projects/:projectId/documents/:documentId/privacy/runs/:runId`
- `/projects/:projectId/documents/:documentId/privacy/runs/:runId/events`
- `/projects/:projectId/documents/:documentId/privacy/workspace?page={page}&runId={runId}&findingId={findingId}&lineId={lineId}&tokenId={tokenId}`
- `/projects/:projectId/documents/:documentId/privacy/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}&page={page}&findingId={findingId}&lineId={lineId}&tokenId={tokenId}`

No second privacy route family is allowed.

## Information architecture

`/privacy` uses tabbed IA via URL query state:

- `overview` (default): active projection summary, findings-by-category, unresolved counts, page blockers, preview readiness
  - includes baseline triage split: auto-applied, needs-review, overridden
- `triage`: page-first queue with category and unresolved filters plus direct-identifier slicing
- `runs`: run lineage and status list with deterministic links into run detail

Required overview actions:

- primary CTA: `Create privacy review run`
- overflow actions: `Compare runs`, `Open active workspace`, `Complete review`

## Workspace shell contract

The privacy workspace is a bounded single-fold shell with:

- left rail: page list with review status and unresolved counts
- center canvas: safeguarded preview image plus finding highlight context
- right panel: transcript context, findings list, and page review projection
- top toolbar:
  - mode switch: `Controlled view` / `Safeguarded preview`
  - previous/next page
  - next unresolved
  - show/hide highlights (safeguarded mode only)
  - open safeguarded preview asset when ready

Mode rules:

- `Controlled view` shows source transcript context and does not pretend to be a masked artefact.
- `Safeguarded preview` shows the deterministic masked preview artefact and truthful readiness/failure states.
- URL query state carries mode so deep links are restorable.

Workspace deep links are URL-restorable by `page`, `runId`, and optional `findingId`, `lineId`, `tokenId`.

## Run and event surfaces

- `/privacy/runs/:runId` reads run summary, run status, run review projection, run pages, and latest append-only events.
- run detail surfaces typed blocker reasons for start-review and complete-review actions:
  - `PAGE_REVIEW_NOT_STARTED`
  - `PAGE_REVIEW_NOT_APPROVED`
  - `SECOND_REVIEW_PENDING`
  - `PREVIEW_NOT_READY`
  - plus run-state blockers when review status is not eligible
- `/privacy/runs/:runId/events` shows append-only merged timeline entries from decision, page-review, run-review, and run-output event tables.
- `/privacy/compare` compares base/candidate run page deltas, including second-review and preview-readiness deltas, and preserves optional page/finding/line/token context.
- compare is read-only and includes rerun lineage references (`supersedes`/`supersededBy`) so reviewers can inspect rerun ancestry without mutating either run.
- compare RBAC is `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, and read-only `AUDITOR`.
- compare includes candidate-policy context and pre-activation warnings for broad allow rules or inconsistent thresholds.
- validated `DRAFT` policy reruns are surfaced as comparison-only candidates and do not imply policy activation.

Finding and area-mask APIs used by workspace:

- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/findings`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/findings/{findingId}`
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/area-masks`
- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/area-masks/{areaMaskId}`

Area-mask edits are append-only revisions; prior geometry rows remain readable and auditable.

## Safe preview route rules

Safeguarded preview bytes are exposed only through authenticated internal routes:

- API: `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/preview`
- Web proxy: `/projects/:projectId/documents/:documentId/privacy/runs/:runId/pages/:pageId/preview`

Rules:

- no raw object-store URLs in browser payloads
- ETag and conditional revalidation are supported
- cache policy is private/no-store style and authorization-varying
- explicit not-ready/failure states are represented through preview-status reads

Run-level reviewed output read surfaces:

- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/output`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/output/status`

These endpoints return status, readiness state, and manifest hash only; they do not leak object-storage keys.

## RBAC baseline

General privacy view access:

- `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, `ADMIN`

Reviewed output artefact/status reads (`preview-status`, `preview`, `output`, `output/status`):

- `PROJECT_LEAD`, `REVIEWER`, `ADMIN`
- read-only `AUDITOR` for `APPROVED` runs only
- `RESEARCHER` denied

Mutations (`create`, `cancel`, `activate`, `start-review`, `complete-review`, finding/page/mask updates):

- `PROJECT_LEAD`, `REVIEWER`, `ADMIN`

## Prompt sequencing

Prompt 59 establishes IA and scaffolding only.

- Prompt 60 deepens detector generation and direct-identifier finding production.
- Prompt 61 deepens token-linked findings and conservative area-mask handling.
- Prompt 62 deepens baseline decision-engine behavior, mask-only defaults, deterministic safeguarded preview projection, and explicit Phase 7 deferral for pseudonymisation/generalization.
- Prompt 63 adds fast-resolution workspace interactions, deterministic next-unresolved deep links, approve/override/false-positive decisions, and page approval gating. See `privacy-workspace-resolution-and-page-approval-contract.md`.
- Prompt 64 adds dual-control second-review enforcement, immutable post-approval lock behavior, and compare-route rerun deltas.
- Prompt 65 adds immutable approved-snapshot artefact capture, snapshot-backed reviewed-output generation, run-output eventing, and explicit readiness handoff semantics.

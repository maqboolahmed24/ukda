# Route Map And User Journeys

> Status: Future-facing browser IA contract
> Scope: Stable route design for the secure web product

Current implemented baseline route ownership is defined in:

- [`/docs/architecture/route-layout-and-url-state-contract.md`](./route-layout-and-url-state-contract.md)

## Route Design Principles

1. Every durable object gets a stable URL anchored by object identity.
2. Review context that matters after refresh or sharing belongs in URL state.
3. Project context stays explicit in the path once a user is inside a project.
4. Route transitions must preserve orientation through breadcrumbs, page titles, and consistent shell regions.
5. Dense review surfaces use nested layouts and bounded regions instead of sending users through modal-only workflows.
6. Browser URLs use `:param` notation in docs. Filesystem routing can translate that to framework-specific conventions such as `[param]`.
7. Human-facing `page` query parameters are 1-based unless a route states otherwise.

## Global And Shell Routes

| Route                              | Purpose                                                       | Notes                                                         |
| ---------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------- |
| `/login`                           | Authentication entry and callback landing                     | Public route only until a session exists                      |
| `/`                                | Lightweight entry resolver                                    | In Phase 0.1, redirects to `/login`; later becomes auth-aware |
| `/health`                          | Live operational diagnostics                                  | Public route for browser-to-API liveness/readiness visibility |
| `/projects`                        | Project list, filters, and quick resume                       | Primary landing surface for most authenticated users          |
| `/approved-models`                 | Platform-approved model catalog for transcription-facing roles | Read: lead/reviewer/admin, mutate: lead/admin                 |
| `/projects/:projectId/overview`    | Project home with recent activity, status, and next actions   | Stable project anchor route                                   |
| `/projects/:projectId/jobs`        | Project job queue, retry controls, and run status             | Member-scoped read; mutation controls are role-gated          |
| `/projects/:projectId/jobs/:jobId` | Job attempt detail, append-only events, and lineage links     | Status polling uses the lightweight status endpoint contract  |
| `/projects/:projectId/members`     | Membership and role management                                | Project lead and admin surface                                |
| `/projects/:projectId/settings`    | Project metadata, purpose, retention, and governance settings | Scoped to project authority                                   |

## Ingest And Viewer Routes

| Route                                               | Purpose                                                          | URL-state expectations                                                                                |
| --------------------------------------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `/projects/:projectId/ingest`                       | Controlled upload, intake status, and import feedback            | Preserve queue filter and selected batch                                                              |
| `/projects/:projectId/documents`                    | Document library with search, sorting, filters, and bulk actions | Filters, sort, and selection belong in the query string                                               |
| `/projects/:projectId/documents/:documentId`        | Document summary, run history, and metadata                      | Stable document anchor                                                                                |
| `/projects/:projectId/documents/:documentId/ingest-status` | Dedicated processing timeline and recovery handoff               | Optional viewer handoff hints (`page`, `zoom`) may be carried for return navigation                  |
| `/projects/:projectId/documents/:documentId/viewer` | Browser viewer workspace                                         | Baseline preserves `page`; later phases add shareable `zoom`, `rotation`, `panel`, and review context |

## Processing Workspace Routes

| Route                                                                                | Purpose                                           | URL-state expectations                                                                 |
| ------------------------------------------------------------------------------------ | ------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `/projects/:projectId/documents/:documentId/preprocessing`                          | Preprocessing overview, tabs, and run entrypoint | Preserve internal tab (`pages`, `runs`, `metadata`)                                   |
| `/projects/:projectId/documents/:documentId/preprocessing/quality`                  | Preprocessing quality diagnostics                 | Preserve `runId`, `warning`, `status`, and cursor filters                             |
| `/projects/:projectId/documents/:documentId/preprocessing/runs/:runId`              | Preprocessing run detail                          | Preserve selected run and linked compare context                                       |
| `/projects/:projectId/documents/:documentId/preprocessing/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}` | Canonical preprocessing run comparison diagnostics | Preserve base/candidate run IDs and compare inspector context                          |
| `/projects/:projectId/documents/:documentId/layout`                                  | Layout overview, triage, and run tabs            | Preserve selected tab and optional `runId` focus                                       |
| `/projects/:projectId/documents/:documentId/layout/runs/:runId`                      | Layout run detail                                 | Preserve selected run context and workspace handoff                                    |
| `/projects/:projectId/documents/:documentId/layout/workspace?page={page}&runId={runId}` | Segmentation workspace shell                      | Preserve 1-based `page`, selected `runId`, overlay mode, and inspector context        |
| `/projects/:projectId/documents/:documentId/transcription`                            | Transcription overview, triage, runs, artefacts   | Preserve selected tab and optional `runId` focus                                       |
| `/projects/:projectId/documents/:documentId/transcription/runs/:runId`                | Transcription run detail                           | Preserve selected run context and workspace handoff                                    |
| `/projects/:projectId/documents/:documentId/transcription/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}&page={page}&lineId={lineId}&tokenId={tokenId}` | Transcription compare mode for governed base-vs-candidate review | Preserve base/candidate run IDs and optional page/line/token focus for deterministic decision context |
| `/projects/:projectId/documents/:documentId/transcription/workspace?page={page}&runId={runId}&mode={mode}&lineId={lineId}&tokenId={tokenId}&sourceKind={sourceKind}&sourceRefId={sourceRefId}` | Editable transcription workspace                   | Preserve page/run/mode, optional line/token anchors, source provenance, and correction context |
| `/projects/:projectId/model-assignments`                                               | Project role-map assignment list and lifecycle actions | Preserve selected role filters or status context when added                            |
| `/projects/:projectId/model-assignments/:assignmentId`                                 | Assignment detail, lifecycle metadata, and role compatibility | Stable assignment anchor                                                                |
| `/projects/:projectId/model-assignments/:assignmentId/datasets`                        | Training dataset lineage for one assignment          | Stable dataset lineage view anchored by assignment                                      |
| `/projects/:projectId/privacy`                                                       | Privacy-review queue and unresolved findings list | Preserve queue filter, severity, and selected document/page                            |
| `/projects/:projectId/privacy/runs/:runId/documents/:documentId/pages/:pageId`       | Privacy review workspace                          | Preserve findings filter, selected token or area mask, compare mode, and inspector tab |

## Governance, Release, And Discovery Routes

| Route                                               | Purpose                                            | URL-state expectations                                   |
| --------------------------------------------------- | -------------------------------------------------- | -------------------------------------------------------- |
| `/projects/:projectId/manifests`                    | Candidate manifests, statuses, and sign-off entry  | Preserve release state filter and selected candidate     |
| `/projects/:projectId/manifests/:manifestId`        | Manifest detail and reconciliation view            | Stable manifest anchor                                   |
| `/projects/:projectId/evidence`                     | Controlled evidence and lineage drill-down         | Preserve evidence type, actor filter, and selected event |
| `/projects/:projectId/policies`                     | Policy assignment, simulation, and version history | Preserve active version and diff target                  |
| `/projects/:projectId/export-candidates`            | Export candidate listing surface (Phase 0 stub)    | Preserve future candidate filters when enabled           |
| `/projects/:projectId/export-requests`              | Export request listing surface (Phase 0 stub)      | Preserve `status`, `requesterId`, `candidateKind`        |
| `/projects/:projectId/export-review`                | Export review queue surface (Phase 0 stub)         | Preserve `status`, `agingBucket`, `reviewerUserId`       |
| `/projects/:projectId/provenance`                   | Provenance overview and bundle inventory           | Preserve bundle filter and selected proof node           |
| `/projects/:projectId/provenance/bundles/:bundleId` | Proof bundle detail and verification view          | Stable bundle anchor                                     |
| `/projects/:projectId/discovery/search`             | Controlled search and jump-to-context results      | Preserve query, filters, sort, and selected hit          |
| `/projects/:projectId/discovery/entities`           | Governed entity index and review surfaces          | Preserve entity type, filters, and selected entity       |

## Platform-Level Admin And Audit Routes

| Route                             | Purpose                                                   | Notes                                     |
| --------------------------------- | --------------------------------------------------------- | ----------------------------------------- |
| `/admin`                          | Platform governance home                                  | Admin and read-only auditor               |
| `/admin/security`                 | Security posture summary and deny-egress diagnostics      | Admin and read-only auditor               |
| `/admin/operations`               | Operations overview and telemetry posture                 | Admin-only                                |
| `/admin/operations/export-status` | Export gateway posture and queue-readiness summary        | Admin and read-only auditor               |
| `/admin/operations/slos`          | SLO baselines and threshold state                         | Admin-only                                |
| `/admin/operations/alerts`        | Alert scaffold with filterable state                      | Admin-only                                |
| `/admin/operations/timelines`     | Read-only operational timelines and trace correlation     | Admin and read-only auditor               |
| `/admin/audit`                    | Audit event exploration and correlation search            | Auditor and admin route                   |
| `/admin/evidence-ledger`          | Controlled evidence ledger exploration                    | Auditor and admin route                   |
| `/admin/model-catalog`            | Approved internal model catalog and service-map oversight | Admin-only                                |
| `/admin/runs`                     | Cross-project run operations and failure triage           | Admin-only                                |
| `/admin/design-system`            | Internal component gallery and shell-state test surface   | Internal-only non-public production route |

## URL-State Discipline

- Put durable review context in the URL: page number, selected run, selected line/token/region, compare mode, active panel, filters, and sort.
- Do not put secrets, raw PII, or mutable draft content in the URL.
- Use stable IDs in paths. Use query parameters for view state.
- When a user opens a deep link, the page should restore the same object focus and inspector context without requiring hidden local state.

## User Journey Guidance

### Zero-State To First Useful Work

1. User logs in at `/login`.
2. In Phase 0.1, `/` redirects to `/login` as a lightweight entry resolver.
3. After auth-aware redirects are added, `/` sends users to the correct next route (`/login` or `/projects`).
4. Once inside a project, `/projects/:projectId/overview` is the stable project anchor for later workflow routes.

### Researcher Journey

1. Enter project home at `/projects/:projectId/overview`.
2. Upload and monitor intake through `/projects/:projectId/documents/import`.
3. Review library state in `/projects/:projectId/documents`.
4. Open source context in `/projects/:projectId/documents/:documentId/viewer`.
5. Consume approved downstream outputs through the later workflow routes without losing project or document context.

### Reviewer Journey

1. Enter the relevant route for preprocessing, layout, transcription, or privacy.
2. For preprocessing diagnostics, start from `/projects/:projectId/documents/:documentId/preprocessing` and open `/preprocessing/compare` for run analysis.
3. Open the deep-linkable page workspace for the assigned run.
4. Resolve uncertainty with source, findings, confidence, and inspector context visible together.
5. Move back to the queue without losing filters or place in line.

### Project Lead Journey

1. Manage members and project purpose from the project routes.
2. Inspect policy, manifest, evidence, and export surfaces inside the same project shell.
3. Approve or reject governed transitions with full lineage available by link, not by detached report.

### Auditor And Admin Journeys

1. Use platform-level routes for cross-project audit, evidence, operations, and model governance.
2. Drill from aggregate surfaces into stable project and object routes.
3. Verify that release, provenance, and audit trails stay navigable without privileged side channels.

## Navigation Contract

- Breadcrumbs should reflect project -> surface -> run/object context.
- The shell should keep primary navigation stable while secondary navigation adapts per route family.
- Back navigation must feel predictable because URL state, not hidden modal state, carries review context.

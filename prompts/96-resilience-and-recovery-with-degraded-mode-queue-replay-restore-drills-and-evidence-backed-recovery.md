You are the implementation agent for UKDE. Work directly in the repository. Do not ask clarifying questions. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: assume zero chat memory and reread the repo plus the listed phase files before changing anything.
- Sequenced: if the repo already contains partial implementation from earlier prompts, extend and reconcile it instead of restarting from scratch.

The actual product source of truth is the extracted `/phases` directory in repo root. Do not mention or expect a zip. Read `/phases` first on every run.

## Mandatory first actions
1. Inspect the full repository tree.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — job orchestration, queues, dead-letter handling, snapshot/restore tooling, admin operations surfaces, routes, browser tests, runbooks, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second recovery-control plane, a second drill model, or conflicting degraded-mode semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for resilience and recovery drill requirements, admin-only recovery API access, degraded-mode UX, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that recovery must be executed and evidenced, not just documented.

## Objective
Build resilience and recovery with degraded-mode UX, queue replay, restore drills, and evidence-backed recovery.

This prompt owns:
- retries, dead-letter queues, and idempotent replay paths
- snapshot/restore strategy integration
- recovery drill records, status, evidence, and cancel flow
- admin-only recovery routes
- degraded-state banners and recovery-mode UX across long-running workspaces
- restore-drill evidence surfacing in operations timelines
- chaos and restore regression coverage

This prompt does not own:
- performance tuning
- security findings workflow
- release automation
- public status pages
- a second recovery orchestration system

## Phase alignment you must preserve
From Phase 11 Iteration 11.2:

### Required backend work
- retries and dead-letter queues
- idempotent jobs
- DB and object-store snapshot strategy
- approved model artefact snapshot and restore strategy
- restore automation and runbooks
- per-role restore order so `privacy-rules` and `transcription-fallback` can recover independently of the primary VLM

### Required table
`recovery_drills`:
- `id`
- `scope`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `started_by`
- `started_at`
- `finished_at`
- `canceled_by`
- `canceled_at`
- `evidence_summary_json`
- `failure_reason`

### Required APIs
- `GET /admin/recovery/status`
- `GET /admin/recovery/drills`
- `POST /admin/recovery/drills`
- `GET /admin/recovery/drills/{drillId}`
- `GET /admin/recovery/drills/{drillId}/status`
- `GET /admin/recovery/drills/{drillId}/evidence`
- `POST /admin/recovery/drills/{drillId}/cancel`

### RBAC
- all recovery APIs are backend-enforced `ADMIN` only
- `AUDITOR` does not access live recovery status, drill execution, or drill evidence endpoints in v1

### Required web routes
- `/admin/recovery/status`
- `/admin/recovery/drills`
- `/admin/recovery/drills/:drillId`
- `/admin/recovery/drills/:drillId/evidence`

### Required UX and tests
- drill detail polls status endpoint, not full record reload
- degraded-state banners for recovery mode on long-running workspaces
- restore-drill evidence panels on admin operations timelines for `ADMIN`; auditor timelines may show only redacted drill-status summaries
- redacted auditor drill-status summaries are limited to `drill_id`, `status`, `started_at`, `finished_at`, and short `summary`
- redacted auditor drill-status summaries must exclude `evidence_summary_json`, evidence storage keys, and raw failure details
- chaos tests:
  - kill worker pods and jobs recover
  - interrupt storage access and system degrades safely
- restore drill from snapshots into a clean environment
- model services restore from approved artefacts without public-network fetches
- non-admin callers rejected at every recovery API
- audit events:
  - `RECOVERY_STATUS_VIEWED`
  - `RECOVERY_DRILLS_VIEWED`
  - `RECOVERY_DRILL_VIEWED`
  - `RECOVERY_DRILL_STATUS_VIEWED`
  - `RECOVERY_DRILL_EVIDENCE_VIEWED`
  - `RECOVERY_DRILL_CREATED`
  - `RECOVERY_DRILL_STARTED`
  - `RECOVERY_DRILL_FINISHED`
  - `RECOVERY_DRILL_FAILED`
  - `RECOVERY_DRILL_CANCELED`

## Implementation scope

### 1. Retry, dead-letter, and replay hardening
Implement or refine canonical recovery-safe job behavior.

Requirements:
- idempotent retries
- dead-letter handling
- replay from safe checkpoints where supported
- no second queue/replay framework
- recovery behavior remains observable and auditable

### 2. Snapshot and restore orchestration
Implement or refine restore orchestration.

Requirements:
- DB snapshot strategy
- object-store snapshot strategy
- approved model artefact restore path
- per-role restore ordering
- no public-network fetches for model recovery
- restore steps remain machine-readable and operator-readable

### 3. Recovery drill lifecycle
Implement the admin drill flow.

Requirements:
- create drill
- run drill
- poll drill status
- evidence retrieval
- cancel when appropriate
- append-only drill history
- deterministic status transitions

### 4. Recovery status and evidence surfaces
Implement or refine the admin recovery routes.

Requirements:
- current recovery status
- drill list
- drill detail
- drill evidence
- timeline-linked drill entries outside admin recovery routes remain summary-only, with only `drill_id`, `status`, `started_at`, `finished_at`, and short `summary`
- timeline-linked drill entries outside admin recovery routes never include `evidence_summary_json`, evidence storage keys, or raw failure details
- calm, exact internal UI
- no second operations shell

### 5. Degraded-mode UX
Refine degraded-state behavior in the product.

Requirements:
- recovery-mode banners on long-running workspaces where relevant
- degraded-state clearly distinct from permanent failure or data-loss semantics
- export approval or release state is not confused with recovery mode
- no dramatic outage theatrics

### 6. Chaos and restore tests
Add or refine resilience coverage.

Requirements:
- kill worker pods and jobs recover
- interrupt storage access and the system degrades safely
- restore drills can run into a clean environment
- evidence captured in `recovery_drills`
- non-admin access blocked at API level

### 7. Audit and documentation
Use the canonical audit path and document the recovery system.

Requirements:
- audit events for all recovery surfaces and drill transitions
- runbooks explain restore and replay clearly
- docs show degraded-mode semantics and admin-only boundaries

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / workers / contracts
- retry/dead-letter/replay hardening
- snapshot/restore orchestration
- recovery drill lifecycle and APIs
- tests

### Web
- admin recovery status, drills, detail, and evidence routes
- degraded-state banners where relevant

### Docs
- recovery and restore drill doc
- degraded-mode and operator-recovery doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small degraded-mode/admin recovery refinements are needed
- storage/ops helpers used by the repo
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- performance tuning
- security findings workflow
- release automation
- public recovery/status pages
- a second recovery plane

## Testing and validation
Before finishing:
1. Verify idempotent retries and dead-letter behavior.
2. Verify recovery drills can be created and progress through canonical states.
3. Verify chaos tests demonstrate worker recovery and safe degraded behavior on storage interruption.
4. Verify restore drills can recover from snapshots into a clean environment.
5. Verify recovery mode is surfaced clearly in the UI where relevant.
6. Verify all `/admin/recovery/*` APIs reject non-admin callers server-side.
7. Verify auditor-visible timeline-linked drill summaries include only `drill_id`, `status`, `started_at`, `finished_at`, and `summary`.
8. Verify auditor-visible timeline-linked drill summaries exclude `evidence_summary_json`, evidence storage keys, and raw failure details.
9. Verify docs match the implemented recovery and degraded-mode behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- resilience and recovery tooling is real
- recovery drills are real and evidenced
- degraded-mode UX is real and safe
- non-admin access to `/admin/recovery/*` APIs and drill evidence payloads is blocked
- the platform now has executed recovery evidence instead of only plans
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

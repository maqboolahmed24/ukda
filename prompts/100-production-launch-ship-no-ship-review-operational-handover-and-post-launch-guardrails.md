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
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — runbooks, incidents, operations/security/readiness evidence, release automation, smoke suites, recovery drills, model rollback evidence, docs, and admin routes — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second launch-readiness package, a second runbook or incident model, or conflicting post-launch guardrails.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for operational readiness, runbook and incident routes, read-only auditor access on incident surfaces, and final go-live expectations.
- Official docs win only for implementation mechanics.
- Preserve the rule that launch readiness is evidence-backed, operationally owned, and reversible.

## Objective
Cut the production launch with final ship/no-ship review, operational handover, and post-launch guardrails.

This prompt owns:
- final launch-readiness package and no-go criteria
- runbooks and incident surfaces
- operational handover artifacts and ownership views
- ship/no-ship review evidence collation
- post-launch watch and guardrails over critical flows
- audit-safe `ADMIN` access to runbooks and read-only `AUDITOR` access to incident timelines
- final readiness and handover docs for operators

This prompt does not own:
- new feature development
- marketing or communications work
- a second incident system
- a second runbook store
- public status or incident comms pages

## Phase alignment you must preserve
From Phase 11 Iteration 11.4:

### Required backend work
- release readiness checklist
- change management and rollback procedure
- on-call ownership and escalation paths
- named operational ownership for the model service map, approved-model lifecycle, and rollback execution
- `runbooks` records:
  - `id`
  - `slug`
  - `title`
  - `owner_user_id`
  - `last_reviewed_at`
  - `status`
  - `storage_key`
- `incidents` records:
  - `id`
  - `severity`
  - `status`
  - `started_at`
  - `resolved_at`
  - `incident_commander_user_id`
  - `summary`
- `incident_timeline_events` records:
  - `id`
  - `incident_id`
  - `event_type`
  - `actor_user_id`
  - `summary`
  - `created_at`

### Required APIs
- `GET /admin/runbooks`
- `GET /admin/runbooks/{runbookId}`
- `GET /admin/runbooks/{runbookId}/content`
- `GET /admin/incidents`
- `GET /admin/incidents/status`
- `GET /admin/incidents/{incidentId}`
- `GET /admin/incidents/{incidentId}/timeline`

### RBAC
- runbook reads are `ADMIN` only
- incident list/status/detail/timeline reads are `ADMIN` and read-only `AUDITOR`
- backend handlers enforce these checks server-side

### Required web routes
- `/admin/runbooks`
- `/admin/runbooks/:runbookId`
- `/admin/incidents`
- `/admin/incidents/status`
- `/admin/incidents/:incidentId`
- `/admin/incidents/:incidentId/timeline`

### Required E2E gates
- go-live rehearsal covering ingest through export review
- incident response tabletop completed
- approved-model rollback rehearsal completed for the primary transcription VLM
- `ADMIN` can access runbook and incident surfaces
- `AUDITOR` remains read-only on incident list/status/detail/timeline views
- audit events:
  - `RUNBOOK_LIST_VIEWED`
  - `RUNBOOK_DETAIL_VIEWED`
  - `INCIDENT_LIST_VIEWED`
  - `INCIDENT_STATUS_VIEWED`
  - `INCIDENT_VIEWED`
  - `INCIDENT_TIMELINE_VIEWED`

## Implementation scope

### 1. Canonical runbook surfaces
Implement or refine the admin runbook routes.

Requirements:
- runbook list
- runbook detail
- rendered runbook content
- clear ownership and last-reviewed status
- `ADMIN` only
- no second runbook access path

### 2. Canonical incident surfaces
Implement or refine the incident routes.

Requirements:
- incident list
- incident status summary
- incident detail
- incident timeline
- read-only `AUDITOR` support
- calm, dense operations-grade UI
- no second incident surface

### 3. Ship / no-ship readiness package
Implement or refine a final readiness package.

Requirements:
- collates:
  - SLO/ops evidence
  - capacity evidence
  - recovery drill evidence
  - security findings/risk acceptance status
  - go-live rehearsal state
  - model rollback rehearsal state
  - export/no-bypass readiness
- explicit blockers and no-go criteria
- machine-readable and operator-readable
- no hidden spreadsheet as source of truth

This may live in docs, generated artifacts, or admin-only read surfaces, but it must be reviewable and coherent.

### 4. Operational handover
Implement or refine handover artifacts.

Requirements:
- on-call ownership
- escalation paths
- named ownership for model service map, approved-model lifecycle, and rollback execution
- runbooks linked from readiness package where useful
- no ambiguity about who owns launch-day and post-launch response

### 5. Post-launch guardrails
Implement or refine immediate post-launch controls.

Requirements:
- guardrail checklist for critical user and batch paths
- incident-status surfaces ready for early-life monitoring
- clear rollback procedure and trigger points
- no broad feature toggling system required if the repo does not already have one; focus on clear operational guardrails

### 6. Audit and E2E evidence
Use the canonical audit path and add/verify end-to-end gates.

Requirements:
- ingest through export-review go-live rehearsal evidence exists
- incident response tabletop evidence exists
- approved-model rollback rehearsal evidence exists
- admin/auditor role boundaries on runbook/incident routes are correct
- access audit events emit through the canonical path

### 7. Documentation
Document:
- final ship/no-ship decision package
- operational handover and ownership
- post-launch watch and rollback guardrails
- what “launch ready” means in evidence terms

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- runbook and incident read surfaces
- readiness package aggregation
- tests

### Web
- runbook list/detail
- incident list/status/detail/timeline
- admin-only/read-only auditor access behavior
- readiness or handover read surfaces if needed

### Docs
- final launch readiness and ship/no-ship doc
- operational handover and post-launch guardrails doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small runbook/incident/readiness refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- new product features
- marketing/PR materials
- a second incident or runbook system
- public incident/status pages

## Testing and validation
Before finishing:
1. Verify runbook routes are `ADMIN` only.
2. Verify incident routes are `ADMIN` and read-only `AUDITOR`.
3. Verify go-live rehearsal evidence is collated and reviewable.
4. Verify incident response tabletop and model rollback rehearsal evidence are included.
5. Verify the readiness package shows explicit blockers and no-go criteria.
6. Verify operational ownership and escalation paths are visible in handover materials.
7. Verify docs match the implemented launch-readiness and handover behavior.
8. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- final ship/no-ship review is evidence-backed
- runbook and incident surfaces are real
- operational handover is explicit
- post-launch guardrails are documented and accessible
- the repo now has a credible production launch package
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

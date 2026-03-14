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
3. Then review the current repository generally — secret and config handling, service-account boundaries, network policies, model lifecycle controls, admin security routes, current findings/acceptance scaffolding, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second security findings store, a second risk-acceptance system, or conflicting role-boundary enforcement.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for security findings, risk acceptance, secret rotation, model-boundary hardening, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that security hardening is real remediation and tracked closure, not just scans or dashboards.

## Objective
Close the last security mile with findings management, secret rotation, boundary hardening, and pen-test remediation.

This prompt owns:
- security findings intake/read surfaces
- risk acceptance lifecycle and append-only events
- secret rotation and lifecycle documentation/hooks
- least-privilege service account and network boundary hardening
- model-role boundary checks and drift/allowlist readiness
- security-sensitive UX review refinements for auth/export/audit areas
- admin and auditor security findings surfaces
- regression coverage for authz, model-boundary isolation, and risk-acceptance correctness

This prompt does not own:
- incident management
- release automation
- performance or recovery tooling
- a second security workflow
- public security reporting

## Phase alignment you must preserve
From Phase 11 Iteration 11.3:

### Required backend work
- dependency and container scanning
- secret rotation
- least-privilege service accounts
- network policy review
- approved-model lifecycle review covering ownership, checksums, allowlists, drift revalidation, and rollback readiness
- service-boundary review confirming each model role uses its own deployment unit, artefact path, and approval record

### Required tables
Implement or reconcile:
- `security_findings`
  - `id`
  - `status`
  - `severity`
  - `owner_user_id`
  - `source`
  - `opened_at`
  - `resolved_at`
  - `resolution_summary`
- `risk_acceptances`
  - `id`
  - `finding_id`
  - `status` (`ACTIVE | EXPIRED | REVOKED`)
  - `justification`
  - `approved_by`
  - `accepted_at`
  - `expires_at`
  - `review_date`
  - `revoked_by`
  - `revoked_at`
  - `created_at`
  - `updated_at`
- `risk_acceptance_events`
  - `id`
  - `risk_acceptance_id`
  - `event_type` (`ACCEPTANCE_CREATED | ACCEPTANCE_REVIEW_SCHEDULED | ACCEPTANCE_RENEWED | ACCEPTANCE_EXPIRED | ACCEPTANCE_REVOKED`)
  - `actor_user_id`
  - `expires_at`
  - `review_date`
  - `reason`
  - `created_at`

Rules:
- `risk_acceptances` are current projections derived from append-only `risk_acceptance_events`
- renew/review-schedule/expire/revoke append events rather than mutating silent history
- `ACCEPTANCE_EXPIRED` is system-generated when `expires_at` elapses via a scheduled expiry evaluator; no manual expire endpoint

### Required APIs
- `GET /admin/security/findings`
- `GET /admin/security/findings/{findingId}`
- `POST /admin/security/findings/{findingId}/risk-acceptance`
- `GET /admin/security/risk-acceptances?status={status}&findingId={findingId}`
- `GET /admin/security/risk-acceptances/{riskAcceptanceId}`
- `GET /admin/security/risk-acceptances/{riskAcceptanceId}/events`
- `POST /admin/security/risk-acceptances/{riskAcceptanceId}/renew`
- `POST /admin/security/risk-acceptances/{riskAcceptanceId}/review-schedule`
- `POST /admin/security/risk-acceptances/{riskAcceptanceId}/revoke`

### RBAC
- reads for findings and risk acceptances are `ADMIN` and read-only `AUDITOR`
- create/renew/review-schedule/revoke are backend-enforced `ADMIN` only

### Required web routes
- `/admin/security/findings`
- `/admin/security/findings/:findingId`
- `/admin/security/risk-acceptances`
- `/admin/security/risk-acceptances/:riskAcceptanceId`
- `/admin/security/risk-acceptances/:riskAcceptanceId/events`

### Required gates
- critical and high findings are resolved or explicitly risk-accepted
- pen-test prep checklist is complete
- authz regression suite passes
- model services cannot load unapproved artefacts or fetch runtime weights from public registries
- model roles cannot point at another role's artefact root or shared mutable cache
- risk acceptance requires justification, approver, and expiry or review date

### Required audit events
- `SECURITY_FINDINGS_VIEWED`
- `SECURITY_FINDING_VIEWED`
- `RISK_ACCEPTANCE_CREATED`
- `RISK_ACCEPTANCE_RENEWED`
- `RISK_ACCEPTANCE_REVIEW_SCHEDULED`
- `RISK_ACCEPTANCE_EXPIRED`
- `SECURITY_RISK_ACCEPTANCES_VIEWED`
- `SECURITY_RISK_ACCEPTANCE_VIEWED`
- `SECURITY_RISK_ACCEPTANCE_EVENTS_VIEWED`
- `RISK_ACCEPTANCE_REVOKED`

## Implementation scope

### 1. Canonical findings and risk-acceptance model
Implement or refine the security findings and risk-acceptance stores.

Requirements:
- one findings store
- append-only risk acceptance events
- current projections derived from event history
- no shadow approval or exception list elsewhere

### 2. Secret rotation and boundary hardening
Implement or refine the operational hardening pieces.

Requirements:
- explicit secret rotation hooks or procedures
- least-privilege service account boundaries encoded and documented
- network policy checks/reviews codified
- model-role isolation checks for artefact roots and deployment units
- no public weight fetch at runtime

### 3. Admin security surfaces
Implement or refine the security findings and acceptance UI.

Requirements:
- list/detail for findings
- list/detail/events for risk acceptances
- read-only auditor support
- admin-only create/renew/revoke actions
- calm, dense, internal UX

### 4. Authz and model-boundary regressions
Add or refine security coverage.

Requirements:
- authz regression suite for sensitive routes
- model role cannot target another role’s artefact root
- allowlist and checksum drift readiness checks
- no public registry fetch at runtime
- risk acceptance event sequence correctness

### 5. Pen-test remediation and runbooks
Document and expose the remediation state.

Requirements:
- pen-test prep checklist and remediation tracking remain visible to admins
- findings can be resolved or explicitly accepted
- accepted findings have expiry/review dates
- no forgotten silent risk exceptions

### 6. Documentation
Document:
- findings and risk-acceptance lifecycle
- secret rotation and boundary hardening expectations
- model-role boundary rules
- what later go-live prompts must treat as security prerequisites

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- security findings store
- risk acceptance events/projections
- admin APIs
- regression checks
- tests

### Web
- security findings list/detail
- risk acceptance list/detail/events
- read-only auditor support

### Docs
- security findings and risk-acceptance doc
- boundary hardening and secret-rotation doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**` only for scheduled risk-acceptance expiry evaluation hooks
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small findings/detail/timeline refinements are needed
- infra/config helpers for boundary checks
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- incidents
- release automation
- recovery tooling
- a second security workflow
- public security reporting

## Testing and validation
Before finishing:
1. Verify findings and risk acceptances are stored and read correctly.
2. Verify risk acceptance lifecycle uses append-only events.
3. Verify expiry transitions append `ACCEPTANCE_EXPIRED` via scheduled evaluation when `expires_at` elapses.
4. Verify admin-only create/renew/review-schedule/revoke and read-only auditor access.
5. Verify authz regression suite covers sensitive routes.
6. Verify model roles cannot point at another role’s artefact root or shared mutable cache.
7. Verify no runtime fetches from public registries are permitted.
8. Verify docs match the implemented security and risk-acceptance behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- security findings management is real
- risk acceptance is real and append-only
- secret/boundary hardening is real and test-backed
- pen-test remediation can be tracked to closure or explicit acceptance
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

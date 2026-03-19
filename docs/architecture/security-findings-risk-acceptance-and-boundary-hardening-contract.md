# Security Findings, Risk Acceptance, and Boundary Hardening Contract

This contract captures the Phase 11.3 implementation for security findings management, append-only risk acceptance lifecycle, and model/runtime boundary hardening.

## Scope

- `security_findings` and risk-acceptance lifecycle are first-class platform data, not ad hoc exceptions.
- risk-acceptance status is a projection derived from append-only `risk_acceptance_events`.
- secret-rotation, service-account, network-policy, and model-boundary checks are surfaced in the findings posture.
- expiry transitions are system-evaluated; there is no manual expire route.

## Data Model

Persisted tables:

- `security_findings`
  - `id`
  - `status` (`OPEN | IN_PROGRESS | RESOLVED`)
  - `severity` (`LOW | MEDIUM | HIGH | CRITICAL`)
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
- `risk_acceptance_events` (append-only)
  - `id`
  - `risk_acceptance_id`
  - `event_type` (`ACCEPTANCE_CREATED | ACCEPTANCE_REVIEW_SCHEDULED | ACCEPTANCE_RENEWED | ACCEPTANCE_EXPIRED | ACCEPTANCE_REVOKED`)
  - `actor_user_id`
  - `expires_at`
  - `review_date`
  - `reason`
  - `created_at`

Append-only enforcement is implemented via database triggers that reject `UPDATE` and `DELETE` on `risk_acceptance_events`.

## API Contract

Routes:

- `GET /admin/security/status`
- `GET /admin/security/findings`
- `GET /admin/security/findings/{findingId}`
- `POST /admin/security/findings/{findingId}/risk-acceptance`
- `GET /admin/security/risk-acceptances?status={status}&findingId={findingId}`
- `GET /admin/security/risk-acceptances/{riskAcceptanceId}`
- `GET /admin/security/risk-acceptances/{riskAcceptanceId}/events`
- `POST /admin/security/risk-acceptances/{riskAcceptanceId}/renew`
- `POST /admin/security/risk-acceptances/{riskAcceptanceId}/review-schedule`
- `POST /admin/security/risk-acceptances/{riskAcceptanceId}/revoke`

RBAC:

- Read surfaces are `ADMIN` and read-only `AUDITOR`.
- Mutations are `ADMIN` only.

Validation rules:

- risk acceptance requires `justification` and at least one of `expiresAt` or `reviewDate`.
- renew requires the same minimum fields and appends `ACCEPTANCE_RENEWED`.
- review scheduling appends `ACCEPTANCE_REVIEW_SCHEDULED`.
- revoke appends `ACCEPTANCE_REVOKED`.
- expiry appends `ACCEPTANCE_EXPIRED` from the system evaluator.

## Audit Events

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

## Pen-Test and Gate Posture

Findings posture includes:

- critical/high unresolved gate (`criticalHighGatePassed`)
- unresolved critical/high finding IDs
- pen-test checklist status and itemized details

Critical/high findings must be resolved or have active risk acceptance to pass the gate.

## Boundary Hardening Controls

### Model role isolation

`validate_model_stack` enforces:

- model-role to service isolation (no two roles sharing the same deployment unit entry)
- artifact-path isolation (roles cannot share or nest artifact roots)
- mutable/shared/cache artifact roots are rejected
- service base URLs and runtime model endpoints must remain internal allowlist targets
- public runtime fetch paths are rejected

### Service-account and network-policy checks

Security findings include checks for:

- least-privilege service-account templates and deployment bindings
- deny-by-default egress + internal allowlist network-policy template presence

### Secret rotation readiness

Security findings include checks for placeholder/default secret material in runtime configuration.

## Worker Expiry Evaluator

Worker runtime runs a risk-acceptance expiry pass on each loop iteration:

- due active acceptances append `ACCEPTANCE_EXPIRED`
- projected `risk_acceptances.status` becomes `EXPIRED`
- `RISK_ACCEPTANCE_EXPIRED` audit events are emitted with system actor context

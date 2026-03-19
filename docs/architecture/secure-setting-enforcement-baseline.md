# Secure-Setting Enforcement Baseline (Phase 0.5)

This document captures the implemented Phase 0.5 enforcement posture for no-egress, internal-only model execution, and hardened web/API defaults.

## Implemented Controls

- Deny-by-default outbound posture:
  - runtime outbound targets are validated through a central allowlist policy (`api/app/security/outbound.py`)
  - non-allowlisted domains hard-fail with typed errors and best-effort audit emission (`OUTBOUND_CALL_BLOCKED`)
- Internal-only model source enforcement:
  - `validate_model_stack` rejects service endpoints outside the outbound allowlist
  - `validate_model_stack` rejects artefact sources that use URL-style external pulls
  - model artefact paths must resolve inside `MODEL_ARTIFACT_ROOT` or `MODEL_DEPLOYMENT_ROOT` and must exist
- Startup security bootstrap:
  - startup model-stack validation runs before normal traffic handling
  - strict environments (`staging`/`prod` or `MODEL_STARTUP_VALIDATION_MODE=strict`) fail startup on invalid model posture
  - startup security status includes a deny-by-default egress self-test signal
- Web/API hardening:
  - CSP baseline (`Content-Security-Policy` or `...-Report-Only` mode)
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy`
  - minimal `Permissions-Policy`
  - in-memory rate limiting for `/auth/*` and protected API routes
- Admin security status:
  - API: `GET /admin/security/status` (`ADMIN` and read-only `AUDITOR`)
  - Web: `/admin/security`
  - includes egress deny test state, CSP mode, last backup timestamp, and diagnostic preference signals
- Security findings and risk acceptance:
  - APIs under `/admin/security/findings` and `/admin/security/risk-acceptances`
  - append-only risk-acceptance events with projection state (`ACTIVE | EXPIRED | REVOKED`)
  - system expiry evaluator appends `ACCEPTANCE_EXPIRED`
- Deployment boundary hardening:
  - dedicated API/worker service accounts with `automountServiceAccountToken: false`
  - deny-by-default and internal-allowlist network policy templates remain encoded in Helm

## Configuration Surface

Environment variables:

- `OUTBOUND_ALLOWLIST`
- `MODEL_STARTUP_VALIDATION_MODE`
- `SECURITY_CSP_MODE`
- `SECURITY_CSP_VALUE`
- `SECURITY_REFERRER_POLICY`
- `SECURITY_PERMISSIONS_POLICY`
- `SECURITY_LAST_BACKUP_AT`
- `AUTH_RATE_LIMIT_WINDOW_SECONDS`
- `AUTH_RATE_LIMIT_MAX_REQUESTS`
- `PROTECTED_RATE_LIMIT_WINDOW_SECONDS`
- `PROTECTED_RATE_LIMIT_MAX_REQUESTS`

See [`.env.example`](/Users/test/Code/UKDA/.env.example) for defaults.

## Required Audit Events

- `BASELINE_POLICY_SNAPSHOT_SEEDED`
- `PROJECT_BASELINE_POLICY_ATTACHED`
- `ADMIN_SECURITY_STATUS_VIEWED`
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

Additional security telemetry events emitted in this baseline:

- `OUTBOUND_CALL_BLOCKED`
- `EXPORT_STUB_ROUTE_ACCESSED`

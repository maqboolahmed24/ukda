# Production Launch Handover and Post-Launch Guardrails

This runbook is the operational handover source for launch day and the first 72 hours after go-live.

## Canonical Inputs

Use these evidence artifacts for ship/no-ship review:

- launch package (machine): `output/launch/latest/ship-no-ship-package.json`
- launch package (operator): `output/launch/latest/ship-no-ship-package.md`
- readiness matrix report: `output/readiness/latest/readiness-report.json`
- release smoke report: `output/smoke/latest/release-smoke-report.json`
- release gate report: `output/release-gates/latest/release-gate-report.json`
- launch operations catalog: `infra/readiness/launch-operations-catalog.v1.json`

## Operational Ownership

- launch day owner: `user-release-manager`
- on-call primary: `user-oncall-primary`
- on-call secondary: `user-oncall-secondary`
- model service map owner: `user-model-platform-owner`
- approved-model lifecycle owner: `user-model-governance-owner`
- rollback execution owner: `user-model-ops-owner`

## Escalation Path

1. `L1` on-call primary (`user-oncall-primary`), target response in 15 minutes.
2. `L2` on-call secondary (`user-oncall-secondary`), target response in 30 minutes.
3. `L3` platform and governance leadership (`user-release-manager`), target response in 45 minutes.

If escalation reaches `L3`, incident commander ownership must be explicit in the incident timeline.

## Ship/No-Ship Procedure

1. Run `make readiness-audit`.
2. Run `make smoke-release TARGET_ENV=prod`.
3. Run `make release-gate RELEASE_MODE=promote SOURCE_ENV=staging TARGET_ENV=prod`.
4. Run `make launch-package`.
5. Open `output/launch/latest/ship-no-ship-package.md` and review blockers.
6. If any blocker exists, decision is `NO_SHIP`. Do not promote.
7. If blocker count is zero, decision is `SHIP` and launch day owner can proceed.

## No-Go Criteria

All must remain clear before ship:

- `no-go-readiness-blockers`: readiness matrix and release gate have no blocking failures.
- `no-go-missing-rehearsals`: go-live rehearsal, incident tabletop, and model rollback rehearsal are all `COMPLETED`.
- `no-go-active-sev1-sev2`: no unresolved `SEV1` or `SEV2` incidents.

## Post-Launch Guardrails (T+0h to T+72h)

- `guardrail-ingest-through-export`
  - owner: `user-release-manager`
  - cadence: every 2 hours
  - trigger: critical-flow smoke failure
  - response: pause promotion and execute deployment rollback procedure
- `guardrail-security-and-egress`
  - owner: `user-security-owner`
  - cadence: every 4 hours
  - trigger: unresolved critical/high finding without active risk acceptance, or egress denial regression failure
  - response: block release approval and escalate to incident commander
- `guardrail-model-rollback`
  - owner: `user-model-ops-owner`
  - cadence: every 6 hours for first 24 hours
  - trigger: transcription primary model SLO breach with elevated fallback/error rate
  - response: execute approved-model rollback playbook and open incident timeline

## Rollback Trigger Points

Initiate rollback when any of the following occur:

- sustained SLO breach for ingestion, privacy review, or export review paths
- unresolved `SEV1` or `SEV2` incident tied to launch changes
- export no-bypass controls regress (`egress_controls` fails)
- critical/high security finding opens without approved active risk acceptance

Primary rollback references:

- deployment rollback: `docs/runbooks/deployment-runbook.md`
- backup and restore: `docs/runbooks/backup-restore-runbook.md`
- key rotation and compromise response: `docs/runbooks/key-rotation-runbook.md`
- provenance replay and verification recovery: `docs/runbooks/provenance-replay-drill-and-bundle-validation-recovery.md`

## Admin and Auditor Surfaces

- `ADMIN` runbook routes:
  - `/admin/runbooks`
  - `/admin/runbooks/:runbookId`
- `ADMIN` and read-only `AUDITOR` incident routes:
  - `/admin/incidents`
  - `/admin/incidents/status`
  - `/admin/incidents/:incidentId`
  - `/admin/incidents/:incidentId/timeline`

These routes are server-side RBAC enforced and audit logged.

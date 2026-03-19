# Production Launch Ship/No-Ship Review

This document defines the final evidence-backed launch decision flow for Prompt 100.

## Decision Artifact

Generate the canonical launch package:

```bash
make launch-package
```

This command writes:

- `output/launch/latest/ship-no-ship-package.json`
- `output/launch/latest/ship-no-ship-package.md`

`--strict` behavior is enforced by `make launch-package`; the command exits non-zero when blockers exist.

## Required Evidence Inputs

The launch package collates:

- SLO and operations readiness evidence from `output/readiness/latest/readiness-report.json`
- capacity and resilience category status from readiness categories
- security findings and no-bypass egress readiness from readiness categories
- release smoke evidence from `output/smoke/latest/release-smoke-report.json`
- release gate evidence from `output/release-gates/latest/release-gate-report.json`
- go-live rehearsal, incident tabletop, and model rollback rehearsal state from `infra/readiness/launch-operations-catalog.v1.json`

## Blocking Decision Rules

Decision is `NO_SHIP` when any blocker exists, including:

- readiness report missing, invalid, or not `PASS`
- readiness report has blocking failures
- smoke report missing, invalid, or not `PASS`
- release gate report missing, invalid, or not `PASS`
- launch catalog missing or invalid
- go-live rehearsal, incident tabletop, or model rollback rehearsal not `COMPLETED`
- required rehearsal completion timestamps missing
- security readiness category not `PASS`
- egress controls category not `PASS`

Decision is `SHIP` only when blocker count is zero.

## Operational Ownership and Handover

Launch ownership, escalation path, model ownership, no-go criteria, and post-launch guardrails are sourced from:

- `infra/readiness/launch-operations-catalog.v1.json`
- `docs/runbooks/production-launch-handover-and-post-launch-guardrails.md`

## Admin Review Surfaces

Use these routes during final launch review:

- runbooks (admin only): `/admin/runbooks`, `/admin/runbooks/:runbookId`
- incidents (admin and read-only auditor): `/admin/incidents`
- incident status summary: `/admin/incidents/status`
- incident detail and timeline: `/admin/incidents/:incidentId`, `/admin/incidents/:incidentId/timeline`

Expected audit events:

- `RUNBOOK_LIST_VIEWED`
- `RUNBOOK_DETAIL_VIEWED`
- `INCIDENT_LIST_VIEWED`
- `INCIDENT_STATUS_VIEWED`
- `INCIDENT_VIEWED`
- `INCIDENT_TIMELINE_VIEWED`

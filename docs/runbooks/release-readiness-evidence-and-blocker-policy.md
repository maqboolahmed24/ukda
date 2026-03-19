# Release Readiness Evidence and Blocker Policy

This runbook defines how release decisions consume cross-phase readiness evidence.

## Evidence Source

Canonical readiness evidence:

- matrix definition: `infra/readiness/cross-phase-readiness-matrix.json`
- generated report: `output/readiness/latest/readiness-report.json`
- per-check logs: `output/readiness/latest/logs/*.log`
- release gate aggregate: `output/release-gates/latest/release-gate-report.json`
- release smoke report: `output/smoke/latest/release-smoke-report.json`
- non-prod seed report: `output/seeds/latest/nonprod-seed-refresh-report.json`

Do not use ad hoc spreadsheets or manual-only checklists as release truth.

## Blocking Rules

Treat release as blocked when any are true:

1. `overallStatus` is `FAIL`.
2. `blockingFailureCount` is greater than `0`.
3. Any blocking category (`accessibility`, `governance_integrity`, `privacy_safety`, `provenance_verification`, `egress_controls`, `discovery_safety`, `security_hardening`) has `status=FAIL`.

`resilience_capacity` is warning-level in v1 and must still be reviewed in launch notes.

## Review Workflow

1. Run `make readiness-audit`.
2. Run `make smoke-release TARGET_ENV=<target>`.
3. Run `make release-gate RELEASE_MODE=promote SOURCE_ENV=<source> TARGET_ENV=<target>`.
4. Confirm report timestamp and matrix version are current.
5. Inspect `blockers[]` and each referenced log path.
6. Record explicit disposition for warning-level failures.
7. Do not approve release automation or launch review when blockers remain open.

## Auditor and Admin Visibility

- `ADMIN` sees full readiness detail and admin-only categories.
- `AUDITOR` sees safe category slices and evidence references via `/admin/operations/readiness`.
- Raw privacy-disclosure artefacts are not exposed through readiness summary payloads.

## Prompt 99 and Prompt 100 Consumption

Prompt 99 (release automation):

- must fail fast when readiness has blocking failures.
- must carry `matrixVersion`, `overallStatus`, and `blockingFailureCount` into release logs.

Prompt 100 (launch review):

- must require a fresh readiness report.
- must include blocker closure evidence paths in ship/no-ship notes.
- must run `make launch-package` to produce the final launch decision artifact.

## Launch Review References

- launch decision flow: `docs/delivery/production-launch-ship-no-ship-review.md`
- operational handover and post-launch guardrails:
  `docs/runbooks/production-launch-handover-and-post-launch-guardrails.md`

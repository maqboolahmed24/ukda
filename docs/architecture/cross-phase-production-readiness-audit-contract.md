# Cross-Phase Production Readiness Audit Contract

This contract defines the canonical machine-readable readiness audit for Phase 11.4 release posture.

## Canonical Matrix

- Matrix source: [`/infra/readiness/cross-phase-readiness-matrix.json`](../../infra/readiness/cross-phase-readiness-matrix.json)
- Execution runner: [`/scripts/run_readiness_audit.py`](../../scripts/run_readiness_audit.py)
- Deterministic report output: `output/readiness/latest/readiness-report.json`
- Deterministic per-check logs: `output/readiness/latest/logs/*.log`

The matrix is the single source of truth for cross-phase readiness categories and check commands.

## Required Categories

- `accessibility`
- `governance_integrity`
- `privacy_safety`
- `provenance_verification`
- `egress_controls`
- `discovery_safety`
- `security_hardening` (admin-only surface)
- `resilience_capacity` (warning-level, admin-only surface)

## Status and Blocking Policy

- Check statuses: `PASS | FAIL | UNAVAILABLE`
- Category statuses: `PASS | FAIL | UNAVAILABLE`
- Blocking policies: `BLOCKING | WARNING`
- Overall status:
  - `FAIL` when any `BLOCKING` check fails
  - `PASS` when all blocking checks pass
  - `UNAVAILABLE` when no coherent report is present

Blocking failures are emitted under `blockers[]` with evidence references.

## Admin and Auditor Read Surfaces

API route:

- `GET /admin/operations/readiness`

RBAC:

- `ADMIN`: full category/check payload with command and exit metadata.
- `AUDITOR`: safe slice only (`accessibility`, `governance_integrity`, `privacy_safety`, `provenance_verification`, `egress_controls`, `discovery_safety`) with command fields redacted and no admin-only categories.

UI route:

- `/admin/operations/readiness`

This page is read-only for `ADMIN` and `AUDITOR` and renders matrix status, blockers, and evidence references.

## CI Gate Integration

CI executes the matrix via:

- `make readiness-audit PYTHON=python`

Workflow job:

- `CI / readiness-audit`

Artifacts:

- `readiness-audit-artifact` (contains report + logs from `output/readiness/latest`)

## Release Dependents

Prompt 99 and Prompt 100 consume this readiness report as release input:

- no promotion when `overallStatus == FAIL`
- no promotion when `blockingFailureCount > 0`
- release review must include blocker details and evidence paths
- release gate aggregation should persist machine-readable output in `output/release-gates/latest/release-gate-report.json`

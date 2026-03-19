# Release Automation And Promotion Gates

This document defines the canonical release automation path for Phase 11.4 go-live readiness.

## Single Promotion Pipeline

Use one workflow only:

- [`/.github/workflows/deploy-environments.yml`](../../.github/workflows/deploy-environments.yml)

Modes:

- `promote`
- `rollback`

The workflow is intentionally the only environment-promotion path. Direct ad hoc production deploys are out of policy.

## Deployment Profiles

Environment profiles are explicit and isolated:

- [`/infra/helm/ukde/values-dev.yaml`](../../infra/helm/ukde/values-dev.yaml)
- [`/infra/helm/ukde/values-staging.yaml`](../../infra/helm/ukde/values-staging.yaml)
- [`/infra/helm/ukde/values-prod.yaml`](../../infra/helm/ukde/values-prod.yaml)

Profile rules:

- each profile must declare its own `global.environment`
- no inline secret material in profile files
- `staging` and `prod` keep deny-by-default egress policy enabled
- production egress stays export-gateway-only by contract

## Promotion Gate Order

Before deploy or rollback execution, `promotion-gates` runs:

1. cross-phase readiness audit (`make readiness-audit`)
2. release smoke suite (`make smoke-release TARGET_ENV=<target>`)
3. non-prod seed validation for `dev`/`staging` targets
4. release gate aggregation (`scripts/run_release_gate.py --strict`)

Gate reports:

- `output/release-gates/latest/release-gate-report.json`
- `output/release-gates/latest/promotion-intent.json`

Promotion path policy:

- allowed: `dev -> staging`
- allowed: `staging -> prod`
- blocked: all other promote transitions

## Rollback-Aware Behavior

Rollback runs through the same workflow using `mode=rollback`.

Requirements:

- `rollback_revision` must be explicit
- release gates execute before rollback
- optional post-rollback endpoint smoke can run when environment variables are configured

Rollback records:

- `output/release-gates/latest/rollback-record.json`

Promotion records:

- `output/release-gates/latest/deployment-record.json`

## Prompt 100 Inputs

Prompt 100 ship/no-ship review should consume:

- `output/release-gates/latest/release-gate-report.json`
- `output/readiness/latest/readiness-report.json`
- `output/smoke/latest/release-smoke-report.json`
- promotion/rollback record artifacts from the deploy workflow

Blocking decision rules:

- no ship if release gate `overallStatus != PASS`
- no ship if readiness `overallStatus != PASS`
- no ship if readiness `blockingFailureCount > 0`

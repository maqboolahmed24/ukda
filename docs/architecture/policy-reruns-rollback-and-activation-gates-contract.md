# Policy Reruns, Rollback, And Activation Gates Contract

## Scope

Phase 7 Prompt 76 extends policy lifecycle safety with:

- canonical policy reruns from approved/governance-ready source runs
- compare-only draft rerun candidates
- non-destructive rollback draft creation
- deterministic pre-activation warning surfaces for risky policy rules

## Canonical Rerun API

- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/rerun?policyId={policyId}`

Rules:

- rerun request access is `PROJECT_LEAD` or `ADMIN`
- source run must be `SUCCEEDED`
- source run review must be `APPROVED`
- source run governance readiness must be `READY`
- target policy must:
  - belong to the same project
  - be `ACTIVE` or `DRAFT`
  - have `validation_status = VALID`
  - have `validated_rules_sha256` matching current `rules_json`
- rerun lineage is append-only:
  - new run uses `run_kind = POLICY_RERUN`
  - new run sets `supersedes_redaction_run_id = source_run_id`
  - source run remains immutable
- policy rerun run records pin explicit policy lineage fields:
  - `policy_id`
  - `policy_family_id`
  - `policy_version`

## Compare Contract

- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`

Read access:

- `PROJECT_LEAD`
- `REVIEWER`
- `ADMIN`
- read-only `AUDITOR`

Compare response includes:

- changed-pages summary and page-level deltas
- policy version context from `baseRun` and `candidateRun`
- `comparisonOnlyCandidate` and `candidatePolicyStatus`
- typed pre-activation warnings:
  - `BROAD_ALLOW_RULE`
  - `INCONSISTENT_THRESHOLD`

## Comparison-Only Draft Reruns

When the rerun target policy is a validated `DRAFT` revision:

- rerun output is comparison-only
- policy activation is not implied
- `project_policy_projections.active_policy_id` is unchanged
- compare UI must label this state explicitly

## Safe Rollback API

- `POST /projects/{projectId}/policies/{policyId}/rollback-draft?fromPolicyId={fromPolicyId}`

Semantics:

- `{policyId}` anchors the lineage context
- `fromPolicyId` names the prior validated revision used as rollback seed
- rollback never mutates historical rows in place
- rollback creates a new `DRAFT` revision in the same family
- rollback source gates:
  - same project and same `policy_family_id`
  - prior version (`from.version < anchor.version`)
  - `validation_status = VALID`
  - validated hash parity with current `rules_json`

The resulting rollback draft must still pass normal validate/compare/activate flow.

## Audit Events

- `POLICY_RERUN_REQUESTED`
- `POLICY_RUN_COMPARE_VIEWED`

`REDACTION_COMPARE_VIEWED` remains historical but is not the canonical Prompt 76 compare audit for policy-rerun analysis.

## Regression/Activation Expectations

Prompt 76 adds deterministic warning hooks and compare semantics used by regression checks:

- broad-allow rule detection
- inconsistent-threshold detection
- compare vs rerun lineage checks

Prompt 77 deepens:

- policy lineage approvals
- governance event modeling around policy decisions
- explainability and operator-facing rationale surfaces

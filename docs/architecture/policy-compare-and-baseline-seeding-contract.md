# Policy Compare And Baseline Seeding Contract

## Scope

This contract defines deterministic policy compare behavior for Phase 7 Prompt 72.

Routes:

- `GET /projects/{projectId}/policies/{policyId}/compare?against={otherPolicyId}`
- `GET /projects/{projectId}/policies/{policyId}/compare?againstBaselineSnapshotId={baselineSnapshotId}`

## Target Selection Rule

Exactly one compare target is allowed per request:

- `against`
- or `againstBaselineSnapshotId`

Requests with both or neither are rejected.

UI link builders must emit one target query only.

## Allowed Compare Pairings

### Revision vs revision

Allowed only when both are true:

- same `project_id`
- same `policy_family_id`

Cross-project and cross-family compare requests are rejected.

### Revision vs baseline snapshot

Allowed only when both are true:

- requested `againstBaselineSnapshotId` exists
- source revision lineage was seeded from that exact baseline snapshot (`seeded_from_baseline_snapshot_id` equality)

Baseline compare is blocked for mismatched lineage origins.

## Deterministic Diff Contract

Compare response is stable and typed:

- source policy metadata
- target kind (`POLICY` or `BASELINE_SNAPSHOT`)
- source/target rule hashes
- ordered list of rule-path differences (`path`, `before`, `after`)
- `differenceCount`

Diff output is path-deterministic for the same source and target inputs.

## Baseline Seeding Rules

- The first explicit Phase 7 policy lineage may seed from the project's attached baseline snapshot.
- New revisions in the lineage preserve that seeded origin.
- Seed origin is lineage metadata, not mutable workflow state.

## Audit + Timeline Expectations

- compare route access is audited (`POLICY_COMPARE_VIEWED`)
- policy lifecycle history remains append-only in `policy_events`
- compare output does not replace policy event timeline; it complements it

## Follow-on Work

Prompt 73 to Prompt 76 build on this compare contract:

- pseudonym lineage and reversible evidence scope
- generalisation transform policy depth
- policy authoring UX
- rerun/rollback/regression orchestration

# Policy Lineage, Usage, And Explainability Contract

## Scope

Phase 7 Prompt 77 defines canonical read surfaces for policy lineage, immutable rule snapshots, policy usage lineage, and bounded explainability.

This contract extends Prompt 72 to Prompt 76 without introducing a second history system.

## Canonical Read APIs

- `GET /projects/{projectId}/policies/{policyId}/lineage`
- `GET /projects/{projectId}/policies/{policyId}/usage`
- `GET /projects/{projectId}/policies/{policyId}/explainability`
- `GET /projects/{projectId}/policies/{policyId}/snapshots/{rulesSha256}`

Read access for all four routes:

- `PROJECT_LEAD`
- `REVIEWER`
- `ADMIN`
- read-only `AUDITOR`

`RESEARCHER` does not have Phase 7 policy read access.

## Lineage Source Of Truth

Lineage is reconstructed from:

- canonical policy rows in `redaction_policies`
- append-only `policy_events`
- active pointer in `project_policy_projections`

No mutable draft state is treated as historical truth.

Lineage response includes:

- baseline seed origin (`seeded_from_baseline_snapshot_id`)
- supersedes and superseded-by links
- active-vs-viewed status (`active_policy_differs`)
- validation/activation/retirement event subsets

## Immutable Rule Snapshots

Each policy lifecycle event persists:

- `rules_sha256`
- `rules_snapshot_key`
- immutable `rules_json` snapshot payload

Snapshots are append-only and queryable by `rulesSha256` under a policy revision.

This enables:

- precise historical inspection of rule content at lifecycle time
- deterministic traceability between policy event hash and rule bytes
- snapshot retrieval without relying on mutable draft content

## Usage Lineage

Policy usage response links one policy revision to:

- document reruns (`redaction_runs` with `policy_id`)
- governance artefacts generated from those runs (`redaction_manifests`, `redaction_evidence_ledgers`, readiness projection fields)
- pseudonym registry usage summary (`pseudonym_registry_entries` by policy scope)

Usage data is read-only and does not mutate policy, run, or governance state.

## Explainability Boundaries

Explainability response exposes deterministic, reviewer-visible fields:

- category actions
- confidence thresholds
- reviewer requirements
- escalation flags
- pseudonymisation and generalisation settings
- reviewer explanation mode
- deterministic sample traces and rationales derived from explicit rules

Explainability does not expose hidden reasoning or chain-of-thought.
Local LLM explanation mode remains secondary metadata under rule-authoritative policy control.

## Audit Events

Prompt 77 canonical read events:

- `POLICY_LINEAGE_VIEWED`
- `POLICY_USAGE_VIEWED`
- `POLICY_EXPLAINABILITY_VIEWED`
- `POLICY_SNAPSHOT_VIEWED`

These events are append-only audit records and follow metadata allowlists.

## Downstream Consumption

Later phases consume these surfaces directly:

- Phase 8 export review can reference policy snapshot hashes and usage lineage without reconstructing history from mutable rows.
- Phase 9 provenance can pin lifecycle snapshot hashes and usage IDs into proof bundles.
- Phase 10 governed data products can resolve active and historical policy context from canonical lineage/snapshot APIs.

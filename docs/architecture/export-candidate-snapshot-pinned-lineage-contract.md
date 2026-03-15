# Export Candidate Snapshot Pinned Lineage Contract

Status: Prompt 67 scaffolding + Prompt 71 integrity checks + Prompt 78 requester-side activation  
Scope: Phase 8 candidate snapshot schema contract and requester-side eligible candidate reads

## Purpose

`export_candidate_snapshots` freezes immutable downstream candidate inputs so Phase 8 export review never depends on mutable live projections.

Prompt 78 enables requester-side candidate reads and deterministic Phase 6 candidate synchronization into this canonical table.

## Canonical fields

Pinned source lineage:

- `project_id`
- `source_phase` (`PHASE6 | PHASE7 | PHASE9 | PHASE10`)
- `source_artifact_kind` (`REDACTION_RUN_OUTPUT | DEPOSIT_BUNDLE | DERIVATIVE_SNAPSHOT`)
- `source_run_id` (nullable for non-run artefacts)
- `source_artifact_id`

Pinned governance lineage:

- `governance_run_id`
- `governance_manifest_id`
- `governance_ledger_id`
- `governance_manifest_sha256`
- `governance_ledger_sha256`

Policy lineage:

- `policy_snapshot_hash`
- `policy_id`
- `policy_family_id`
- `policy_version`

Candidate identity and immutability:

- `candidate_kind`
- `artefact_manifest_json`
- `candidate_sha256`
- `eligibility_status` (`ELIGIBLE | SUPERSEDED`)
- `supersedes_candidate_snapshot_id`
- `superseded_by_candidate_snapshot_id`
- `created_by`
- `created_at`

## Pinned-lineage rules

1. Candidate snapshots are append-only immutable rows.
2. `source_artifact_kind` disambiguates `source_artifact_id`; consumers must not infer table meaning from candidate kind alone.
3. Phase 6 candidates pin `source_artifact_kind = REDACTION_RUN_OUTPUT`.
4. Governance lineage is frozen at candidate creation time and must not be replaced by later live governance projection changes.
5. Supersession is explicit through `supersedes_*` and `superseded_by_*` pointers.

## Typed contracts

Shared contract definitions are exposed in `packages/contracts/src/index.ts`:

- `ExportCandidateSourcePhase`
- `ExportCandidateSourceArtifactKind`
- `ExportCandidateKind`
- `ExportCandidateEligibilityStatus`
- `ExportCandidateSnapshotContract`
- `ExportCandidateSnapshotContractsResponse`

## Out of scope in this contract

- Reviewer dashboard and decision mutation workflow
- Receipt attachment and no-bypass infrastructure controls

Those remain for later Phase 8 prompts while reusing this schema without churn.

## Integrity validation

Prompt 71 adds deterministic validation coverage for pinned-lineage assumptions:

- `api/app/documents/governance_integrity.py`
  - `validate_candidate_snapshot_handoff(...)`
  - `validate_provenance_handoff(...)`
- `api/tests/test_governance_integrity.py`

Failure artifacts are emitted to:

- `api/tests/.artifacts/governance-integrity/last-evaluation.json`

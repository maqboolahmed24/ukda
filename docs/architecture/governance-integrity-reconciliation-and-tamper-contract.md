# Governance Integrity Reconciliation And Tamper Contract

Status: Prompt 71  
Scope: Deterministic reconciliation and tamper-evidence checks between approved Phase 5 decisions, Phase 6 manifest/ledger artefacts, and readiness behavior under replacement attempts.

## Objectives

- prove every manifest entry and controlled ledger row can be reconciled to an approved decision lineage
- fail closed when manifest bytes or ledger rows are tampered
- preserve active `READY` pointers until replacement artefacts are both successful and verified `VALID`
- emit machine-readable integrity evidence for CI and triage

## Canonical harness

Implemented module:

- `api/app/documents/governance_integrity.py`

Primary checks:

- `manifest_hash`: stream hash must equal pinned manifest hash
- `manifest_reconciliation`: approved decision set must map 1:1 to manifest entries
- `ledger_reconciliation`: canonical ledger rows must match approved decision lineage and hash-chain verification
- `candidate_snapshot_handoff`: pinned governance lineage must be present for Phase 8 handoff
- `provenance_handoff`: pinned lineage fields must be sufficient for Phase 9 deterministic consumers

Artifact writer:

- `write_governance_integrity_artifact(...)`

Artifact output path:

- `api/tests/.artifacts/governance-integrity/last-evaluation.json`

## Readiness pointer promotion rule

`governance_readiness_projections` pointer updates follow:

1. Keep existing `manifest_id` and `ledger_id` when replacement attempts are still unverified.
2. Promote to replacement pointers only after a successful verification run with `verification_result = VALID` that targets the replacement ledger hash.
3. Failed/invalid/canceled replacement verification attempts do not collapse a previously valid ready pair.

This logic is implemented in:

- `resolve_governance_ready_pair_from_attempts(...)` in `api/app/documents/governance.py`
- consumed by store projection sync during `_sync_governance_scaffold(...)`

## CI and regression entrypoints

- `make test-governance-integrity`
- `make ci-python` (includes governance-integrity checks before broad pytest sweep)

CI failure artifact upload includes:

- `api/tests/.artifacts/governance-integrity`

## Regression coverage

`api/tests/test_governance_integrity.py` covers:

- canonical pass path for manifest and ledger reconciliation
- manifest hash mismatch and manifest entry mismatch detection
- ledger tamper detection via hash-chain invalidation
- ready-pointer preservation during unverified replacement attempts
- ready-pointer promotion only after replacement verification becomes `VALID`
- resilience against invalid replacement verification
- candidate/provenance pinned-lineage field validation failures

# Downstream Governance Handoff Integrity Contract

Status: Prompt 71  
Scope: Phase 6 to Phase 8/9 lineage guarantees for immutable candidate snapshots and provenance consumers.

## Required pinned lineage

For Phase 6-backed candidate snapshots, downstream consumers must read pinned fields and never infer from mutable live projections:

- `sourceArtifactKind = REDACTION_RUN_OUTPUT`
- `governanceRunId`
- `governanceManifestId`
- `governanceLedgerId`
- `governanceManifestSha256`
- `governanceLedgerSha256`

These fields are required for:

- Phase 8 release-pack creation from immutable candidate snapshots
- Phase 9 proof/bundle builders that require deterministic governance lineage

## Stability guarantees

- candidate lineage records are immutable once frozen
- later governance replacements must not rewrite previously pinned candidate lineage
- provenance consumers rely on pinned IDs and hashes, not `governance_readiness_projections` lookups at read time

## Verification surface

Integrity checks are enforced in:

- `api/app/documents/governance_integrity.py`

Relevant checks:

- `candidate_snapshot_handoff`
- `provenance_handoff`

Regression coverage:

- `api/tests/test_governance_integrity.py`

## Consumer rule for Phase 9

Proof/bundle inputs should fail fast when any required pinned governance field is absent or empty.

Allowed policy-lineage basis:

- either `policySnapshotHash`
- or explicit policy tuple `policyId`, `policyFamilyId`, `policyVersion`

No ad hoc fallback to mutable live route state is allowed.

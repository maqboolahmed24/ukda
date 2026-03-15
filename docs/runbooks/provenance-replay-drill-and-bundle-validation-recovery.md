# Runbook: Provenance Replay Drill and Bundle Validation Recovery

## Purpose

Run deterministic replay checks for a deposit bundle, classify failures quickly, and recover without mutating historical lineage.

## Preconditions

- export request status is `APPROVED` or `EXPORTED`
- target bundle status is `SUCCEEDED`
- operator is `ADMIN` for mutation actions
- profile id is known when running profile validation

## Replay Drill Procedure

1. Identify bundle lineage:
   - `projectId`, `exportRequestId`, `bundleId`
   - confirm pinned `candidateSnapshotId` and `provenanceProofId` on bundle detail
2. Run replay CLI:
   - `ukde-provenance-replay <projectId> <exportRequestId> <bundleId> --profile <profileId>`
3. Confirm drill output:
   - `drillStatus`
   - per-step `status`
   - per-step `failureClass`
4. Compare replay output to API-visible run evidence:
   - verification runs: `/verification-runs`
   - validation runs: `/validation-runs?profile=...`
   - timeline evidence: `/events`

## Recovery Actions by Failure Class

- `MISSING_ARTEFACT`:
  - verify bundle archive entries exist and storage object is intact
  - rebuild bundle lineage attempt if artefact is incomplete
- `TAMPERED_PROOF`:
  - treat as integrity incident
  - regenerate provenance proof, rebuild bundle, rerun verification/validation
- `INVALID_BUNDLE_CONTENTS`:
  - inspect metadata/proof mismatches
  - rebuild from approved snapshot and re-run validation
- `PROFILE_MISMATCH`:
  - select correct profile for bundle kind
  - rerun `validate-profile` with intended profile
- `ENVIRONMENTAL_RUNTIME`:
  - inspect storage/database/runtime health
  - re-run replay after infrastructure recovery

## API Recovery Flow

1. Start verification replay attempt (`ADMIN`):
   - `POST .../bundles/{bundleId}/verify`
2. Start profile validation replay attempt (`ADMIN`):
   - `POST .../bundles/{bundleId}/validate-profile?profile={profileId}`
3. Monitor:
   - verification: `/verification/status`
   - validation: `/validation-status?profile={profileId}`
4. If in-flight run must stop:
   - cancel verification run: `POST .../verification/{verificationRunId}/cancel`
   - cancel validation run: `POST .../validation-runs/{validationRunId}/cancel`

## Invariants

- do not mutate old attempts; append new ones
- do not downgrade prior successful verification/validation truth on failed retries
- use bundle events as canonical combined history feed

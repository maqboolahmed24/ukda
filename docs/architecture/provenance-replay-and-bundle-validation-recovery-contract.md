# Provenance Replay and Bundle Validation Recovery Contract

Scope: Phase 9 replay drills, deposit-profile validation, and deterministic failure recovery semantics.

## Canonical Replay Path

Replay uses one verification and validation stack:

- verification engine: `api/app/exports/verification.py`
- profile validation engine: `api/app/exports/deposit_profiles.py`
- replay orchestration: `api/app/exports/replay.py`
- replay CLI: `ukde-provenance-replay`

Replay is deterministic once bundle bytes and pinned lineage references are resolved.
No external key fetches or mutable live lineage lookups are required during verification.

## Data Contracts

`bundle_validation_runs` is append-only per `(bundle_id, profile_id)` lineage:

- `attempt_number` increments per profile lineage
- `supersedes_validation_run_id` and `superseded_by_validation_run_id` link attempts
- every run stores immutable `profile_snapshot_key` and `profile_snapshot_sha256`

`bundle_validation_projections` is read truth per `(bundle_id, profile_id)`:

- `PENDING`: no non-canceled outcome exists yet
- `FAILED`: latest non-canceled outcome failed and no successful outcome exists yet
- `READY`: a successful non-canceled outcome exists and verification projection is `VERIFIED`

Failure or cancel retries do not erase prior successful readiness truth.

## API Surface

- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundle-profiles`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validate-profile?profile={profileId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-status?profile={profileId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-runs?profile={profileId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-runs/{validationRunId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-runs/{validationRunId}/status`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-runs/{validationRunId}/cancel`

Validation start/cancel is `ADMIN` only. Validation reads follow bundle-kind read boundaries.

## Failure Evidence Model

Replay and validation evidence emits deterministic failure classes:

- `MISSING_ARTEFACT`
- `TAMPERED_PROOF`
- `INVALID_BUNDLE_CONTENTS`
- `PROFILE_MISMATCH`
- `ENVIRONMENTAL_RUNTIME`

These classes are present in verification/validation payloads and replay drill output.

## Recovery Guarantees

- verification failures never erase prior `VERIFIED` projection truth
- validation failures never erase prior `READY` projection truth
- canceled runs remain visible and append-only
- terminal runs cannot be canceled
- retries append new attempts; historical attempts remain immutable

## Downstream Assumptions

Later archive and deposit workflows may assume:

- replay can re-verify pinned bundle/proof lineage deterministically
- profile validation history is reproducible via pinned profile snapshots
- readiness truth is stable across failed replacement attempts

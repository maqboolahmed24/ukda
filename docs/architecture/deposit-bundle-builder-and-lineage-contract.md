# Deposit Bundle Builder And Lineage Contract

Scope: Phase 9 iteration 9.1 deposit-ready bundle builders for approved export requests.

## Canonical Bundle Kinds

- `SAFEGUARDED_DEPOSIT`
- `CONTROLLED_EVIDENCE`

Both are internal governed artefacts. They do not expose raw object-store URLs and do not create a second egress path outside Phase 8.

## Persistence Model

`deposit_bundles` is the single authoritative bundle-attempt store:

- append-only attempt lineage
- `attempt_number` monotonic per `(export_request_id, candidate_snapshot_id, bundle_kind)`
- `supersedes_bundle_id` and `superseded_by_bundle_id` forward/backward links
- one current unsuperseded lineage head per tuple
- idempotent create returns current unsuperseded attempt for the tuple
- explicit rebuild appends the next attempt and supersedes the prior head
- cancel allowed only for `QUEUED` or `RUNNING`; terminal attempts are rejected

`bundle_verification_projections` is created per bundle attempt with initial `PENDING` state for later Prompt 86 verification workflows.

`bundle_events` is append-only and is the single timeline feed for bundle lifecycle, verification, and validation activity.

## Build Contract

Bundle creation is allowed only when the linked export request lineage is `APPROVED` or `EXPORTED`, and it freezes:

- `candidate_snapshot_id`
- current unsuperseded `provenance_proof_id`
- `provenance_proof_artifact_sha256`

Deterministic archive contents:

- `bundle/metadata.json`
- `bundle/provenance-proof.json`
- `bundle/provenance-signature.json`
- `bundle/provenance-verification-material.json`

Archive bytes are deterministic (fixed zip entry timestamps/permissions and canonical JSON payloads), then pinned by `bundle_sha256`.

## Included Metadata

`metadata.json` includes:

- transcript/derivative references from candidate manifest
- manifest and governance lineage references
- tool/policy lineage references
- linked `export_request_id`, review decision metadata, and request revision
- approved `candidate_snapshot_id`
- pinned provenance proof linkage (`proofId`, root/hash material)
- optional receipt metadata when export receipt already exists

Proof verification material is carried from the signed provenance artifact so offline verification can be executed later without live lineage lookups.

## RBAC

- Build `SAFEGUARDED_DEPOSIT`: `PROJECT_LEAD`, `REVIEWER`, `ADMIN`
- Build/Rebuild/Cancel `CONTROLLED_EVIDENCE`: `ADMIN` only
- Read `CONTROLLED_EVIDENCE`: `ADMIN` and read-only `AUDITOR` only
- Read `SAFEGUARDED_DEPOSIT`: follows export request read permissions
- `RESEARCHER` never reads controlled-evidence bundles

## APIs

- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles?kind={bundleKind}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/status`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/events`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/cancel`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/rebuild`

## Prompt 86 Handoff

Prompt 86 implementation details now live in:

- `docs/architecture/bundle-verification-tooling-and-proof-viewer-contract.md`

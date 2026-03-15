# Bundle Verification Tooling And Proof Viewer Contract

Scope: Phase 9 iteration 9.2 bundle verification runs, append-only lineage, and auditor-grade proof viewing.

## Verification Tooling

Bundle verification is implemented through one canonical verifier:

- shared verifier: `api/app/exports/verification.py`
- CLI wrapper: `python -m app.exports.bundle_verify_cli <bundle.zip> [--expected-sha256 ...]`
- server-side run execution: `ExportStore.create_bundle_verification_run(...)`

Both paths use the same archive-check logic:

- require canonical bundle entries:
  - `bundle/metadata.json`
  - `bundle/provenance-proof.json`
  - `bundle/provenance-signature.json`
  - `bundle/provenance-verification-material.json`
- verify merkle reconstruction and leaf-hash consistency from bundled proof leaves
- verify root signature from bundled verification material only
- enforce internal consistency between metadata proof pointers and proof artifact hashes
- never call live lineage DB lookups or external key fetches during verification

## Persistence Model

`bundle_verification_runs` is append-only verification lineage:

- `attempt_number` monotonic per `bundle_id`
- `supersedes_verification_run_id` / `superseded_by_verification_run_id` link attempts
- terminal statuses: `SUCCEEDED`, `FAILED`, `CANCELED`
- cancel allowed only for `QUEUED` or `RUNNING`

`bundle_verification_projections` remains bundle-level read truth:

- projection tracks the last known good successful verification
- failed attempts only replace projection status when no successful projection is currently pinned
- canceled attempts do not replace successful verification truth

## Verification APIs

- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verify`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/status`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification-runs`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/{verificationRunId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/{verificationRunId}/status`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/{verificationRunId}/cancel`

## RBAC

- verification start: `ADMIN` only
- verification cancel: `ADMIN` only
- read verification for `SAFEGUARDED_DEPOSIT`: same read boundary as request/bundle
- read verification for `CONTROLLED_EVIDENCE`: `ADMIN` and read-only `AUDITOR` only

## Proof Viewer Surface

Route:

- `/projects/:projectId/export-requests/:exportRequestId/bundles/:bundleId/verification`

The viewer presents:

- bundle verification projection and latest attempt status
- root hash and signature status
- bundled verification material summary
- append-only verification attempt history
- selected attempt pass/fail detail and machine-readable failure reasons

No raw object-store URLs are exposed.

## Audit Events

Verification routes emit:

- `BUNDLE_VERIFICATION_RUN_CREATED`
- `BUNDLE_VERIFICATION_RUN_STARTED`
- `BUNDLE_VERIFICATION_RUN_FINISHED`
- `BUNDLE_VERIFICATION_RUN_FAILED`
- `BUNDLE_VERIFICATION_RUN_CANCELED`
- `BUNDLE_VERIFICATION_VIEWED`
- `BUNDLE_VERIFICATION_STATUS_VIEWED`

## Prompt 87 Outcome

Prompt 87 extends this contract with:

- deposit-profile validation runs and projections
- deterministic replay drill tooling and failure-class evidence
- recovery semantics preserving last-known-good verification and validation truth

See:

- `docs/architecture/provenance-replay-and-bundle-validation-recovery-contract.md`
- `docs/runbooks/provenance-replay-drill-and-bundle-validation-recovery.md`

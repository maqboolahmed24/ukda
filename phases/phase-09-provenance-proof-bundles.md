# Phase 9: Provenance Proof + Deposit-Ready Bundles - Proof of Origin

> Status: ACTIVE
> Web Root: /web
> Active Phase Ceiling: 11
> Execution Policy: Phase 0 through Phase 11 are ACTIVE for this prompt program.
> Web Translation Overlay (ACTIVE): preserve existing workflow intent and phase semantics while translating any legacy desktop or WinUI terms into equivalent browser-native routes, layouts, and interaction patterns under /web.

## Phase Objective
Prove the lineage of candidate snapshots attached to approved Phase 8 export requests back to a specific Controlled master and generate deposit-ready bundle artefacts that can be verified later without creating a second release path. Bundle creation depends on Phase 8 approval, not on completed external gateway delivery.

## Entry Criteria
Start Phase 9 only when all are true:
- the target output has passed Phase 8 disclosure review
- manifest, ledger, and baseline policy snapshot hash or explicit Phase 7 policy version metadata are complete for the candidate snapshot linked to the approved export request
- the linked Phase 8 approval record is available for bundle metadata, and export receipt metadata is attached later when gateway delivery has already occurred
- signing and verification keys are available inside the secure environment

## Scope Boundary
Phase 9 adds proofs and packaging on top of approved outputs.

Out of scope for this phase:
- search and derivative discovery products (Phase 10)
- operational hardening and pen-test readiness work (Phase 11)

## Phase 9 Non-Negotiables
- Secure web application is the active delivery target: preserve phase behavior and governance contracts while implementing browser-native interaction, routing, and layout patterns from first principles (no desktop-mechanics carryover).
- All workspace and page surfaces inherit the canonical `Obsidian Folio` experience contract (dark-first Fluent 2 tokens, app-window adaptive states, single-fold defaults, keyboard-first accessibility); see `ui-premium-dark-blueprint-obsidian-folio.md`.
1. Provenance proof must not reveal Controlled-only source text.
2. Bundle verification must succeed from bundle artefacts plus included verification material.
3. Candidate snapshots linked to approved Phase 8 export requests are immutable inputs to deposit bundles.
4. Controlled and safeguarded bundle variants must remain clearly separated.
5. Phase 9 packaging does not replace Phase 8 approval; any released bundle remains tied to a linked Phase 8 approval record and gateway path.

## Iteration Model
Build Phase 9 in four iterations (`9.0` to `9.3`). Each iteration must strengthen verifiability without weakening disclosure protection.

## Iteration 9.0: Provenance Graph + Signed Root

### Goal
Create a reproducible lineage chain from source transcript through review, policy, manifest, and export approval.

### Backend Work
- build provenance graph over:
  - transcription run
  - project model assignment or approved model reference for the active transcription role
  - redaction run
  - detector lineage including privacy rules version and NER or assist lineage when those contributed to approved decisions
  - manifest
  - governance readiness reference including the manifest or ledger pair that was current when the approved candidate snapshot was frozen
  - ledger verification lineage including the latest verification outcome that made the governance artefacts downstream-consumable
  - baseline policy snapshot hash or Phase 7 policy version
  - export request
  - export receipt (optional post-delivery evidence when gateway release has already occurred)
  - approved candidate snapshot
- compute Merkle root over Controlled lineage references using a pinned canonicalization contract:
  - each leaf is a canonical JSON object containing `artifact_kind`, stable identifier, immutable hash or version reference, and parent references only
  - canonical JSON uses UTF-8, sorted keys, and no insignificant whitespace
  - leaves are sorted by `(artifact_kind, stable_identifier)` before tree construction
  - each leaf hash is `SHA-256(canonical_leaf_bytes)`
- sign root with internal signing key

Add `provenance_proofs`:
- `id`
- `project_id`
- `export_request_id`
- `candidate_snapshot_id`
- `attempt_number`
- `supersedes_proof_id` (nullable)
- `superseded_by_proof_id` (nullable)
- `root_sha256`
- `signature_key_ref`
- `signature_bytes_key`
- `proof_artifact_key`
- `proof_artifact_sha256`
- `created_by`
- `created_at`

Rules:
- every approved export-request lineage has one current unsuperseded `provenance_proofs` record for the exact approved `candidate_snapshot_id`; repeated regeneration appends a new proof row, increments `attempt_number`, points `supersedes_proof_id` at the replaced proof, and records the forward link on the superseded row through `superseded_by_proof_id` instead of mutating the signed proof artifact in place
- the proof artifact contains the canonical leaf set, root hash, signature, and public-key verification material needed for offline verification inside later bundle workflows
- `GET /projects/{projectId}/export-requests/{exportRequestId}/provenance/proof` returns the current unsuperseded proof for that approved request lineage unless a specific historical proof row is requested later
- the first proof attempt is generated through an internal `GENERATE_PROVENANCE_PROOF(export_request_id)` workflow once an export request is approved and before bundle creation may proceed; manual regeneration appends a later proof attempt instead of replacing the original proof row

APIs:
- `GET /projects/{projectId}/export-requests/{exportRequestId}/provenance`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/provenance/proofs`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/provenance/proof`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/provenance/proofs/{proofId}`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/provenance/proofs/regenerate`

RBAC:
- `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can read provenance for approved export requests in their project.
- `AUDITOR` has read-only provenance access.
- `RESEARCHER` inherits provenance read access only when they can already read the linked approved export request.
- `POST /projects/{projectId}/export-requests/{exportRequestId}/provenance/proofs/regenerate` is `ADMIN` only

### Web Client Work
- provenance route under the existing export-request surface:
  - `/projects/:projectId/export-requests/:exportRequestId/provenance`
- provenance summary page:
  - lineage nodes
  - root hash and signature status
  - linked manifest, policy, model-lineage, and approval references

### Tests and Gates (Iteration 9.0)
#### Unit
- same lineage inputs produce same root
- changed input artefact invalidates the root
- canonical leaf ordering and serialization produce the same root across process restarts and language runtimes
- signed provenance proof artifacts persist immutable bytes and can be retrieved independently of later bundle generation
- approved export requests trigger the initial `GENERATE_PROVENANCE_PROOF` workflow before bundle creation proceeds, and manual regeneration appends a later proof attempt instead of replacing the original row

### Exit Criteria (Iteration 9.0)
Approved packages carry a stable lineage anchor.

## Iteration 9.1: Bundle Builder

### Goal
Package approved outputs into repeatable deposit-ready structures.

### Backend Work
Add `deposit_bundles`:
- `id`
- `project_id`
- `export_request_id`
- `candidate_snapshot_id`
- `provenance_proof_id`
- `provenance_proof_artifact_sha256`
- `bundle_kind` (`CONTROLLED_EVIDENCE | SAFEGUARDED_DEPOSIT`)
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `attempt_number`
- `supersedes_bundle_id` (nullable)
- `superseded_by_bundle_id` (nullable)
- `bundle_key` (nullable until build succeeds)
- `bundle_sha256` (nullable until build succeeds)
- `failure_reason` (nullable)
- `created_by`
- `created_at`
- `started_at`
- `finished_at`
- `canceled_by` (nullable)
- `canceled_at` (nullable)

Rules:
- repeated bundle builds append a new bundle attempt, point `supersedes_bundle_id` at the previous attempt, and record the forward link on the superseded row through `superseded_by_bundle_id` instead of mutating bundle bytes in place
- one unsuperseded bundle lineage exists per `(export_request_id, candidate_snapshot_id, bundle_kind)` tuple; create calls are idempotent for that lineage until an explicit rebuild is requested
- only `SAFEGUARDED_DEPOSIT` bundle lineages may later register Phase 8 `export_candidate_snapshots`, and only through an explicit bundle-to-candidate registration step that creates a new candidate lineage and re-enters full Phase 8 approval; `CONTROLLED_EVIDENCE` bundles remain internal admin/auditor artefacts and never become export candidates
- bundle creation freezes the specific current unsuperseded `provenance_proof_id` and `provenance_proof_artifact_sha256` included in the bundle, so later proof regeneration does not make an already-built bundle ambiguous about which signed proof attempt it contains

Add `bundle_verification_projections`:
- `bundle_id`
- `status` (`PENDING | VERIFIED | FAILED`)
- `last_verification_run_id` (nullable)
- `verified_at` (nullable)
- `updated_at`

Add `bundle_events`:
- `id`
- `bundle_id`
- `event_type` (`BUNDLE_BUILD_QUEUED | BUNDLE_REBUILD_REQUESTED | BUNDLE_BUILD_STARTED | BUNDLE_BUILD_SUCCEEDED | BUNDLE_BUILD_FAILED | BUNDLE_BUILD_CANCELED | BUNDLE_VERIFICATION_STARTED | BUNDLE_VERIFICATION_SUCCEEDED | BUNDLE_VERIFICATION_FAILED | BUNDLE_VERIFICATION_CANCELED | BUNDLE_VALIDATION_STARTED | BUNDLE_VALIDATION_SUCCEEDED | BUNDLE_VALIDATION_FAILED | BUNDLE_VALIDATION_CANCELED`)
- `verification_run_id` (nullable)
- `validation_run_id` (nullable)
- `actor_user_id` (nullable for system-generated build, verification, and validation jobs)
- `reason` (nullable)
- `created_at`

Bundle-event rules:
- bundle build enqueue, rebuild-request, start, success, failure, and cancel actions append `bundle_events`
- verification start, success, failure, and cancel actions append `bundle_events` with `verification_run_id` populated in addition to updating `bundle_verification_runs` and `bundle_verification_projections`
- validation start, success, failure, and cancel actions append `bundle_events` with `validation_run_id` populated in addition to updating `bundle_validation_runs` and `bundle_validation_projections`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/events` is the single bundle-history feed for build, verification, and validation activity; UI timelines must not merge three separate status stores ad hoc

Build:
- `controlled_evidence_bundle.zip` (internal only)
- `safeguarded_deposit_bundle.zip` (internal bundle artefact tied to an approved candidate snapshot; if later frozen as a candidate it must re-enter Phase 8 as a new candidate lineage and never bypass review)

APIs:
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles?kind={bundleKind}`
  - requires `bundleKind`
  - returns the current unsuperseded bundle of that kind for the same request and candidate snapshot when one already exists, instead of silently creating a duplicate lineage
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/status`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/events`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/cancel`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/rebuild`
  - appends the next attempt in the existing bundle lineage for the same `bundle_kind` and `candidate_snapshot_id`

RBAC:
- `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can build safeguarded deposit bundles for already approved export requests in their project.
- `controlled_evidence_bundle.zip` build access is limited to `ADMIN`; read access is limited to `ADMIN` and read-only `AUDITOR`.
- `safeguarded_deposit_bundle.zip` is visible only when it is tied to an approved Phase 8 export request for the same project, and its read access follows that export request's read permissions.
- cancel and rebuild actions for `SAFEGUARDED_DEPOSIT` bundles follow the same role checks as bundle creation for that request
- cancel and rebuild actions for `CONTROLLED_EVIDENCE` bundles are limited to `ADMIN`
- `RESEARCHER` does not access Controlled evidence bundles.

Bundle retrieval stays behind authenticated internal handlers. Bundle APIs do not return raw object-store URLs and do not create a second egress path outside Phase 8.
Bundle detail surfaces show the latest attempt status plus prior attempts when a rebuild supersedes an older bundle row.
`GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/events` reads from append-only `bundle_events`, so build, verify, validate, and cancel history does not depend on mutable status projections.

Include:
- transcript or derivative output
- manifest
- metadata
- tool and policy versions
- the signed provenance proof artifact itself
- included public-key or certificate material needed to verify that proof offline
- governance-readiness and ledger-verification references that justify why the bundled candidate was eligible for downstream packaging
- linked `export_request_id` and approval metadata
- approved `candidate_snapshot_id`
- linked export receipt metadata when a receipt already exists

### Web Client Work
- bundle routes under the existing export-request surface:
  - `/projects/:projectId/export-requests/:exportRequestId/bundles`
  - `/projects/:projectId/export-requests/:exportRequestId/bundles/:bundleId`
  - `/projects/:projectId/export-requests/:exportRequestId/bundles/:bundleId/events`
- bundle preview page:
  - contents
  - hashes
  - proof status
  - linked export approval record
  - approved candidate snapshot
  - linked export receipt when delivery evidence exists
  - attempt history from the bundle events route and live status polling through the bundle status endpoint

### Tests and Gates (Iteration 9.1)
#### Unit
- bundle content schema tests
- bundle hashes match source artefacts
- bundle creation is blocked unless the linked export request is `APPROVED`
- bundle create is idempotent per `(export_request_id, candidate_snapshot_id, bundle_kind)` lineage
- bundle event timeline shows build lifecycle transitions from append-only `bundle_events` without inferring missing steps from status projections
- bundle contents include the signed provenance proof artifact plus the verification material required for offline proof verification

### Exit Criteria (Iteration 9.1)
Bundles are repeatable governed artefacts instead of hand-assembled export sets.

## Iteration 9.2: Verification Tooling

### Goal
Make proof checking operational for `ADMIN`, `AUDITOR`, and internal deposit-validation workflows.

### Backend Work
- `verify bundle` CLI inside secure environment
- server-side verification job
- verification result records linked to bundle ID

Add `bundle_verification_runs`:
- `id`
- `project_id`
- `bundle_id`
- `attempt_number`
- `supersedes_verification_run_id` (nullable)
- `superseded_by_verification_run_id` (nullable)
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `result_json`
- `created_by`
- `created_at`
- `started_at`
- `finished_at`
- `canceled_by` (nullable)
- `canceled_at` (nullable)
- `failure_reason` (nullable)

Rules:
- repeated verification requests append a new verification attempt, point `supersedes_verification_run_id` at the previous attempt, and record the forward link on the superseded row through `superseded_by_verification_run_id`
- `bundle_verification_projections` stores the latest non-canceled verification outcome for bundle-level status reads, while per-run status endpoints expose in-flight or canceled attempts without overwriting the last successful verification state
- bundle verification must succeed from bundle contents plus the included signed provenance proof artifact and included verification material; it must not depend on live database lookups or external key fetches during verification

APIs:
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verify`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/status`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification-runs`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/{verificationRunId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/{verificationRunId}/status`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/{verificationRunId}/cancel`

RBAC:
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verify` is `ADMIN` only
- verification read endpoints for `SAFEGUARDED_DEPOSIT` bundles follow the underlying bundle read permissions for the approved export request
- verification read endpoints for `CONTROLLED_EVIDENCE` bundles are limited to `ADMIN` and read-only `AUDITOR`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/{verificationRunId}/cancel` is `ADMIN` only

Audit events emitted:
- `EXPORT_PROVENANCE_VIEWED`
- `BUNDLE_LIST_VIEWED`
- `BUNDLE_BUILD_RUN_CREATED`
- `BUNDLE_BUILD_RUN_STARTED`
- `BUNDLE_BUILD_RUN_FINISHED`
- `BUNDLE_BUILD_RUN_FAILED`
- `BUNDLE_BUILD_RUN_CANCELED`
- `BUNDLE_DETAIL_VIEWED`
- `BUNDLE_STATUS_VIEWED`
- `BUNDLE_EVENTS_VIEWED`
- `BUNDLE_VERIFICATION_RUN_CREATED`
- `BUNDLE_VERIFICATION_RUN_STARTED`
- `BUNDLE_VERIFICATION_RUN_FINISHED`
- `BUNDLE_VERIFICATION_RUN_FAILED`
- `BUNDLE_VERIFICATION_RUN_CANCELED`
- `BUNDLE_VERIFICATION_VIEWED`
- `BUNDLE_VERIFICATION_STATUS_VIEWED`

### Web Client Work
- verification route under the existing export-request surface:
  - `/projects/:projectId/export-requests/:exportRequestId/bundles/:bundleId/verification`
- verification page:
  - `ADMIN` can trigger verification
  - `PROJECT_LEAD` and `REVIEWER` can read verification results for safeguarded deposit bundles they can already access
  - `AUDITOR` has read-only access to pass/fail details and proof metadata
  - Controlled evidence bundle verification details remain limited to `ADMIN` and read-only `AUDITOR`
  - verification summary reads `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/status`
  - verification history is listed by `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification-runs` and can open a specific run or poll `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/{verificationRunId}/status`

### Tests and Gates (Iteration 9.2)
#### Integration
- tamper test: modify one file and verification fails
- valid bundle verifies consistently through CLI and server job using only bundle contents plus included verification material
- verification requests are rejected unless the target bundle status is `SUCCEEDED`
- `ADMIN` can trigger verification; `AUDITOR` can read results but cannot start verification jobs or mutate bundle state
- canceled verification runs stop cleanly without mutating stored bundle bytes or replacing the latest successful verification result
- repeated verification requests append a new verification attempt, write `superseded_by_verification_run_id` on the prior attempt, and leave prior run rows intact
- verification history listing returns append-only attempts in newest-first order without reconstructing attempt order from mutable projection state
- verification does not rely on live database lineage lookups once the bundle and included proof material are present
- bundle rows pin the packaged `provenance_proof_id`, so bundle detail and verification reads can identify the exact signed proof attempt included in a historical bundle even after later proof regeneration

### Exit Criteria (Iteration 9.2)
Bundle verification is repeatable and not dependent on manual expert interpretation.

## Iteration 9.3: Deposit Profiles + Archive Validation

### Goal
Prepare bundles for common archive or deposit expectations without collapsing security boundaries.

### Backend Work
- profile-specific metadata templates
- completeness checks for missing manifest, proof, or checksum files
- validation rules for contradictory bundle contents

Add `bundle_validation_runs`:
- `id`
- `project_id`
- `bundle_id`
- `profile_id`
- `profile_snapshot_key`
- `profile_snapshot_sha256`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `attempt_number`
- `supersedes_validation_run_id` (nullable)
- `superseded_by_validation_run_id` (nullable)
- `result_json`
- `failure_reason` (nullable)
- `created_by`
- `created_at`
- `started_at`
- `finished_at`
- `canceled_by` (nullable)
- `canceled_at` (nullable)

Add `bundle_validation_projections`:
- `bundle_id`
- `profile_id`
- `status` (`PENDING | READY | FAILED`)
- `last_validation_run_id` (nullable)
- `ready_at` (nullable)
- `updated_at`

Rules:
- repeated profile validations append a new validation attempt, point `supersedes_validation_run_id` at the previous attempt, and record the forward link on the superseded row through `superseded_by_validation_run_id`
- `bundle_validation_projections` stores the latest non-canceled validation outcome per bundle/profile for `validation-status` reads, while per-run status endpoints expose in-flight or canceled attempts without replacing the last successful validation result
- `bundle_validation_projections.status = READY` when `last_validation_run_id` points to a `SUCCEEDED` run, `FAILED` when the latest non-canceled run for that profile failed and no successful validation remains current, and `PENDING` before any non-canceled validation result exists for that bundle/profile
- each validation attempt resolves the requested deposit profile into immutable `profile_snapshot_key` and `profile_snapshot_sha256` values before validation starts, so historical validation outcomes remain reproducible even if the named profile template changes later

APIs:
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundle-profiles`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validate-profile`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-status?profile={profileId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-runs?profile={profileId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-runs/{validationRunId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-runs/{validationRunId}/status`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-runs/{validationRunId}/cancel`

RBAC:
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validate-profile` is available to `ADMIN` for any bundle, and to `PROJECT_LEAD` or `REVIEWER` only for `SAFEGUARDED_DEPOSIT` bundles they can already access
- validation read endpoints for `SAFEGUARDED_DEPOSIT` bundles follow the underlying bundle read permissions for the approved export request
- validation read endpoints for `CONTROLLED_EVIDENCE` bundles are limited to `ADMIN` and read-only `AUDITOR`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-runs/{validationRunId}/cancel` follows the same role checks as validation-start for that bundle kind and access scope

### Web Client Work
- deposit profile selector
- deposit-profile validation route under the existing export-request surface:
  - `/projects/:projectId/export-requests/:exportRequestId/bundles/:bundleId/validation?profile={profileId}`
- validation summary for the selected profile after a bundle exists and before the bundle is marked deposit-ready for that profile
- deposit-ready badges read `bundle_validation_projections` and are shown only when the selected profile's latest validation run is `SUCCEEDED` and the bundle's verification projection is `VERIFIED`
- validation history preserves the resolved `profile_snapshot_key` and `profile_snapshot_sha256` for each attempt, so historical pass or fail results remain reproducible after deposit-profile evolution

### Tests and Gates (Iteration 9.3)
#### Unit
- profile selection produces expected metadata files

#### Integration
- completeness checks block incomplete bundles
- canceled validation runs stop cleanly without replacing the latest successful validation result
- profile validation does not mark a bundle deposit-ready for a profile unless the latest validation run for that profile is `SUCCEEDED` and the bundle's verification projection is `VERIFIED`
- repeated profile validations append a new validation attempt, write `superseded_by_validation_run_id` on the prior attempt, and leave prior validation rows intact
- Audit events emitted:
  - `BUNDLE_PROFILES_VIEWED`
  - `BUNDLE_VALIDATION_RUN_CREATED`
  - `BUNDLE_VALIDATION_RUN_STARTED`
  - `BUNDLE_VALIDATION_RUN_FINISHED`
  - `BUNDLE_VALIDATION_RUN_FAILED`
  - `BUNDLE_VALIDATION_RUN_CANCELED`
  - `BUNDLE_VALIDATION_VIEWED`
  - `BUNDLE_VALIDATION_STATUS_VIEWED`

### Exit Criteria (Iteration 9.3)
Approved outputs can be turned into deposit-ready bundles with predictable validation.

## Handoff to Later Phases
- Phase 10 may index approved derivatives and Controlled data products, but bundle packaging remains a separate governed concern and does not create a new egress path.
- Phase 11 hardens the proof, verification, and packaging workflows for production reliability.

## Phase 9 Definition of Done
Move to Phase 10 only when all are true:
1. Approved outputs carry a verifiable lineage proof back to Controlled lineage inputs.
2. Controlled and safeguarded bundles are built from immutable approved snapshots and linked to the governing Phase 8 approval record.
3. Verification tooling catches tampering and validates legitimate bundles consistently.
4. Deposit-profile validation blocks incomplete or contradictory package structures.
5. Provenance proof and bundle metadata do not leak Controlled-only text.

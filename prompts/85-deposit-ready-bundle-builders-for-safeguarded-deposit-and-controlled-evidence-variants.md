You are the implementation agent for UKDE. Work directly in the repository. Do not ask clarifying questions. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: assume zero chat memory and reread the repo plus the listed phase files before changing anything.
- Sequenced: if the repo already contains partial implementation from earlier prompts, extend and reconcile it instead of restarting from scratch.

The actual product source of truth is the extracted `/phases` directory in repo root. Do not mention or expect a zip. Read `/phases` first on every run.

## Mandatory first actions
1. Inspect the full repository tree.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/phase-09-provenance-proof-bundles.md`
3. Then review the current repository generally — approved export requests, candidate snapshots, provenance proofs, storage adapters, typed contracts, route shells, audit code, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second bundle model, a second bundle event stream, or conflicting bundle-kind semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for bundle kinds, bundle lineage, included contents, RBAC, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that bundles are governed internal artefacts, that only safeguarded deposit bundles may later re-enter Phase 8 as new candidate lineage, and that controlled evidence bundles never become export candidates.

## Objective
Implement deposit-ready bundle builders for safeguarded-deposit and controlled-evidence variants.

This prompt owns:
- canonical deposit bundle schema and lifecycle
- `SAFEGUARDED_DEPOSIT` and `CONTROLLED_EVIDENCE` bundle builders
- bundle contents assembly
- bundle event stream
- bundle list/detail/status/events APIs
- bundle preview routes and detail shells
- idempotent create and explicit rebuild semantics
- bundle RBAC and internal-only retrieval behavior

This prompt does not own:
- bundle verification jobs
- auditor-grade proof viewer
- deposit profile variants beyond the two canonical bundle kinds
- public or external bundle delivery
- candidate re-registration workflow beyond preserving the lineage contract

## Phase alignment you must preserve
From Phase 9 Iteration 9.1:

### Required table
Implement or reconcile `deposit_bundles`:
- `id`
- `project_id`
- `export_request_id`
- `candidate_snapshot_id`
- `provenance_proof_id`
- `provenance_proof_artifact_sha256`
- `bundle_kind` (`CONTROLLED_EVIDENCE | SAFEGUARDED_DEPOSIT`)
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `attempt_number`
- `supersedes_bundle_id`
- `superseded_by_bundle_id`
- `bundle_key`
- `bundle_sha256`
- `failure_reason`
- timestamps and cancel metadata

### Required projections and events
Implement or reconcile:
- `bundle_verification_projections`
- `bundle_events`

`bundle_events` must be the single bundle-history feed for build, verification, and validation activity.

### Required bundle rules
- repeated bundle builds append a new bundle attempt
- one unsuperseded bundle lineage exists per `(export_request_id, candidate_snapshot_id, bundle_kind)` tuple
- create is idempotent for that lineage until an explicit rebuild is requested
- cancel is allowed only while bundle attempt status is `QUEUED` or `RUNNING`; terminal-state cancellation is rejected
- `SAFEGUARDED_DEPOSIT` bundles may later register new candidate lineage through an explicit later step
- `CONTROLLED_EVIDENCE` bundles remain internal-only and never become Phase 8 candidates
- bundle creation freezes the exact unsuperseded `provenance_proof_id` included in the bundle

### Required bundle contents
Include:
- transcript or derivative output
- manifest
- metadata
- tool and policy versions
- the signed provenance proof artefact
- included public-key or certificate material needed to verify the proof offline
- governance-readiness and ledger-verification references
- linked `export_request_id` and approval metadata
- approved `candidate_snapshot_id`
- linked export receipt metadata when a receipt already exists

### Required routes and APIs
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles?kind={bundleKind}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/status`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/events`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/cancel`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/rebuild`

### Required RBAC
- `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can build `SAFEGUARDED_DEPOSIT` bundles for approved export requests in their project
- `CONTROLLED_EVIDENCE` build access is limited to `ADMIN`
- `SAFEGUARDED_DEPOSIT` rebuild/cancel mutations follow safeguarded bundle build permissions (`PROJECT_LEAD`, `REVIEWER`, `ADMIN`) for approved export requests in their project
- `CONTROLLED_EVIDENCE` rebuild/cancel mutations are limited to `ADMIN`
- `CONTROLLED_EVIDENCE` read access limited to `ADMIN` and read-only `AUDITOR`
- `SAFEGUARDED_DEPOSIT` read access follows the approved export request’s read permissions
- `RESEARCHER` does not access Controlled evidence bundles

## Implementation scope

### 1. Canonical bundle schema and lineage
Implement or refine the canonical bundle model.

Requirements:
- one authoritative `deposit_bundles` store
- append-only attempt lineage
- idempotent create behavior per `(export_request_id, candidate_snapshot_id, bundle_kind)` lineage
- explicit rebuild semantics that supersede prior attempts
- no second bundle schema

### 2. Bundle builder pipeline
Implement the build pipeline for both bundle kinds.

Requirements:
- deterministic assembly of contents
- correct inclusion of signed provenance proof artefact and verification material
- correct inclusion of governance and approval metadata
- correct linkage to candidate snapshot and export request
- no raw object-store path leakage inside bundle metadata where that would violate internal packaging rules

### 3. Bundle events
Implement or refine the bundle event stream.

Requirements:
- build enqueue, rebuild request, start, success, failure, cancel events append to `bundle_events`
- timeline ordering is deterministic
- no separate shadow history store
- UI reads bundle history from the event stream

### 4. Retrieval APIs and status
Implement or refine bundle list/detail/status/events APIs.

Requirements:
- typed contracts
- internal-only retrieval
- no public URLs
- detail shows latest attempt plus prior attempts when superseded
- status remains exact for `QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`

### 5. Web bundle surfaces
Implement or refine:
- `/projects/:projectId/export-requests/:exportRequestId/bundles`
- `/projects/:projectId/export-requests/:exportRequestId/bundles/:bundleId`
- `/projects/:projectId/export-requests/:exportRequestId/bundles/:bundleId/events`

Requirements:
- list of bundle lineages and attempts
- bundle detail preview with contents, hashes, proof status, linked approval record, approved candidate snapshot, optional receipt metadata
- event timeline
- calm empty/loading/error/not-ready states
- dense, internal, review-grade UI

### 6. RBAC and internal-only behavior
Harden the access and build semantics.

Requirements:
- role permissions exactly follow phase rules
- bundle retrieval remains behind authenticated internal handlers
- no raw object-store URLs are returned
- no second egress path is introduced

### 7. Audit and tests
Use the canonical audit path and add coverage.

At minimum cover:
- bundle creation blocked unless export request is `APPROVED`
- bundle create idempotency per lineage key
- bundle hashes match included source artefacts
- bundle event timeline reflects append-only lifecycle
- controlled evidence bundles remain inaccessible to `RESEARCHER`
- safeguarded deposit bundle access follows request permissions
- signed proof artefact and verification material are included

### 8. Documentation
Document:
- bundle kinds and access rules
- lineage and rebuild semantics
- included contents
- event history semantics
- what Prompt 86 will deepen with verification

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / storage / contracts
- deposit bundle schema
- bundle builder pipeline
- bundle events
- typed bundle APIs
- tests

### Web
- bundle list/detail/events surfaces
- internal-only status and access messaging

### Docs
- deposit bundle builder and lineage doc
- internal access and bundle-event timeline doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- storage adapters/config used by the repo
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small bundle-list/detail/timeline refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- bundle verification jobs
- provenance proof generation
- public bundle delivery
- candidate re-registration workflow
- a second bundle model

## Testing and validation
Before finishing:
1. Verify bundle creation is blocked unless export request is `APPROVED`.
2. Verify create is idempotent per `(export_request_id, candidate_snapshot_id, bundle_kind)` lineage.
3. Verify rebuild appends a superseding attempt.
4. Verify bundle contents include proof artefact and verification material.
5. Verify bundle hashes match source artefacts.
6. Verify bundle events are append-only and ordered deterministically.
7. Verify RBAC for `SAFEGUARDED_DEPOSIT` vs `CONTROLLED_EVIDENCE`.
8. Verify rebuild/cancel role boundaries match bundle-kind RBAC.
9. Verify cancel is allowed only for `QUEUED` or `RUNNING` bundle attempts and rejected for terminal states.
10. Verify docs match the implemented bundle behavior.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- deposit bundle builders are real
- bundle lineage and events are real
- bundle surfaces are real
- internal-only access rules are real
- later verification and deposit tooling can build on stable bundle contracts
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

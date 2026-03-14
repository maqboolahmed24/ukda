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
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — provenance proofs, bundle builders, verification tooling, storage/signing helpers, bundle schemas, validation scaffolding if any, CI workflows, runbooks, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second provenance replay framework, a second bundle-validation model, or conflicting failure-recovery semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for proof and bundle immutability, validation profiles, append-only attempt lineage, recovery behavior, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that provenance replay and validation must succeed from stored bundle artefacts plus included verification material, without hidden dependence on mutable live database state or external key fetches.

## Objective
Rehearse end-to-end provenance replay with deterministic verification and failure-recovery handling.

This prompt owns:
- deterministic provenance replay tooling from approved request lineage to proof verification and bundle validation
- deposit-profile validation runs and projections
- replay-safe verification and validation attempt lineage
- deterministic failure and recovery handling for proof, bundle, and validation workflows
- operator-visible status and recovery evidence for replay drills
- CI and runbook coverage proving that replay and recovery actually work

This prompt does not own:
- new proof generation formats
- new bundle kinds
- public deposit flows
- export gateway behavior
- a second replay or validation stack

## Phase alignment you must preserve
From Phase 9 Iteration 9.2 and 9.3, plus Phase 11 recovery expectations:

### Existing proof and bundle rules
- approved export requests have one current unsuperseded provenance proof lineage
- bundle creation freezes the exact proof attempt included in the bundle
- verification must succeed from bundle contents plus included proof material only
- repeated verification attempts append new rows and do not mutate prior attempts

### Existing deposit-profile validation rules
Implement or reconcile:
- `bundle_validation_runs`
- `bundle_validation_projections`

`bundle_validation_runs`:
- `id`
- `project_id`
- `bundle_id`
- `profile_id`
- `profile_snapshot_key`
- `profile_snapshot_sha256`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `attempt_number`
- `supersedes_validation_run_id`
- `superseded_by_validation_run_id`
- `result_json`
- `failure_reason`
- timestamps and cancel fields

`bundle_validation_projections`:
- `bundle_id`
- `profile_id`
- `status` (`PENDING | READY | FAILED`)
- `last_validation_run_id`
- `ready_at`
- `updated_at`

Rules:
- repeated profile validations append a new validation attempt
- the projection stores the latest non-canceled successful validation outcome per bundle/profile as last-known-good readiness truth
- `READY` requires:
  - a non-canceled successful validation outcome exists for the bundle/profile (last-known-good)
  - bundle verification projection is `VERIFIED`
- `FAILED` is used when the latest non-canceled validation outcome is `FAILED` and no non-canceled successful validation exists yet for the bundle/profile
- `PENDING` is used when no non-canceled validation outcome exists yet for the bundle/profile
- profile validation history must preserve the resolved `profile_snapshot_key` and `profile_snapshot_sha256`

### Required APIs
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundle-profiles`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validate-profile?profile={profileId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-status?profile={profileId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-runs?profile={profileId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-runs/{validationRunId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-runs/{validationRunId}/status`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/validation-runs/{validationRunId}/cancel`

### RBAC
- `POST .../validate-profile` and `POST .../validation-runs/{validationRunId}/cancel` are `ADMIN` only
- `GET .../bundle-profiles` follows the same read boundary as validation reads for the target bundle kind
- validation reads for `SAFEGUARDED_DEPOSIT` bundles follow underlying bundle read permissions
- validation reads for `CONTROLLED_EVIDENCE` bundles are limited to `ADMIN` and read-only `AUDITOR`
- `AUDITOR` is read-only on replay/validation surfaces

### Recovery and replay expectations
- replay must be able to reconstruct verification and validation deterministically from stored artefacts
- canceled attempts do not replace prior valid verification/validation truth
- replacement attempts do not collapse last known good projections during failure
- operator runbooks must describe replay and recovery steps, not just nominal happy path

## Implementation scope

### 1. Canonical provenance replay tooling
Implement or refine one replay path that can:
- locate the approved export request lineage
- resolve the pinned candidate snapshot
- resolve the pinned provenance proof
- replay verification over a built bundle
- replay profile validation over that verified bundle

Requirements:
- no mutable live DB convenience lookups are required once artefacts are resolved
- replay is deterministic
- failures produce exact step-local evidence
- no second hidden replay implementation separate from production verification/validation logic

### 2. Bundle-profile validation pipeline
Implement or refine the Phase 9.3 validation pipeline.

Requirements:
- deposit profile list/read
- validation run creation
- validation run execution
- validation result persistence
- validation projections updated using deterministic `PENDING | READY | FAILED` rules with last-known-good readiness preservation
- validate-profile requests require explicit `profile={profileId}` selection consistent with validation-status and validation-runs reads
- explicit profile snapshot pinning on each attempt
- no ambiguous "current profile definition" behavior for historical validation results

### 3. Failure-recovery handling
Harden failure and cancellation behavior.

Requirements:
- verification failure does not erase prior successful verification state
- validation failure does not erase prior successful validation projection
- canceled verification or validation attempts remain visible and append-only
- cancel is allowed only while verification/validation run status is `QUEUED` or `RUNNING`; terminal-state cancellation is rejected
- failed retries after a prior successful validation do not downgrade projection readiness truth; failure evidence remains visible in run history
- retries/replays append new attempts
- no silent replacement of last known good state by a failed replay attempt

### 4. Replay drill and evidence support
Implement or refine a replay drill path for operators.

Requirements:
- deterministic replay of proof verification and profile validation for a chosen bundle
- drill results include enough evidence to distinguish:
  - missing artefact
  - tampered proof
  - invalid bundle contents
  - profile mismatch
  - environmental/runtime issue
- drill status is machine-readable and operator-readable
- no new production mutation path is required to run a replay drill

If a persisted replay-drill record helps and fits the repo cleanly, add it. If not, at minimum provide deterministic job/event evidence and operator runbooks.

### 5. Read surfaces and status
Expose typed status for:
- current verification outcome
- current per-profile validation outcome
- last successful attempt
- in-flight replacement attempt
- canceled/failure evidence

Prefer extending existing bundle verification/detail surfaces over inventing parallel status APIs unless a dedicated replay-status endpoint is necessary.

### 6. CI and operational regression
Add or refine:
- deterministic proof replay tests
- tamper-detection replay tests
- profile-validation replay tests
- failure-recovery projection tests
- cancel-and-retry behavior tests
- runbook consistency checks where practical

### 7. Documentation
Document:
- provenance replay workflow
- validation profile semantics
- failure-recovery rules
- operator replay drill steps
- what later deposit and archive workflows can assume from these guarantees

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / workers / contracts
- provenance replay tooling
- bundle validation runs and projections
- failure-recovery-safe verification/validation lineage
- tests

### Web
- only small truthful replay/validation status refinements if needed for current bundle/proof surfaces

### Docs
- provenance replay and validation recovery doc
- operator replay drill and failure handling doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- storage/signing helpers used by the repo
- `/web/**` only if small truthful status refinements are needed
- `/packages/contracts/**`
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- new bundle kinds
- new proof formats
- public archive delivery
- a second replay framework
- any mutation of historical proof, bundle, verification, or validation attempts

## Testing and validation
Before finishing:
1. Verify proof replay succeeds deterministically on untampered bundles.
2. Verify tampered bundles fail verification deterministically.
3. Verify profile validation runs append new attempts and preserve profile snapshot lineage.
4. Verify validate-profile rejects missing or unknown `profile` selectors.
5. Verify failed validation does not erase the last known good validation projection.
6. Verify `FAILED` projection status is used when the latest non-canceled validation fails and no prior successful validation exists for that profile.
7. Verify failed retries after a prior successful validation do not downgrade `READY` projection truth.
8. Verify canceled validation or verification attempts remain append-only and visible.
9. Verify cancel is allowed only for `QUEUED` or `RUNNING` verification/validation runs and rejected for terminal states.
10. Verify replay/validation RBAC boundaries for admin writes and read-only auditor behavior.
11. Verify replay drills or equivalent evidence can distinguish failure classes clearly.
12. Verify docs match the implemented replay and recovery behavior.
13. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- end-to-end provenance replay is real
- deposit-profile validation is real
- failure-recovery behavior is real and deterministic
- last-known-good verification/validation truth is preserved during failure
- operators have a concrete replay and recovery story
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

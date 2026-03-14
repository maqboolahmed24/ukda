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
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-09-provenance-proof-bundles.md`
3. Then review the current repository generally — provenance proofs, deposit bundle schema, verification projections, bundle routes, audit events, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second verification model, a second proof-viewer route family, or conflicting verification-status semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for verification-run lineage, proof-material requirements, RBAC, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that verification must work from bundle contents plus included proof material alone, and that auditors can inspect but not mutate verification state.

## Objective
Create bundle-verification tooling and an auditor-grade proof viewer for lineage inspection.

This prompt owns:
- bundle verification CLI and server-side verification job
- verification attempt lineage and projections
- bundle verification routes and detail/status APIs
- auditor/admin proof viewer surfaces
- pass/fail detail display and immutable verification history
- cancellation behavior for in-flight verification
- tamper-detection tests and offline-verification correctness
- browser-grade verification UX for allowed roles

This prompt does not own:
- provenance proof generation
- bundle building
- deposit profile variants beyond those already built
- external key fetches
- a second verification framework

## Phase alignment you must preserve
From Phase 9 Iteration 9.2:

### Required table
Implement or reconcile `bundle_verification_runs`:
- `id`
- `project_id`
- `bundle_id`
- `attempt_number`
- `supersedes_verification_run_id`
- `superseded_by_verification_run_id`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `result_json`
- `created_by`
- `created_at`
- `started_at`
- `finished_at`
- `canceled_by`
- `canceled_at`
- `failure_reason`

### Existing projection rules
- `bundle_verification_projections` stores the latest non-canceled successful verification outcome as bundle-level verification truth
- per-run status endpoints expose in-flight or canceled attempts without overwriting the last successful verification state
- repeated verification requests append a new verification attempt and supersede the previous attempt

### Existing verification rules
- verification must succeed from bundle contents plus the included signed provenance proof artefact and included verification material
- verification must not depend on live database lineage lookups or external key fetches
- target bundle must be `SUCCEEDED` before verification can start
- cancel is allowed only while verification run status is `QUEUED` or `RUNNING`; terminal-state cancellation is rejected

### Existing APIs
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verify`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/status`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification-runs`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/{verificationRunId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/{verificationRunId}/status`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/bundles/{bundleId}/verification/{verificationRunId}/cancel`

### RBAC
- `POST .../verify` is `ADMIN` only
- verification reads for `SAFEGUARDED_DEPOSIT` bundles follow underlying bundle read permissions
- verification reads for `CONTROLLED_EVIDENCE` bundles are limited to `ADMIN` and read-only `AUDITOR`
- cancel is `ADMIN` only

### Audit events
Use or reconcile:
- `EXPORT_PROVENANCE_VIEWED`
- `BUNDLE_LIST_VIEWED`
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

## Implementation scope

### 1. Canonical verification tooling
Implement or refine the secure verification tooling.

Requirements:
- a CLI inside the secure environment
- a server-side verification job
- both paths verify using bundle contents plus included proof material only
- no live DB lineage lookups during verification
- no external key fetches
- no second verification codepath with divergent rules

### 2. Verification attempt lineage
Implement append-only verification runs.

Requirements:
- repeated verification requests append attempts
- supersession links are coherent
- bundle-level projection points to latest non-canceled successful verification truth (last-known-good)
- historical verification runs remain readable and immutable
- cancellation does not destroy prior valid verification history

### 3. Verification APIs and status
Implement or refine the canonical verification APIs.

Requirements:
- typed contracts
- verification start blocked unless bundle status is `SUCCEEDED`
- status polling is dedicated and efficient
- verification run detail exposes exact result and failure fields
- verification history listing is append-only and newest-first

### 4. Auditor-grade proof viewer
Implement the verification UI and proof viewer.

Requirements:
- verification summary page under:
  - `/projects/:projectId/export-requests/:exportRequestId/bundles/:bundleId/verification`
- `ADMIN` can trigger verification
- `PROJECT_LEAD`, `REVIEWER`, and `RESEARCHER` can read verification results for safeguarded deposit bundles only when they already have access through underlying bundle/request permissions
- `AUDITOR` has read-only access to pass/fail details and proof metadata
- controlled evidence bundle verification details remain limited to `ADMIN` and `AUDITOR`
- UI shows:
  - root hash
  - signature status
  - included verification material summary
  - verification result
  - verification history
  - tamper or mismatch detail
- calm, dense, exact presentation

### 5. Tamper and offline-verification behavior
Make failure cases explicit.

Requirements:
- tamper with one file -> verification fails
- pass/fail detail is reviewable
- no manual expert interpretation required for core valid/invalid result
- proof viewer does not expose raw storage URLs or unnecessary internal-only material beyond allowed verification details

### 6. Browser quality and accessibility
Add or refine browser coverage.

At minimum cover:
- verification summary
- admin-triggered verification
- verification history list
- failed tamper case
- read-only auditor view
- focus, keyboard, and status update behavior
- visual baselines for valid / invalid / pending states

### 7. Documentation
Document:
- verification tooling architecture
- append-only verification-run lineage
- proof viewer semantics
- offline verification requirements
- what later deposit-validation prompts can assume from this layer

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / workers / contracts
- verification CLI and server job
- bundle verification runs and projections
- typed verification APIs
- tests

### Web
- verification route and proof viewer
- verification history and status surfaces
- browser tests and visual baselines

### Docs
- bundle verification tooling doc
- proof viewer and verification lineage doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small verification/proof-view refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- proof generation
- bundle building
- external verification services
- a second verification framework
- widening bundle access beyond allowed roles

## Testing and validation
Before finishing:
1. Verify valid bundles verify through both CLI and server job using only bundle contents and included verification material.
2. Verify tampering one file causes verification failure.
3. Verify verification start is rejected unless bundle status is `SUCCEEDED`.
4. Verify repeated verification requests append new attempts and preserve prior history.
5. Verify canceled verification runs do not replace the latest successful verification result.
6. Verify `ADMIN` can trigger verification and `AUDITOR` stays read-only.
7. Verify cancel is `ADMIN` only and rejected for non-admin roles.
8. Verify cancel is allowed only for `QUEUED` or `RUNNING` verification runs and rejected for terminal states.
9. Verify safeguarded-deposit verification reads follow underlying bundle/request read permissions.
10. Verify controlled-evidence verification reads remain limited to `ADMIN` and `AUDITOR`.
11. Verify proof viewer surfaces pass/fail details and metadata coherently.
12. Verify docs match the implemented verification and proof-view behavior.
13. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- bundle verification tooling is real
- append-only verification lineage is real
- auditor-grade proof viewer is real
- valid/invalid verification is deterministic and reviewable
- later deposit-validation and archive workflows can rely on this layer
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

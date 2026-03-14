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
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/phase-08-safe-outputs-export-gateway.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — export request schema, gateway scaffolding, receipt models, storage adapters, infra policies, CI/security tests, UI routes, audit code, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second receipt path, a second export write path, or silent bypasses through convenience APIs, storage credentials, or worker jobs.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for gateway-only egress, receipt lineage, route denial, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that the export gateway is the only door out, approved requests are the only write source to `safeguarded/exports`, and receipts are append-only, service-account-only artefacts.

## Objective
Enforce no-bypass egress across UI, API, workers, storage, and operational controls.

This prompt owns:
- the internal gateway receipt API
- append-only export receipt lineage
- projection of request export state from receipt history
- deny-by-default route and storage enforcement for all non-gateway egress paths
- UI blocked states for non-approved or not-yet-exported requests
- route-permission matrix hardening
- gateway-only write enforcement to `safeguarded/exports`
- no-bypass audit and security regression coverage
- operational controls and alertable signals for attempted bypasses

This prompt does not own:
- reviewer dashboard logic
- request submission model
- provenance bundle generation
- public download features
- any external path around the canonical gateway

## Phase alignment you must preserve
From Phase 8 Iteration 8.2 and Phase 11 hardening posture:

### Required backend rules
- block direct candidate-download routes for external release
- allow only approved export requests to write to `safeguarded/exports`
- internal-only gateway receipt API:
  - `POST /internal/export-requests/{exportRequestId}/receipt`
- receipt API is service-account-only
- receipt rows append, never mutate in place
- receipt attachment appends:
  - `REQUEST_RECEIPT_ATTACHED`
  - `REQUEST_EXPORTED`
- export receipt reads:
  - `GET /projects/{projectId}/export-requests/{exportRequestId}/receipt`
  - `GET /projects/{projectId}/export-requests/{exportRequestId}/receipts`
- successful gateway delivery projects request to terminal `EXPORTED`
- there is no user-facing `GET /download` bypass route
- user-facing routes cannot attach or overwrite receipts

### Existing receipt schema
Use or reconcile:
- `export_receipts`
  - `attempt_number`
  - `supersedes_receipt_id`
  - `superseded_by_receipt_id`
  - `receipt_key`
  - `receipt_sha256`
  - `created_by`
  - `created_at`
  - `exported_at`

### Existing access rules
- receipt reads inherit request-detail permissions
- `AUDITOR` remains read-only
- only internal gateway service account can attach receipts

### Existing security gate
- route-permission matrix denies non-gateway export paths by default

## Implementation scope

### 1. Canonical internal receipt API
Implement or refine:
- `POST /internal/export-requests/{exportRequestId}/receipt`

Requirements:
- service-account-only authentication/authorization
- no user-facing equivalent
- append-only receipt creation
- request projection updates:
  - `receipt_id`
  - `receipt_key`
  - `receipt_sha256`
  - `receipt_created_by`
  - `receipt_created_at`
  - `exported_at`
- event emission:
  - `REQUEST_RECEIPT_ATTACHED`
  - `REQUEST_EXPORTED`
- no mutation of prior receipt history

### 2. Receipt lineage and reads
Implement or refine:
- current receipt read
- receipt history read

Requirements:
- receipt history remains append-only
- corrected or repeated receipts supersede earlier rows instead of mutating them
- request detail surfaces show current receipt projection plus history where allowed
- no raw storage-key leakage
- no second receipt model

### 3. UI no-bypass blocked states
Refine requester/reviewer UI to make bypass impossible and blocked states explicit.

Requirements:
- non-approved requests show blocked state
- approved but not-yet-exported requests show awaiting-gateway state
- no direct download buttons or hidden links
- receipt surfaces appear only when a receipt exists and permissions allow it
- no “copy internal path” or similar bypass affordance

### 4. Storage and worker enforcement
Harden storage and worker boundaries.

Requirements:
- only gateway identity can write to `safeguarded/exports`
- non-gateway workers and APIs cannot write exportable artefacts there
- configuration, IAM/policy, or internal guard layer encodes this explicitly
- any internal helper jobs remain denied unless acting as the gateway identity
- no convenience storage adapter bypass exists

### 5. Route-permission matrix hardening
Enforce deny-by-default.

Requirements:
- candidate and bundle routes cannot be used as public or external release paths
- no user-facing attachment or streaming endpoint bypasses approval + gateway receipt flow
- route matrix is explicit and test-backed
- unauthorized or disallowed paths fail closed and log safely

### 6. Operational controls and alerts
Add no-bypass operational safety.

Requirements:
- attempted bypasses are auditable
- security/ops logs remain privacy-safe
- repeated receipt corrections remain lineage-safe
- system can surface or alert on bypass attempts or forbidden write attempts
- docs explain the operational meaning of these signals

### 7. Security and regression coverage
Add or refine no-bypass test coverage.

At minimum cover:
- candidate/bundle direct download attempts blocked
- only gateway service account can attach receipts
- non-gateway writes to `safeguarded/exports` denied
- repeated receipts supersede rather than mutate
- successful gateway delivery projects `EXPORTED` while preserving approval lineage
- receipt reads are permissioned correctly
- route-permission matrix denies non-gateway export paths by default

### 8. Documentation
Document:
- gateway-only egress contract
- receipt lineage rules
- blocked UI states
- storage and worker enforcement boundaries
- operational alerting for attempted bypasses
- how later export/provenance phases must continue to respect the single door out

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / infra / contracts
- internal receipt API
- append-only receipt lineage
- request projection updates
- storage and worker enforcement rules
- route-permission matrix hardening
- tests

### Web
- blocked non-export states
- receipt/history read surfaces
- no direct download affordances

### Docs
- no-bypass egress and receipt-lineage doc
- gateway-only operational control doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**`
- storage adapters/config used by the repo
- `/infra/**`
- `/web/**`
- `/packages/contracts/**`
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- reviewer dashboard features
- provenance bundle generation
- public export downloads
- any second export write path
- any second receipt model

## Testing and validation
Before finishing:
1. Verify only the internal gateway service account can attach receipts.
2. Verify user-facing routes cannot attach or overwrite receipts.
3. Verify candidate and bundle direct-download bypasses are blocked.
4. Verify only gateway identity can write to `safeguarded/exports`.
5. Verify repeated or corrected receipts append new rows and supersede older receipts.
6. Verify successful receipt attachment projects request to terminal `EXPORTED`.
7. Verify receipt reads obey request-detail permissions and keep `AUDITOR` read-only.
8. Verify route-permission matrix denies non-gateway egress by default.
9. Verify docs match the implemented no-bypass and receipt-lineage behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the gateway is the only technical egress path
- receipt attachment is service-account-only and append-only
- non-gateway routes and storage paths are blocked
- UI does not offer bypass affordances
- no-bypass enforcement is test-backed and operationally visible
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

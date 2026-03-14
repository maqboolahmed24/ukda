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
   - `/phases/phase-08-safe-outputs-export-gateway.md`
3. Then review the current repository generally — export request schemas, review-stage schemas, dashboard routes, release-pack reads, audit events, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second export-approval workflow, a second review history model, or conflicting request-status semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for review-stage order, dual-review requirements, rationale capture, immutable state changes, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that export approval is append-only, optimistic-lock-safe, and dual-review aware for high-risk requests.

## Objective
Implement export approval workflow with dual control, rationale capture, and immutable state changes.

This prompt owns:
- exact review-stage state transitions
- dual-control enforcement for high-risk export requests
- rationale capture for approve / reject / return decisions
- immutable request-status and review-history projection behavior
- request-approval locking semantics
- request detail and review surfaces that expose these states clearly
- append-only event consistency between request-level and stage-level history

This prompt does not own:
- release-pack generation
- no-bypass egress enforcement
- retention operations
- provenance or bundle workflows
- a second review queue or second approval model

## Phase alignment you must preserve
From Phase 8 Iteration 8.1:

### Existing canonical review models
Use or reconcile:
- `export_requests`
- `export_request_events`
- `export_request_reviews`
- `export_request_review_events`

### Existing stage rules
- stages are `PRIMARY` and, when required, `SECONDARY`
- decisions are `APPROVE | REJECT | RETURN`
- request-level status projects from append-only request events plus current review-stage projection
- stale `reviewEtag` values must be rejected for claim, release, start, and decision writes
- start-review applies only to the current active required stage
- requester cannot approve their own request
- `AUDITOR` is read-only on release-review surfaces

### Existing APIs
Use or refine:
- `GET /projects/{projectId}/export-review?...`
- `GET /projects/{projectId}/export-requests/{exportRequestId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/events`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/reviews`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/reviews/{reviewId}/claim`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/reviews/{reviewId}/release`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/start-review`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/decision`

### Existing reviewer permissions
- `REVIEWER` and `ADMIN` can claim/release/start/approve/reject/return
- `AUDITOR` is read-only
- `PROJECT_LEAD` and `RESEARCHER` have no review-stage mutation actions in this workflow

### High-risk dual-review rules
- `review_path = DUAL` and `requires_second_review = true` for high-risk requests
- a request cannot project to `APPROVED` until both required review stages are approved
- the secondary reviewer must differ from the primary reviewer
- a `RETURNED` or `REJECTED` decision from the active required stage is terminal for that request revision

### Rationale rules
- reject requires `decision_reason`
- return requires `return_comment`
- approval rationale must be captured through the canonical stage event and review projection fields without inventing a second hidden rationale channel
- rationale history must remain append-only and auditable

## Implementation scope

### 1. Canonical review-state transition engine
Implement or refine one canonical transition path for:
- claim
- release
- start review
- approve
- reject
- return

Requirements:
- use the existing `reviewEtag` optimistic-concurrency contract
- reject invalid stage/order transitions
- keep request-level status as a projection from append-only request events and stage projections
- no route-local status mutations that bypass the canonical path

### 2. Dual-control enforcement
Implement exact dual-control behavior.

Requirements:
- primary and secondary review stages are explicit
- same-user second review is blocked
- dual-review requests do not reach `APPROVED` until both required stages approve
- dual-review state is visible and typed
- terminal returns/rejections close the request revision truthfully

### 3. Rationale capture
Implement or refine rationale capture without adding a shadow model.

Requirements:
- reject captures `decision_reason`
- return captures `return_comment`
- approval may capture a reviewer note through the canonical event/review structure if the repo already supports it cleanly, but it must not become a separate mutable store
- rationale surfaces remain exact, auditable, and immutable in history
- no hidden reviewer notes or private side channels

### 4. Immutable request and review history
Harden append-only history.

Requirements:
- `export_request_events` remain the request-history source of truth
- `export_request_review_events` remain the stage-history source of truth
- projections on `export_requests` and `export_request_reviews` are read models only
- history must be reconstructable after mutable projections change
- no in-place rewriting of historical decisions

### 5. Request detail and review detail refinement
Refine the current UI so reviewers and auditors can understand:
- active stage
- assigned reviewer
- decision rationale
- review-path (`SINGLE` vs `DUAL`)
- status transitions
- immutable history
- blocked next actions

Keep the UI dense, calm, and exact. Do not turn it into a giant workflow wizard.

### 6. Approval locking semantics
Implement or refine lock behavior.

Requirements:
- once a request revision reaches terminal `APPROVED`, `REJECTED`, or `RETURNED`, later decision mutation on that same active stage is blocked
- any future changes require the canonical resubmission or successor path, not in-place mutation
- request detail clearly reflects terminal lock state

### 7. Audit alignment
Use the canonical audit path and emit or reconcile:
- `EXPORT_REVIEW_QUEUE_VIEWED`
- `EXPORT_REQUEST_REVIEW_CLAIMED`
- `EXPORT_REQUEST_REVIEW_STARTED`
- `EXPORT_REQUEST_APPROVED`
- `EXPORT_REQUEST_REJECTED`
- `EXPORT_REQUEST_RETURNED`
- `EXPORT_REQUEST_REVIEWS_VIEWED`
- `EXPORT_REQUEST_REVIEW_EVENTS_VIEWED`

Do not create a second audit path.

### 8. Documentation
Document:
- review-stage lifecycle
- dual-control enforcement
- rationale capture rules
- immutable history/projection rules
- what Prompt 82 will deepen around operations, aging, and retention

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- review transition engine
- dual-control enforcement
- rationale capture and history consistency
- tests

### Web
- request detail and review detail refinement
- clear stage/rationale/history surfaces
- blocked-state and lock-state presentation

### Docs
- export approval workflow and dual-control doc
- rationale capture and immutable history doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small review/timeline/status refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- release-pack generation
- no-bypass gateway enforcement
- retention jobs
- provenance workflows
- a second approval workflow

## Testing and validation
Before finishing:
1. Verify invalid state transitions are blocked.
2. Verify stale `reviewEtag` writes are rejected safely.
3. Verify same-user second review is rejected when dual review is required.
4. Verify high-risk requests cannot project to `APPROVED` until distinct primary and secondary reviewers approve.
5. Verify reject and return rationale requirements are enforced.
6. Verify append-only history remains reconstructable after mutable projection updates.
7. Verify requester self-approval is blocked.
8. Verify review-stage mutation RBAC boundaries: only `REVIEWER` and `ADMIN` can claim/release/start/decide; `AUDITOR`, `PROJECT_LEAD`, and `RESEARCHER` remain read-only on review-stage mutations.
9. Verify docs match the implemented approval and history behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- export approval workflow is real
- dual control is real
- rationale capture is real
- immutable state changes and history are real
- reviewers and auditors can trust the approval lineage
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

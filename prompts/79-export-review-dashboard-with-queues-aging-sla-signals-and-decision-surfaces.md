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
   - `/phases/phase-08-safe-outputs-export-gateway.md`
3. Then review the current repository generally — export request schema, release-pack surfaces, review-stage tables/events, current routes, typed contracts, audit code, browser tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second reviewer queue, a second decision workflow, or hidden SLA state outside the canonical export request and review tables.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for reviewer dashboard behavior, review-stage workflow, SLA fields, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that review stages, claims, releases, starts, and decisions are optimistic-lock-safe, read-only for `AUDITOR`, and dual-review aware for high-risk requests.

## Objective
Create the export-review dashboard with queues, aging, SLA signals, and decision surfaces for reviewers.

This prompt owns:
- reviewer dashboard and queue
- claim/release/start-review decision workflow UI
- decision surfaces for approve/reject/return
- aging and SLA indicators
- project and requester history views where phase calls for them
- queue filters by status, aging bucket, and reviewer
- read-only `AUDITOR` queue access
- dual-review surfacing for high-risk exports

This prompt does not own:
- gateway receipt attachment
- no-bypass storage enforcement
- retention jobs themselves
- provenance/export packaging
- a second review system

## Phase alignment you must preserve
From Phase 8 Iteration 8.1 and 8.3:

### Reviewer queue route
- `/projects/:projectId/export-review?status={status}&agingBucket={agingBucket}&reviewerUserId={reviewerUserId}`

### Reviewer permissions
- `REVIEWER` and `ADMIN`:
  - claim
  - release
  - start review
  - approve
  - reject
  - return
- `AUDITOR`:
  - read-only access to queue, release packs, and histories
- requester cannot approve their own request
- high-risk requests with `requires_second_review = true` need distinct primary and secondary reviewers, and decision writes must enforce this

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
- write contract for `start-review` and `decision`: request payload must include current active-stage `reviewId` and `reviewEtag`; stale etag or stage mismatch fails with typed conflict

### Existing state and SLA fields
Use or refine:
- `first_review_started_at`
- `sla_due_at`
- `last_queue_activity_at`
- `retention_until`

### Required UX
- queue by status
- release-pack view
- decision timeline
- aging indicators
- decision notes panel
- export history by project and requester
- calm, dense, review-grade UI

## Implementation scope

### 1. Reviewer dashboard shell
Implement or refine the canonical reviewer dashboard.

Requirements:
- one coherent export-review queue
- status filters
- aging bucket filter
- reviewer filter
- dense queue rows with clear state
- read-only mode for `AUDITOR`
- no second admin-only queue path

### 2. Claim, release, and start-review flows
Implement or refine the reviewer interaction flow.

Requirements:
- claim uses `reviewEtag`
- release uses `reviewEtag`
- start-review uses current active-stage `reviewEtag`
- start-review applies only to current active required stage
- start-review requires that the stage is either unassigned and atomically claimed or already assigned to the caller
- stale `reviewEtag` conflicts are surfaced calmly and exactly
- no silent reviewer overwrite

### 3. Decision surfaces
Implement or refine approve/reject/return flows.

Requirements:
- approve/reject/return decisions use current active-stage `reviewEtag` and fail on stale writes
- exact reason capture for reject or return
- dual-review status visible on high-risk requests
- `AUDITOR` sees read-only decision surfaces
- requester self-approval blocked
- no noisy workflow theatrics

### 4. Queue aging and SLA signals
Surface operational timing clearly.

Requirements:
- aging indicators
- SLA due signals
- last-activity visibility
- first-review-started state
- project and requester history read surfaces where useful
- no fake “healthy” badge when timing is slipping

### 5. Decision timeline and release-pack detail
Refine reviewer context.

Requirements:
- release-pack view in context
- decision timeline
- review-stage history
- request history by requester/project when useful
- queue-to-detail-to-return-to-queue flow is coherent
- no second detail shell

### 6. Dual-review and reviewer-role truth
Make high-risk paths explicit.

Requirements:
- high-risk queue rows indicate dual-review requirement
- second-review state is visible
- same reviewer cannot satisfy both stages
- queue and detail surfaces show which stage is active
- return/reject remain terminal for that request revision

### 7. Browser quality and accessibility
Add or refine browser coverage.

At minimum cover:
- queue default
- claimed state
- in-review state
- return flow
- approve flow
- reject flow
- auditor read-only queue
- aging/SLA indicators
- keyboard and focus behavior
- visual baselines for primary review states

### 8. Documentation
Document:
- export-review dashboard ownership
- review-stage interaction rules
- SLA/aging surface semantics
- read-only auditor behavior
- how Prompt 80 will enforce no-bypass egress under this workflow

## Required deliverables
Create or refine the closest coherent equivalent of:

### Web
- export-review dashboard
- claim/release/start-review flows
- approve/reject/return surfaces
- queue aging and SLA indicators
- decision timeline and release-pack detail
- browser tests and visual baselines

### Backend / contracts
- only tiny helper or typed read/write refinements if strictly needed for the canonical reviewer workflow

### Docs
- export-review dashboard UX contract doc
- SLA, aging, and review-stage workflow doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/web/**`
- `/api/**` only if tiny helper/typed refinements are strictly needed
- `/packages/contracts/**`
- `/packages/ui/**`
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- gateway receipt attachment
- storage no-bypass enforcement
- retention-job implementation
- provenance/export packaging
- a second review queue

## Testing and validation
Before finishing:
1. Verify claim/release/start-review/decision writes use optimistic concurrency and reject stale `reviewEtag` writes.
2. Verify `AUDITOR` is read-only.
3. Verify requester cannot approve own request.
4. Verify high-risk dual-review state is surfaced correctly and same-reviewer dual-approval attempts are rejected.
5. Verify aging and SLA indicators are computed and displayed coherently.
6. Verify decision reason requirements for reject/return.
7. Verify queue/detail/history flows remain coherent and keyboard-safe.
8. Verify docs match the implemented dashboard and reviewer workflow.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the reviewer dashboard is real
- decision flows are real
- SLA and aging signals are real
- `AUDITOR` stays read-only
- high-risk dual-review paths are visible and coherent
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

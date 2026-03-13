# Phase 8: Safe Outputs Workflow + Export Gateway v1 - The Only Exit

> Status: ACTIVE
> Web Root: /web
> Active Phase Ceiling: 11
> Execution Policy: Phase 0 through Phase 11 are ACTIVE for this prompt program.
> Web Translation Overlay (ACTIVE): preserve existing workflow intent and phase semantics while translating any legacy desktop or WinUI terms into equivalent browser-native routes, layouts, and interaction patterns under /web.

## Phase Objective
Force all external releases through a formal output-review workflow that acts as the only egress path from the secure environment.

## Entry Criteria
Start Phase 8 only when all are true:
- candidate outputs are governance-ready under Phase 6, or policy-pinned under Phase 7 when project-specific reruns are in use
- policy-controlled rendering from Phase 7 is stable enough to submit for review when a project is using explicit Phase 7 policies
- project purpose and requester identity are available for release decisions

## Scope Boundary
Phase 8 owns disclosure review, export requests, and egress enforcement.

Out of scope for this phase:
- provenance proofs and deposit packaging (Phase 9)
- search and derivative data products (Phase 10)

## Phase 8 Non-Negotiables
- Secure web application is the active delivery target: preserve phase behavior and governance contracts while implementing browser-native interaction, routing, and layout patterns from first principles (no desktop-mechanics carryover).
- All workspace and page surfaces inherit the canonical `Obsidian Folio` experience contract (dark-first Fluent 2 tokens, app-window adaptive states, single-fold defaults, keyboard-first accessibility); see `ui-premium-dark-blueprint-obsidian-folio.md`.
1. No candidate artefact becomes exportable without an approved output-review record.
2. Export requests operate on immutable candidate snapshots, not live working files.
3. Returned or rejected requests remain internal and cannot be downloaded externally.
4. The export gateway is enforced technically, not only by process.

## Iteration Model
Build Phase 8 in four iterations (`8.0` to `8.3`). Each iteration must strengthen control without creating a release-review bottleneck.

## Iteration 8.0: Export Request Model + Release Pack

### Goal
Make output screening start from a formal request with a deterministic evidence pack.

### Backend Work
Add `export_candidate_snapshots`:
- `id`
- `project_id`
- `source_phase` (`PHASE6`, `PHASE7`, later `PHASE9`, `PHASE10`)
- `source_artifact_kind` (`REDACTION_RUN_OUTPUT | DEPOSIT_BUNDLE | DERIVATIVE_SNAPSHOT`)
- `source_run_id` (nullable when the source artefact is not directly run-based, including Phase 9 bundles and Phase 10 derivative snapshots)
- `source_artifact_id`
- `governance_run_id` (nullable when the source class has no Phase 6 governance basis of its own and instead copies lineage from an earlier candidate)
- `governance_manifest_id` (nullable)
- `governance_ledger_id` (nullable)
- `governance_manifest_sha256` (nullable)
- `governance_ledger_sha256` (nullable)
- `policy_snapshot_hash` (nullable when the source class has no policy basis)
- `policy_id` (nullable when the source class has no explicit Phase 7 policy lineage)
- `policy_family_id` (nullable when the source class has no explicit Phase 7 policy lineage)
- `policy_version` (nullable when the source class has no explicit Phase 7 policy lineage)
- `candidate_kind` (`SAFEGUARDED_PREVIEW`, `POLICY_RERUN`, `DEPOSIT_BUNDLE`, `SAFEGUARDED_DERIVATIVE`)
- `artefact_manifest_json`
- `candidate_sha256`
- `eligibility_status` (`ELIGIBLE | SUPERSEDED`)
- `supersedes_candidate_snapshot_id` (nullable)
- `superseded_by_candidate_snapshot_id` (nullable)
- `created_by`
- `created_at`

Candidate-snapshot rules:
- approved, governance-ready Phase 6 runs register immutable candidate snapshots for their run-level safeguarded output manifests from Phase 5 `redaction_run_outputs`
- Phase 7 reruns register new candidate snapshots instead of mutating earlier ones
- Phase 9 `SAFEGUARDED_DEPOSIT` bundles may be frozen as new candidate snapshots only through an explicit bundle-to-candidate registration step; that creates a distinct candidate lineage and must re-enter full Phase 8 request/review approval instead of inheriting the source candidate's prior approval
- Phase 9 `CONTROLLED_EVIDENCE` bundles never register `export_candidate_snapshots`; they remain internal-only admin/auditor artefacts and are not Phase 8 candidates
- Phase 10 safeguarded derivatives register candidate snapshots only when they are immutable, policy-pinned, and linked to their provenance inputs
- when a candidate becomes obsolete, `eligibility_status=SUPERSEDED` must point at the replacement candidate through the supersession fields rather than leaving the lineage implicit
- `source_artifact_kind` disambiguates what `source_artifact_id` points to, so later provenance, release-pack, and supersession reads do not have to infer table meaning from `candidate_kind` alone
- Phase 6 candidates persist `policy_snapshot_hash` with null explicit policy-lineage fields; Phase 7 and Phase 10 policy-pinned candidates persist `policy_snapshot_hash` plus explicit `policy_id`, `policy_family_id`, and `policy_version`; explicitly registered Phase 9 bundle-derived candidates copy forward the policy lineage that made the bundled source candidate eligible while recording the new bundle-derived source artefact lineage
- candidate registration pins the exact governance artefact pair that made the source eligible at freeze time through `governance_run_id`, `governance_manifest_id`, `governance_ledger_id`, and their hashes; release-pack generation must read those pinned fields instead of following a mutable live governance projection
- `GET /projects/{projectId}/export-candidates/{candidateId}/release-pack` is a pre-submission preview over immutable candidate inputs; once a request is submitted, the review workflow must read the request's frozen release-pack artifact rather than regenerating a live pack from mutable request state

Candidate list or read permissions:
- `RESEARCHER`, `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can list eligible candidate snapshots for their project.
- `AUDITOR` has read-only access to candidate snapshots for governance review.

Add project-scoped APIs:
- `GET /projects/{projectId}/export-candidates`
- `GET /projects/{projectId}/export-candidates/{candidateId}`
- `GET /projects/{projectId}/export-candidates/{candidateId}/release-pack`
- `POST /projects/{projectId}/export-requests`
- `GET /projects/{projectId}/export-requests?status={status}&requesterId={requesterId}&candidateKind={candidateKind}&cursor={cursor}&limit={limit}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/status`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/release-pack`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/events`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/reviews`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/reviews/events`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/reviews/{reviewId}/claim`
  - available only to `REVIEWER` or `ADMIN`; requires the current `reviewEtag`, assigns the stage to the caller when it is unassigned or already assigned to that caller, and appends an append-only review-assignment event
- `POST /projects/{projectId}/export-requests/{exportRequestId}/reviews/{reviewId}/release`
  - available only to the currently assigned reviewer or `ADMIN`; requires the current `reviewEtag`, clears `assigned_reviewer_user_id` only while the stage is still non-terminal, and appends an append-only `REVIEW_RELEASED` event
- `POST /projects/{projectId}/export-requests/{exportRequestId}/start-review`
  - available only to `REVIEWER` or `ADMIN`; requires `reviewId` plus the current `reviewEtag`, applies only to the current active required stage, and rejects attempts to start a later or already completed stage
  - the stage must either already be assigned to the caller or be atomically assigned to that caller as part of the start action; start-review cannot begin a stage assigned to someone else
  - appends an append-only review-start event and updates the current stage projection only when the etag still matches
- `POST /projects/{projectId}/export-requests/{exportRequestId}/resubmit`
  - creates a new request revision linked to the returned request; it never mutates the returned record in place, increments `request_revision`, sets `supersedes_export_request_id` on the new row, and records the forward link on the returned source row through `superseded_by_export_request_id`
  - may reuse the prior `candidate_snapshot_id` when only reviewer notes or metadata changed, or may reference a replacement eligible `candidateId` from the same project when the return requires updated files or a corrected candidate snapshot
  - carries forward the previous `bundle_profile` and `purpose_statement` unless the resubmission payload explicitly replaces them
- `POST /projects/{projectId}/export-requests/{exportRequestId}/decision`
  - requires `reviewId` plus the current `reviewEtag`; accepts `decision = APPROVE | REJECT | RETURN`; `decision_reason` is required for `REJECT` and `return_comment` is required for `RETURN`
  - appends both request-level and review-stage events and updates mutable review/request projections only when the etag still matches, so concurrent reviewers cannot silently overwrite each other

Add `export_requests`:
- `id`
- `project_id`
- `candidate_snapshot_id`
- `candidate_origin_phase`
- `candidate_kind`
- `bundle_profile` (nullable)
- `risk_classification` (`STANDARD | HIGH`)
- `risk_reason_codes_json`
- `review_path` (`SINGLE | DUAL`)
- `requires_second_review`
- `supersedes_export_request_id` (nullable)
- `superseded_by_export_request_id` (nullable)
- `request_revision`
- `purpose_statement`
- `status` (`SUBMITTED | RESUBMITTED | IN_REVIEW | APPROVED | EXPORTED | REJECTED | RETURNED`)
- `submitted_by`
- `submitted_at`
- `first_review_started_by` (nullable)
- `first_review_started_at` (nullable)
- `sla_due_at` (nullable)
- `last_queue_activity_at` (nullable)
- `retention_until` (nullable)
- `final_review_id` (nullable)
- `final_decision_by` (nullable)
- `final_decision_at` (nullable)
- `final_decision_reason` (nullable)
- `final_return_comment` (nullable)
- `release_pack_key`
- `release_pack_sha256`
- `release_pack_created_at`
- `receipt_id` (nullable)
- `receipt_key` (nullable)
- `receipt_sha256` (nullable)
- `receipt_created_by` (nullable)
- `receipt_created_at` (nullable)
- `exported_at` (nullable)

Add `export_request_events`:
- `id`
- `export_request_id`
- `event_type` (`REQUEST_SUBMITTED | REQUEST_REVIEW_STARTED | REQUEST_RESUBMITTED | REQUEST_APPROVED | REQUEST_EXPORTED | REQUEST_REJECTED | REQUEST_RETURNED | REQUEST_RECEIPT_ATTACHED | REQUEST_REMINDER_SENT | REQUEST_ESCALATED`)
- `from_status` (nullable)
- `to_status`
- `actor_user_id`
- `reason` (nullable)
- `created_at`

Add `export_receipts`:
- `id`
- `export_request_id`
- `attempt_number`
- `supersedes_receipt_id` (nullable)
- `superseded_by_receipt_id` (nullable)
- `receipt_key`
- `receipt_sha256`
- `created_by`
- `created_at`
- `exported_at`

Add `export_request_reviews`:
- `id`
- `export_request_id`
- `review_stage` (`PRIMARY | SECONDARY`)
- `is_required`
- `status` (`PENDING | IN_REVIEW | APPROVED | RETURNED | REJECTED`)
- `assigned_reviewer_user_id` (nullable)
- `assigned_at` (nullable)
- `acted_by_user_id` (nullable)
- `acted_at` (nullable)
- `decision_reason` (nullable)
- `return_comment` (nullable)
- `review_etag`
- `created_at`
- `updated_at`

Add `export_request_review_events`:
- `id`
- `review_id`
- `export_request_id`
- `review_stage`
- `event_type` (`REVIEW_CREATED | REVIEW_CLAIMED | REVIEW_STARTED | REVIEW_APPROVED | REVIEW_REJECTED | REVIEW_RETURNED | REVIEW_RELEASED`)
- `actor_user_id`
- `assigned_reviewer_user_id` (nullable)
- `decision_reason` (nullable)
- `return_comment` (nullable)
- `created_at`

`export_requests.status`, `final_review_id`, `final_decision_by`, `final_decision_at`, `final_decision_reason`, and `final_return_comment` are current projections derived from append-only `export_request_events` plus the acted review row in `export_request_reviews`; stage-level decisions are not stored as independent sources of truth on the request row.
`export_request_reviews` is the mutable current-stage projection only. Append-only `export_request_review_events` is the source of truth for assignment, start, and decision history within each review stage.
request submission materializes an immutable request-scoped release pack artifact under `release_pack_key` plus `release_pack_sha256`; review, approval, and later provenance or bundle reads for that request use the frozen request-level release pack rather than regenerating a live pack from mutable request metadata
`export_requests.receipt_id`, `receipt_key`, `receipt_sha256`, `receipt_created_by`, `receipt_created_at`, and `exported_at` are current projections from append-only `export_receipts`; attaching or correcting a receipt appends a new receipt row and supersedes the earlier receipt lineage instead of mutating receipt bytes in place.
`REQUEST_REVIEW_STARTED` is emitted when a `REVIEWER` or `ADMIN` actively takes a request into review and projects the current request status to `IN_REVIEW`.
`REQUEST_RESUBMITTED` is the append-only event emitted on the newly created successor request revision. The returned predecessor remains terminal for its own revision, while the new revision starts in `RESUBMITTED` until the next review action begins.
`REQUEST_EXPORTED` is emitted only after the internal gateway persists an append-only `export_receipts` row for successful delivery; that event projects the request from `APPROVED` to terminal `EXPORTED`.
Only `RETURNED` requests can be resubmitted. `APPROVED` and `REJECTED` requests are terminal. Resubmission is limited to the original requester, `PROJECT_LEAD`, or `ADMIN` for the same project.
Returned requests that depend on changed files or corrected derivatives must resubmit against a replacement eligible candidate snapshot; resubmission is rejected if it points at a superseded, cross-project, or non-eligible candidate.
resubmission appends a fresh set of `export_request_reviews` stage rows for the successor request revision, recalculates `review_path` and `requires_second_review` from the successor revision's pinned release-pack classifier result, and appends new `REVIEW_CREATED` stage events with fresh `review_etag` values instead of reusing mutable review rows from the returned predecessor
`reviewerUserId` queue filtering reads the current `assigned_reviewer_user_id` from `export_request_reviews`. Assignment happens only through `POST /reviews/{reviewId}/claim`, `POST /reviews/{reviewId}/release`, or `POST /start-review`, not by implicit UI-local state.
Request risk classification is deterministic in v1 and is pinned at submission time from the release-pack classifier:
- `HIGH` when any of the following are true:
  - `candidate_kind` is `DEPOSIT_BUNDLE` or `SAFEGUARDED_DERIVATIVE`
  - the release pack reports any manual reviewer override count greater than `0`
  - the release pack reports any conservative area-mask count greater than `0`
  - the release pack reports special-category, indirect-risk, or policy-escalation flags
  - the requested `bundle_profile` is marked by policy as dual-review-required
- `STANDARD` otherwise
High-risk requests persist `review_path = DUAL` and `requires_second_review = true` before the first decision action is allowed. Those requests cannot project to `APPROVED` until both required review stages are `APPROVED`, and the secondary reviewer must differ from the primary reviewer. A `RETURNED` or `REJECTED` decision from the currently active required stage remains terminal for that revision and closes any still-pending later review stage.

List/read permissions:
- `RESEARCHER` can list and read only their own export requests inside a project.
- `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can list and read all export requests for the project.
- `AUDITOR` has read-only access to project export requests and related release packs.
- export-receipt reads inherit the same request-detail permissions after a receipt exists.

Release pack includes:
- file list, sizes, and hashes
- candidate snapshot ID and request revision
- baseline policy snapshot hash or Phase 7 policy version
- candidate source-artifact kind and immutable source-artifact reference
- approved model references by role, including the active transcription model and any fallback or privacy model lineage used to derive the candidate
- approved model checksums or immutable version references for every included role
- redaction counts by category
- reviewer override count
- conservative area-mask count
- risk flags and classifier reason codes
- manifest hash and integrity status
- pinned governance manifest and ledger references from the frozen candidate snapshot lineage
- release-review checklist
- every request-scoped release pack is persisted as immutable bytes and addressed by the request's `release_pack_key` plus `release_pack_sha256`

### Web Client Work
- `/projects/:projectId/export-candidates`
- `/projects/:projectId/export-candidates/:candidateId`
- `/projects/:projectId/export-requests`
- `/projects/:projectId/export-requests/new?candidateId={candidateId}`
- `/projects/:projectId/export-requests/:exportRequestId`
- `/projects/:projectId/export-requests/:exportRequestId/reviews`
- `/projects/:projectId/export-requests/:exportRequestId/events`
- `/projects/:projectId/export-requests/:exportRequestId/reviews/events`
- `/projects/:projectId/export-review?status={status}&agingBucket={agingBucket}&reviewerUserId={reviewerUserId}`
- export request wizard:
  - candidate selection
  - purpose statement
  - release-pack preview backed by `GET /projects/{projectId}/export-candidates/{candidateId}/release-pack`
- `/projects/:projectId/export-requests` shows only the caller's requests for `RESEARCHER`, while `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` get the project-wide request list
- export history by project and requester is backed by `GET /projects/{projectId}/export-requests?status={status}&requesterId={requesterId}&candidateKind={candidateKind}&cursor={cursor}&limit={limit}`
- export request detail loads its review pack from `GET /projects/{projectId}/export-requests/{exportRequestId}/release-pack`
- export request detail polls `GET /projects/{projectId}/export-requests/{exportRequestId}/status` for SLA and review-state updates, and its decision timeline reads `GET /projects/{projectId}/export-requests/{exportRequestId}/events`
- export request review-stage history reads `GET /projects/{projectId}/export-requests/{exportRequestId}/reviews/events`, while `GET /projects/{projectId}/export-requests/{exportRequestId}/reviews` returns the current stage projections with `reviewEtag` values for claim/release/start/decision actions
- returned request detail page exposes a `Resubmit` action only to the original requester, `PROJECT_LEAD`, or `ADMIN`

### Tests and Gates (Iteration 8.0)
#### Unit
- requests cannot be created for non-immutable candidates
- release-pack integrity matches actual candidate files

#### Integration
- project scoping is enforced for request creation and read access
- export-candidate listing returns only immutable `ELIGIBLE` snapshots
- export-candidate detail only reveals candidates inside the caller's authorized project scope
- `RESEARCHER`, `PROJECT_LEAD`, `REVIEWER`, or `ADMIN` can submit requests for their project; only `REVIEWER` or `ADMIN` can start review or decide; `AUDITOR` remains read-only
- returned requests can be resubmitted either against the same candidate or against a replacement eligible candidate from the same project, but never against a superseded or cross-project candidate
- request creation pins `risk_classification` and `risk_reason_codes_json` from the release-pack classifier, so dual-review eligibility is reproducible instead of inferred ad hoc by reviewers
- request submission persists an immutable request-scoped release pack artifact, and review/detail reads for that request use the frozen `release_pack_key` plus `release_pack_sha256`
- resubmission creates a fresh set of `export_request_reviews` rows with new `review_etag` values for the successor request revision instead of reusing mutable review projections from the returned predecessor
- Audit events emitted:
  - `EXPORT_CANDIDATES_VIEWED`
  - `EXPORT_CANDIDATE_VIEWED`
  - `EXPORT_RELEASE_PACK_VIEWED`
  - `EXPORT_REQUEST_SUBMITTED`
  - `EXPORT_HISTORY_VIEWED`
  - `EXPORT_REQUEST_VIEWED`
  - `EXPORT_REQUEST_STATUS_VIEWED`
  - `EXPORT_REQUEST_EVENTS_VIEWED`
  - `EXPORT_REQUEST_REVIEWS_VIEWED`
  - `EXPORT_REQUEST_REVIEW_EVENTS_VIEWED`
  - `EXPORT_REQUEST_REVIEW_CLAIMED`
  - `EXPORT_REQUEST_REVIEW_STARTED`
  - `EXPORT_REQUEST_RETURNED`
  - `EXPORT_REQUEST_RESUBMITTED`
  - `EXPORT_REQUEST_APPROVED`
  - `EXPORT_REQUEST_REJECTED`

### Exit Criteria (Iteration 8.0)
Output review begins from a formal request and an immutable release pack.

## Iteration 8.1: Reviewer Dashboard + Decision Workflow

### Goal
Give release reviewers (`REVIEWER`, `ADMIN`) and read-only governance observers (`AUDITOR`) a dedicated queue and decision surface instead of ad hoc review.

### Web Client Work
- reviewer dashboard (`REVIEWER`, `ADMIN`, and read-only `AUDITOR`):
  - queue by status
  - release-pack view
  - decision timeline
- decision actions:
  - `Approve`
  - `Reject`
  - `Return for changes`

`AUDITOR` access is read-only; claim, decision, and review-start actions are available only to `REVIEWER` and `ADMIN`.

### Backend Work
- reviewer queue API:
  - `GET /projects/{projectId}/export-review?status={status}&agingBucket={agingBucket}&reviewerUserId={reviewerUserId}`
    - readable by `REVIEWER`, `ADMIN`, and read-only `AUDITOR`; queue rows remain read-only for `AUDITOR`
- review assignment API:
  - `POST /projects/{projectId}/export-requests/{exportRequestId}/reviews/{reviewId}/claim`
    - requires the current `reviewEtag`; claims the active review stage for the caller and records `assigned_reviewer_user_id`
- review release API:
  - `POST /projects/{projectId}/export-requests/{exportRequestId}/reviews/{reviewId}/release`
    - requires the current `reviewEtag`; available only to the assigned reviewer or `ADMIN`, and only while the stage remains non-terminal
- review start API:
  - `POST /projects/{projectId}/export-requests/{exportRequestId}/start-review`
- review and decision writes use optimistic concurrency through `reviewEtag`; stale claim, release, start, or decision submissions are rejected instead of last-write-wins
- claim, release, start, and decision actions must target the current active required stage; callers cannot start or decide a future stage out of order
- start-review requires that the targeted stage is either unassigned and atomically claimed by the caller, or already assigned to that same caller
- decision reasons required for reject or return
- high-risk exports use an explicit dual-review path driven by `export_requests.review_path` and `requires_second_review`
- immutable request history stored in `export_request_events`
- stage assignment and stage outcomes persist in `export_request_reviews`, while append-only stage history persists in `export_request_review_events`
- requester cannot approve their own export request
- enforce read-only access for `AUDITOR` on release-decision surfaces
- queue reads emit `EXPORT_REVIEW_QUEUE_VIEWED`

### Tests and Gates (Iteration 8.1)
#### Unit
- invalid state transitions are blocked
- reason requirement is enforced
- `AUDITOR` can view release packs but cannot approve, reject, or return requests
- high-risk requests with `requires_second_review = true` cannot project to `APPROVED` until distinct primary and secondary reviewers have both approved
- risk classification is deterministic from the pinned release-pack fields and does not depend on ad hoc reviewer judgment at review time
- stale `reviewEtag` values are rejected for claim, release, review-start, and decision writes so concurrent reviewers cannot silently overwrite each other
- stage review history remains reconstructable from `export_request_review_events` even after mutable review projections change
- reviewer queue filters by `reviewerUserId` resolve against persisted `assigned_reviewer_user_id`, not client-local assignment state
- review-start rejects stages assigned to another reviewer and rejects attempts to start a non-current required stage

#### E2E
- `RESEARCHER` submits, `REVIEWER` starts review, `REVIEWER` returns, `RESEARCHER` creates a linked resubmission through `POST /projects/{projectId}/export-requests/{exportRequestId}/resubmit`, `REVIEWER` starts review again, then approves
- the request-lineage timeline shows `REQUEST_SUBMITTED -> REQUEST_REVIEW_STARTED -> REQUEST_RETURNED -> REQUEST_RESUBMITTED -> REQUEST_REVIEW_STARTED -> REQUEST_APPROVED`, while the returned source revision remains `RETURNED` and the successor revision moves `RESUBMITTED -> IN_REVIEW -> APPROVED`

### Exit Criteria (Iteration 8.1)
Authorized release reviewers can complete release decisions entirely inside the platform.

## Iteration 8.2: No-Bypass Egress Enforcement

### Goal
Make the gateway the only path by which approved files can leave the environment.

### Backend Work
- block direct candidate-download routes for external release
- allow only approved export requests to write to `safeguarded/exports`
- persist signed export receipt with request record
- internal-only gateway receipt API:
  - `POST /internal/export-requests/{exportRequestId}/receipt`
    - service-account-only
    - appends a new `export_receipts` row, supersedes any prior receipt row for that request, projects the current receipt fields on `export_requests`, and persists `receipt_sha256`, `receipt_created_by`, `receipt_created_at`, and `exported_at`
    - appends `REQUEST_RECEIPT_ATTACHED` and `REQUEST_EXPORTED` to `export_request_events` and emits `EXPORT_COMPLETED`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/receipt`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/receipts`
- receipt reads inherit request-detail permissions, keep `AUDITOR` read-only, and never create a bypass download route
- receipt persistence records `receipt_created_by`, `receipt_created_at`, and `exported_at`
- attaching a receipt appends new `export_receipts` and request-event rows without rewriting the existing approval or request-submission history
- there is no user-facing POST or PATCH receipt-attachment route
- gateway delivery remains an internal service-account action; there is no user-facing `GET /download` bypass route

### Web Client Work
- approved request page exposes export receipt and final package summary
- non-approved requests show explicit blocked state instead of silent failure

### Tests and Gates (Iteration 8.2)
#### Integration
- no-bypass enforcement for candidate and bundle routes
- only export gateway writes exportable artefacts
- user-facing project routes cannot attach or overwrite receipts; only the internal gateway service account can call the receipt-write API
- repeated or corrected gateway receipts append a new `export_receipts` row and supersede the older receipt instead of mutating receipt history in place
- successful gateway delivery projects the request to terminal `EXPORTED` status while preserving the earlier approval lineage in `export_request_events`
- receipt reads emit `EXPORT_RECEIPT_VIEWED`
- successful gateway delivery emits `EXPORT_COMPLETED`

#### Security
- route-permission matrix denies non-gateway export paths by default

### Exit Criteria (Iteration 8.2)
There is one auditable and technically enforced door out of the platform.

## Iteration 8.3: Operations, SLA Tracking, and Retention

### Goal
Make output review operationally sustainable rather than a hidden queue.

### Backend Work
- queue aging timestamps
- reminder and escalation events
- retention rules for stale, rejected, and approved requests
- `first_review_started_at`, `sla_due_at`, `last_queue_activity_at`, and `retention_until` are computed and persisted from queue entry, review-claim, review-start, reminder, escalation, decision, receipt-attachment, and retention-policy events

### Web Client Work
- queue aging indicators
- decision notes panel
- export history by project and requester

### Tests and Gates (Iteration 8.3)
#### Integration
- SLA timers compute consistently
- retention jobs do not delete audit-critical records
- review-claim events update `last_queue_activity_at` so claimed-but-not-started requests remain operationally visible

### Exit Criteria (Iteration 8.3)
The export workflow is safe, observable, and operable at steady state.

## Handoff to Later Phases
- Phase 9 adds lineage proofs and deposit-ready packaging on top of Phase 8-approved outputs, but any released bundle still exits through the same Phase 8 approval record and gateway.
- Phase 10 may consume approved outputs and Controlled data products, but must not bypass Phase 8 for release.

## Phase 8 Definition of Done
Move to Phase 9 only when all are true:
1. Every exportable package is tied to an approved export request and release pack.
2. Direct download bypasses are blocked technically, not just procedurally.
3. Release decisions, reasons, and receipts are audit-complete.
4. Returned and rejected requests remain internal-only.
5. Queue visibility and SLA tracking are good enough for continuous operation.

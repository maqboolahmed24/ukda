# Export Review Dashboard SLA And Decision Workflow Contract

Status: Prompt 79  
Scope: Phase 8.1 and 8.3 reviewer queue, decision workflow, and SLA-facing surfaces

## Route ownership

Reviewer workflow route family:

- `/projects/:projectId/export-review?status={status}&agingBucket={agingBucket}&reviewerUserId={reviewerUserId}`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/reviews/{reviewId}/claim`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/reviews/{reviewId}/release`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/start-review`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/decision`

Requester history and release-pack read routes remain the same Phase 8.0 contract:

- `/projects/:projectId/export-requests`
- `/projects/:projectId/export-requests/:exportRequestId`
- `/projects/:projectId/export-requests/:exportRequestId/events`
- `/projects/:projectId/export-requests/:exportRequestId/reviews`
- `/projects/:projectId/export-requests/:exportRequestId/reviews/events`
- `/projects/:projectId/export-requests/:exportRequestId/release-pack`

## Permission model

- `REVIEWER` and `ADMIN` can claim, release, start review, and record decisions.
- `AUDITOR` can view queue, release packs, and histories; all mutation routes are read-only denied.
- Requester self-approval is blocked: the user who submitted a request cannot approve that same request revision.

## Active-stage and optimistic locking rules

All claim/release/start/decision writes are constrained to the current active required review stage and must include the current `reviewEtag`.

1. `reviewEtag` mismatch returns conflict.
2. A non-active stage cannot be claimed, started, released, or decided.
3. Start-review requires stage assignment to caller:
   - already assigned to caller, or
   - unassigned and claimed atomically by caller.
4. Start-review rejects stages assigned to another reviewer.
5. Decision writes require stage status `IN_REVIEW` and assignment to caller.

## Decision projection and reason requirements

Decision payload:

- `decision = APPROVE | REJECT | RETURN`
- `decisionReason` required for `REJECT`
- `returnComment` required for `RETURN`

Projection rules:

- Single-review requests approve to terminal `APPROVED` from primary stage approval.
- Dual-review requests:
  - primary approval keeps request in `IN_REVIEW`
  - secondary approval projects request to terminal `APPROVED`
  - secondary approver must differ from primary approver
- `REJECT` and `RETURN` from the active required stage are terminal for that request revision.

## Queue aging and SLA semantics

Queue surfaces expose persisted timestamps (`first_review_started_at`, `sla_due_at`, `last_queue_activity_at`, `retention_until`) plus computed aging buckets:

- `UNSTARTED`: no first-review timestamp, or stage not yet actively taken
- `NO_SLA`: in-review without a due timestamp
- `ON_TRACK`: due timestamp present and more than 24 hours remaining
- `DUE_SOON`: due timestamp present and 24 hours or less remaining
- `OVERDUE`: due timestamp has passed

Queue mutations update `last_queue_activity_at` and preserve deterministic SLA projections from request lifecycle events.

Reminder and escalation hooks are append-only request events:

- `REQUEST_REMINDER_SENT` applies only to open requests and uses cooldown thresholds to prevent spam loops.
- `REQUEST_ESCALATED` applies only when persisted SLA due timestamps have exceeded the configured escalation threshold.
- both events update `last_queue_activity_at` to keep claimed-but-stalled work visible in operations views.

Retention scaffolding is explicit and non-destructive:

- stale open requests can be assigned policy retention windows without deleting request/review/receipt history
- terminal requests (`APPROVED`, `EXPORTED`, `REJECTED`, `RETURNED`) receive status-based retention defaults when missing
- retention maintenance never deletes audit-critical evidence in this phase

## Dashboard UX contract

The `/export-review` surface is one coherent queue and detail context:

1. Queue filters for status, aging bucket, and reviewer user id.
2. Dense queue rows with risk/review-path/active-stage visibility.
3. In-context claim/release/start and decision controls.
4. Read-only presentation for auditors.
5. Request timeline and review-stage history panels.
6. Frozen release-pack summary in the same decision context.
7. Project history plus requester history panes for operational context.

## Audit events

Prompt 79 adds and/or activates:

- `EXPORT_REVIEW_QUEUE_VIEWED`
- `EXPORT_REQUEST_REVIEW_CLAIMED`
- `EXPORT_REQUEST_REVIEW_RELEASED`
- `EXPORT_REQUEST_REVIEW_STARTED`
- `EXPORT_REQUEST_APPROVED`
- `EXPORT_REQUEST_REJECTED`
- `EXPORT_REQUEST_RETURNED`

## Prompt 81 hardening link

Prompt 81 hardens approval-stage dual-control identity separation, rationale capture, and immutable
lock semantics under:

- [`/docs/architecture/export-approval-dual-control-rationale-and-immutable-history-contract.md`](./export-approval-dual-control-rationale-and-immutable-history-contract.md)

## Prompt 80 boundary

Prompt 79 does not implement no-bypass storage/egress enforcement mechanics.
Prompt 80 owns hard enforcement across UI/API/workers/storage and operational controls while preserving this reviewer workflow contract.

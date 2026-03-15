# Export Approval Dual-Control, Rationale, And Immutable History Contract

Status: Prompt 81  
Scope: Phase 8.1 approval workflow hardening for dual control, rationale capture, and immutable history

## Route ownership

Review workflow routes:

- `GET /projects/{projectId}/export-review`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/reviews/{reviewId}/claim`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/reviews/{reviewId}/release`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/start-review`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/decision`
- `GET /projects/{projectId}/export-requests/{exportRequestId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/events`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/reviews`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/reviews/events`

## Canonical stage lifecycle

Active required stage flow is canonical and optimistic-lock protected:

1. `claim` targets only the active required stage and requires the current `reviewEtag`.
2. `release` targets only the active required stage and requires the current `reviewEtag`.
3. `start-review` targets only the active required stage and requires the current `reviewEtag`.
4. `decision` targets only the active required stage, requires `IN_REVIEW`, assignment to caller, and current `reviewEtag`.

Invalid stage/order transitions are rejected; stale `reviewEtag` writes return conflict.

## Dual-control enforcement

For high-risk requests (`review_path=DUAL`, `requires_second_review=true`):

- request cannot project to `APPROVED` until both required stages are `APPROVED`
- secondary stage cannot be claimed, started, or decided unless primary is already `APPROVED`
- primary and secondary reviewers must be distinct users
- `RETURN` or `REJECT` on the active required stage is terminal for that request revision

## Rationale capture rules

- `REJECT` requires `decision_reason`
- `RETURN` requires `return_comment`
- `APPROVE` may include reviewer rationale through canonical review event/projection fields
- no separate mutable note store is used

Rationale is persisted in append-only `export_request_review_events` and reflected on mutable review/request projections.

## Immutable history and projection model

Source-of-truth event logs remain append-only:

- request history: `export_request_events`
- stage history: `export_request_review_events`

Mutable projections:

- request projection: `export_requests`
- stage projection: `export_request_reviews`

Terminal request revisions (`APPROVED`, `EXPORTED`, `REJECTED`, `RETURNED`) are locked for further review-stage mutation; successor resubmission is required for further change.

## RBAC boundaries

- mutate review stages: `REVIEWER`, `ADMIN`
- read-only review surfaces: `AUDITOR`
- no review-stage mutation rights: `RESEARCHER`, `PROJECT_LEAD`
- requester self-approval is blocked

## Audit alignment

The approval workflow emits and preserves:

- `EXPORT_REVIEW_QUEUE_VIEWED`
- `EXPORT_REQUEST_REVIEW_CLAIMED`
- `EXPORT_REQUEST_REVIEW_STARTED`
- `EXPORT_REQUEST_APPROVED`
- `EXPORT_REQUEST_REJECTED`
- `EXPORT_REQUEST_RETURNED`
- `EXPORT_REQUEST_REVIEWS_VIEWED`
- `EXPORT_REQUEST_REVIEW_EVENTS_VIEWED`

## Web surface contract

Review and request detail surfaces must expose:

- active stage, assignment, and `reviewEtag`
- review path (`SINGLE` vs `DUAL`)
- terminal lock state
- rationale fields (`decisionReason`, `returnComment`)
- append-only request and stage timelines

## Prompt 82 boundary

Prompt 82 extends operational controls around:

- retention windows and handoff hooks
- aging/reminder/escalation operations
- long-running queue and resubmission operations

Prompt 81 does not add new retention jobs or a second approval workflow.

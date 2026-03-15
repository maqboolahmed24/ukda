# Export Request Release-Pack And Lineage Contract

Status: Prompt 78  
Scope: Phase 8.0 requester-side export candidates, frozen request packs, and revision lineage

## Route ownership

Requester-side export route family:

- `/projects/:projectId/export-candidates`
- `/projects/:projectId/export-candidates/:candidateId`
- `/projects/:projectId/export-candidates/:candidateId/release-pack`
- `/projects/:projectId/export-requests`
- `/projects/:projectId/export-requests/new?candidateId={candidateId}`
- `/projects/:projectId/export-requests/new?candidateId={candidateId}&supersedesExportRequestId={exportRequestId}`
- `/projects/:projectId/export-requests/:exportRequestId`
- `/projects/:projectId/export-requests/:exportRequestId/status`
- `/projects/:projectId/export-requests/:exportRequestId/release-pack`
- `/projects/:projectId/export-requests/:exportRequestId/validation-summary`
- `/projects/:projectId/export-requests/:exportRequestId/events`
- `/projects/:projectId/export-requests/:exportRequestId/reviews`
- `/projects/:projectId/export-requests/:exportRequestId/reviews/events`
- `/projects/:projectId/export-requests/:exportRequestId/resubmit`

Deferred in later prompts:

- none in this contract scope

## Candidate snapshot contract

`export_candidate_snapshots` remains the canonical immutable export-candidate model.

Prompt 78 reconciliation rules:

1. Candidate reads only use pinned snapshot lineage (`governance_*`, `policy_*`, `candidate_sha256`), not mutable live projection rows.
2. Listing of eligible candidates excludes superseded lineage via explicit `supersedes_candidate_snapshot_id` links.
3. Phase 6 approved/governance-ready run outputs are reconciled into candidate snapshots through deterministic sync logic.
4. Candidate snapshots are append-only; new lineage appears as new rows.

## Export request model

Canonical requester-side persistence:

- `export_requests`
- `export_request_events`
- `export_request_reviews`
- `export_request_review_events`

Request lineage behavior:

1. Submission creates a new request row with immutable `release_pack_json`, `release_pack_key`, and `release_pack_sha256`.
2. Resubmission never mutates a returned request in place.
3. Resubmission creates a successor row with:
   - incremented `request_revision`
   - `supersedes_export_request_id` pointing to the returned predecessor
4. Predecessor row keeps its original terminal status and records `superseded_by_export_request_id`.
5. Successor revision creates fresh review-stage projections and append-only `REVIEW_CREATED` events.

## Frozen release-pack builder contract

Release-pack generation has two scopes:

1. Candidate preview (`GET /export-candidates/:candidateId/release-pack`)
   - deterministic preview payload over immutable candidate inputs
2. Request frozen pack (submission/resubmission)
   - request-scoped immutable bytes pinned in `export_requests.release_pack_json`

Deterministic and safety rules:

- canonical JSON serialization with sorted keys and stable separators
- SHA-256 hash over canonical bytes
- no direct filesystem path leakage in surfaced file references
- risk classification is derived only from pinned release-pack fields
- request review path and dual-review requirement are pinned at submission time

Minimum release-pack payload includes:

- file list (`fileName`, `fileSizeBytes`, `sha256`)
- candidate snapshot ID and request revision
- policy lineage/snapshot hash
- source artefact references
- approved model references by role
- redaction counts by category
- reviewer override count
- conservative area-mask count
- risk flags and classifier reason codes
- governance manifest/ledger pins
- release-review checklist

## Role visibility and mutation rules

Requester-side read visibility:

- `RESEARCHER`: own requests only
- `PROJECT_LEAD`, `REVIEWER`, `ADMIN`: all project requests
- `AUDITOR`: read-only project-wide requester surfaces

Requester-side mutation rules:

- create/resubmit: `RESEARCHER`, `PROJECT_LEAD`, `ADMIN`
- `RESEARCHER` may mutate only own request lineage
- `REVIEWER` and `AUDITOR` are read-only on requester-side mutations

## Audit contract additions

Requester-side read/create lineage emits:

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
- `EXPORT_REQUEST_RESUBMITTED`

Reserved for later reviewer-decision prompts:

- `EXPORT_REQUEST_REVIEW_CLAIMED`
- `EXPORT_REQUEST_REVIEW_STARTED`
- `EXPORT_REQUEST_RETURNED`
- `EXPORT_REQUEST_APPROVED`
- `EXPORT_REQUEST_REJECTED`

## Prompt 80 follow-on (Completed)

Prompt 80 completed:

- no-bypass egress enforcement across UI/API/workers/storage
- internal gateway receipt attach flow
- append-only receipt lineage and supersession
- operational/audit signals for blocked bypass attempts

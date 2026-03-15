# Export Gateway No-Bypass And Receipt Lineage Contract

Status: Prompt 80  
Scope: Phase 8.2 no-bypass egress enforcement, internal receipt attach, append-only receipt lineage

## Route ownership

Gateway-only attachment:

- `POST /internal/export-requests/{exportRequestId}/receipt`

Requester/reviewer read surfaces:

- `GET /projects/{projectId}/export-requests/{exportRequestId}/receipt`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/receipts`

No user-facing attachment route exists.

## Gateway-only attachment rules

1. Internal receipt attachment requires the internal gateway token (`X-UKDE-Internal-Token`).
2. Attachment is denied for requests outside `APPROVED` or `EXPORTED`.
3. `receiptKey` must resolve under `safeguarded/exports/`.
4. Non-gateway writer paths (for example `controlled/raw/*`, `controlled/derived/*`) are rejected.
5. Request projection is updated to terminal `EXPORTED` on successful attach.

## Receipt lineage rules

`export_receipts` is append-only and versioned by `attempt_number`.

1. New receipts never mutate prior rows.
2. Corrections append a new row and supersede the prior current receipt:
   - `supersedes_receipt_id` on the new row
   - `superseded_by_receipt_id` on the prior row
3. Request projection fields (`receipt_id`, `receipt_sha256`, `receipt_created_*`, `exported_at`) always point at the current receipt row.

## Request event projection

Each attachment appends:

- `REQUEST_RECEIPT_ATTACHED`
- `REQUEST_EXPORTED`

This preserves immutable history for first export and later correction attempts.

## No-bypass UI contract

Request detail surface exposes explicit state:

1. Non-approved requests: blocked state with no direct download affordance.
2. Approved without receipt: awaiting-gateway state.
3. Exported with receipt: receipt summary + receipt history table.

No direct download button/link is provided.

## Operational/audit signals

1. Internal auth failures for gateway route emit `ACCESS_DENIED`.
2. Receipt read views emit:
   - `EXPORT_REQUEST_RECEIPT_VIEWED`
   - `EXPORT_REQUEST_RECEIPTS_VIEWED`
3. Successful gateway delivery emits:
   - `EXPORT_REQUEST_EXPORTED`

These signals provide alertable evidence of blocked bypass attempts and successful controlled egress.

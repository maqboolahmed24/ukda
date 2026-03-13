# Audit Logging And Integrity (Phase 0.3 / Prompt 07)

This document defines the current append-only audit posture implemented in the web-first UKDE stack.

## Event Persistence

Audit data is stored in Postgres table `audit_events` with append-only enforcement:

- `id`
- `chain_index`
- `timestamp`
- `actor_user_id` (nullable for unauthenticated failures)
- `project_id` (nullable)
- `event_type`
- `object_type` (nullable)
- `object_id` (nullable)
- `ip` (nullable)
- `user_agent` (nullable)
- `request_id`
- `metadata_json` (strict key allowlist + sanitization)
- `prev_hash`
- `row_hash`

## Append-Only Guarantees

Current baseline guarantees:

- application writes are insert-only through one audit writer path
- no update/delete API endpoints are exposed for audit rows
- DB triggers reject `UPDATE` and `DELETE` on `audit_events`
- audit reads are separate from mutation APIs

Hardening boundary:

- local/dev environments still use one DB role for practicality
- strict DB-role separation (`INSERT` without `UPDATE`/`DELETE` grants) remains an infra hardening task

## Correlation IDs

- every API request gets a `request_id` (generated or accepted from validated `X-Request-ID`)
- `request_id` is attached to response header `X-Request-ID`
- audit events emitted during request handling include the same `request_id`
- non-HTTP contexts can provide explicit `request_id` and metadata directly to the audit writer

## Metadata Hygiene Rules

Audit metadata is centrally sanitized:

- per-event key allowlists
- control-character stripping and bounded string lengths
- sensitive-key suppression (`token`, `password`, `secret`, raw content markers)
- no raw request-body mirroring into audit metadata

## Event Types Implemented

- `USER_LOGIN`
- `USER_LOGOUT`
- `AUTH_FAILED`
- `PROJECT_CREATED`
- `PROJECT_MEMBER_ADDED`
- `PROJECT_MEMBER_REMOVED`
- `PROJECT_MEMBER_ROLE_CHANGED`
- `AUDIT_LOG_VIEWED`
- `AUDIT_EVENT_VIEWED`
- `MY_ACTIVITY_VIEWED`
- `ACCESS_DENIED`
- `JOB_LIST_VIEWED`
- `JOB_RUN_CREATED`
- `JOB_RUN_STARTED`
- `JOB_RUN_FINISHED`
- `JOB_RUN_FAILED`
- `JOB_RUN_CANCELED`
- `JOB_RUN_VIEWED`
- `JOB_RUN_STATUS_VIEWED`
- `OPERATIONS_OVERVIEW_VIEWED`
- `OPERATIONS_SLOS_VIEWED`
- `OPERATIONS_ALERTS_VIEWED`
- `OPERATIONS_TIMELINE_VIEWED`

## Integrity Verification

Hash-chain model:

- each row stores `prev_hash` and `row_hash`
- `row_hash = sha256(prev_hash + canonical_event_json)`
- chain order is defined by monotonic `chain_index`

Verification:

- API endpoint: `GET /admin/audit-integrity` (`ADMIN` or read-only `AUDITOR`)
- backend routine replays the chain and reports first mismatch if tampering is detected

## API Surfaces

- `GET /admin/audit-events`
- `GET /admin/audit-events/{eventId}`
- `GET /admin/audit-integrity`
- `GET /me/activity`

Access boundaries:

- `ADMIN` and `AUDITOR` can read admin audit surfaces
- `/me/activity` is current-user scoped
- audit-read actions emit self-auditing events with bounded metadata

## Web Surfaces

- `/admin/audit`
- `/admin/audit/:eventId`
- `/activity`

The UI is intentionally dense and calm: filterable list, traceable detail, and visible integrity status without a noisy dashboard pattern.

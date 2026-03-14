# Observability And Operations Surfaces (Prompt 08 Foundation)

This document defines the current observability baseline for UKDE Phase 0/early Phase 11 alignment.

## Current Signals

The API process records:

- request count
- request error count/rate
- request latency (including p95)
- per-route request/error/latency aggregates using route templates (low-cardinality labels)
- DB readiness check count, failures, and latency
- auth success/failure counts
- audit-write success/failure counts
- queue depth from unsuperseded `QUEUED` jobs
- trace context presence (`traceparent`) and request correlation (`X-Request-ID`)

## Operations APIs

All operations APIs are read-only.

- `GET /admin/operations/overview` (`ADMIN`)
- `GET /admin/operations/export-status` (`ADMIN` and read-only `AUDITOR`)
- `GET /admin/operations/slos` (`ADMIN`)
- `GET /admin/operations/alerts?state={state}&cursor={cursor}&pageSize={pageSize}` (`ADMIN`)
- `GET /admin/operations/timelines?scope={scope}&cursor={cursor}&pageSize={pageSize}` (`ADMIN` and read-only `AUDITOR`)

Reads are self-audited with bounded metadata:

- `OPERATIONS_OVERVIEW_VIEWED`
- `OPERATIONS_SLOS_VIEWED`
- `OPERATIONS_ALERTS_VIEWED`
- `OPERATIONS_TIMELINE_VIEWED`

`/admin/operations/export-status` currently reuses security posture data while the dedicated Phase 11 export-status API and event (`OPERATIONS_EXPORT_STATUS_VIEWED`) remain pending.

## Operations Web Surfaces

- `/admin/operations` (`ADMIN`)
- `/admin/operations/export-status` (`ADMIN` and read-only `AUDITOR`)
- `/admin/operations/slos` (`ADMIN`)
- `/admin/operations/alerts` (`ADMIN`)
- `/admin/operations/timelines` (`ADMIN` and read-only `AUDITOR`)

The UI is intentionally dense and restrained: status cards, tables, explicit filters, and simple pagination.

## SLO Scaffold (Current)

The current process-level SLO checks are:

- service availability (`>= 99.0%`)
- request p95 latency (`<= 800ms`)
- request error rate (`<= 2.0%`)
- DB readiness latency (`<= 250ms`)
- audit-write failure rate (`<= 1.0%`)
- queue depth (`<= 200` queued jobs)

## Alert Scaffold

Alerts are derived from SLO state:

- `MEETING` -> `OK`
- `BREACHING` -> `OPEN`
- `UNAVAILABLE` -> `UNAVAILABLE`

Exporter misconfiguration (including non-internal endpoints) is emitted as an `OPEN` telemetry alert.

## Trace And Correlation Baseline

- incoming API requests accept `traceparent`
- API returns `traceparent` and `X-Request-ID` headers
- Next.js server-side API calls propagate trace context and request correlation headers
- OIDC outbound calls from API include downstream `traceparent` when context exists

## Internal Export Path

Telemetry export defaults to disabled:

- `TELEMETRY_EXPORT_MODE=none`

If enabled (`otlp_http`), endpoint posture is evaluated:

- internal-only endpoint -> `CONFIGURED_INTERNAL`
- missing endpoint -> `MISCONFIGURED`
- non-internal endpoint -> `BLOCKED_PUBLIC_ENDPOINT`

This provides explicit failure-state visibility without enabling public telemetry paths by default.

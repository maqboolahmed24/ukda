# Observability And Operations Surfaces (Prompt 94 Baseline)

This document defines the current Phase 11 observability baseline for UKDE operations.

## Canonical Signals

The platform collects privacy-safe operational telemetry across API, workers, model services, and controlled storage.

- request count, request error rate, and request p95 latency
- per-route request/error/latency aggregates using route templates
- jobs per minute and completed-job count
- queue depth and queue-latency (queued-at to worker-claim) averages/p95
- GPU utilization (average/max/sample count) with sampler source metadata
- model-service request latency and warm/cold-start duration by deployment unit
- per-model error rate and fallback invocation rate
- export-review latency (submission to final decision)
- storage operation telemetry (READ/WRITE request counts, errors, latency)
- DB readiness checks and auth/audit outcome counters
- request correlation (`X-Request-ID`) and trace context (`traceparent`)

## Operations APIs

All operations APIs are read-only.

- `GET /admin/operations/overview` (`ADMIN`)
- `GET /admin/operations/readiness` (`ADMIN`, `AUDITOR`; auditor safe slice only)
- `GET /admin/operations/export-status` (`ADMIN`, `AUDITOR`)
- `GET /admin/operations/slos` (`ADMIN`)
- `GET /admin/operations/alerts?state={state}&cursor={cursor}&pageSize={pageSize}` (`ADMIN`)
- `GET /admin/operations/timelines?scope={scope}&cursor={cursor}&pageSize={pageSize}` (`ADMIN`, `AUDITOR`)

Capacity evidence APIs persist and expose benchmark/load/soak runs:

- `POST /admin/capacity/tests` (`ADMIN`)
- `GET /admin/capacity/tests?cursor={cursor}&pageSize={pageSize}` (`ADMIN`, `AUDITOR`)
- `GET /admin/capacity/tests/{testRunId}` (`ADMIN`, `AUDITOR`)
- `GET /admin/capacity/tests/{testRunId}/results` (`ADMIN`, `AUDITOR`)

Recovery APIs persist and expose restore/replay drills:

- `GET /admin/recovery/status` (`ADMIN`)
- `GET /admin/recovery/drills?cursor={cursor}&pageSize={pageSize}` (`ADMIN`)
- `POST /admin/recovery/drills` (`ADMIN`)
- `GET /admin/recovery/drills/{drillId}` (`ADMIN`)
- `GET /admin/recovery/drills/{drillId}/status` (`ADMIN`)
- `GET /admin/recovery/drills/{drillId}/evidence` (`ADMIN`)
- `POST /admin/recovery/drills/{drillId}/cancel` (`ADMIN`)

Operations reads emit audit events:

- `OPERATIONS_OVERVIEW_VIEWED`
- `OPERATIONS_EXPORT_STATUS_VIEWED`
- `OPERATIONS_SLOS_VIEWED`
- `OPERATIONS_ALERTS_VIEWED`
- `OPERATIONS_TIMELINE_VIEWED`

Capacity surfaces emit audit events:

- `CAPACITY_TEST_RUN_CREATED`
- `CAPACITY_TEST_RUNS_VIEWED`
- `CAPACITY_TEST_RUN_VIEWED`
- `CAPACITY_TEST_RESULTS_VIEWED`

Recovery surfaces emit audit events:

- `RECOVERY_STATUS_VIEWED`
- `RECOVERY_DRILLS_VIEWED`
- `RECOVERY_DRILL_VIEWED`
- `RECOVERY_DRILL_STATUS_VIEWED`
- `RECOVERY_DRILL_EVIDENCE_VIEWED`
- `RECOVERY_DRILL_CREATED`
- `RECOVERY_DRILL_STARTED`
- `RECOVERY_DRILL_FINISHED`
- `RECOVERY_DRILL_FAILED`
- `RECOVERY_DRILL_CANCELED`

## RBAC And Auditor Timeline Redaction

- `overview`, `slos`, and `alerts` are `ADMIN` only.
- `export-status` and `timelines` are readable by `ADMIN` and read-only `AUDITOR`.
- For recovery-linked timeline rows read by `AUDITOR`, backend responses are summary-only and include only:
  - `drill_id`
  - `status`
  - `started_at`
  - `finished_at`
  - `summary`
- Recovery evidence payloads are excluded from `AUDITOR` timeline rows, including:
  - `evidence_summary_json`
  - evidence storage keys
  - raw failure details

## Operations Web Surfaces

- `/admin/operations` (`ADMIN`)
- `/admin/operations/readiness` (`ADMIN`, `AUDITOR`; auditor safe slice only)
- `/admin/operations/export-status` (`ADMIN`, `AUDITOR`)
- `/admin/operations/slos` (`ADMIN`)
- `/admin/operations/alerts` (`ADMIN`)
- `/admin/operations/timelines` (`ADMIN`, `AUDITOR`)
- `/admin/capacity/tests` (`ADMIN`, `AUDITOR`)
- `/admin/capacity/tests/:testRunId` (`ADMIN`, `AUDITOR`)
- `/admin/recovery/status` (`ADMIN`)
- `/admin/recovery/drills` (`ADMIN`)
- `/admin/recovery/drills/:drillId` (`ADMIN`)
- `/admin/recovery/drills/:drillId/evidence` (`ADMIN`)

The operations UI remains dense and bounded: status cards, deterministic tables, explicit filters, and paginated lists.
Operations timelines include recovery drill evidence panels for `ADMIN`; `AUDITOR` sees only redacted drill-status summaries.

## SLO And Alert Model

SLO status is machine-readable and threshold-driven (`MEETING`, `BREACHING`, `UNAVAILABLE`).

Current SLO families include:

- service availability
- request p95 latency
- request error rate
- DB readiness latency
- audit-write failure rate
- queue depth
- queue latency p95
- model-service request latency p95
- model-service error rate
- model fallback invocation rate
- export-review latency p95
- storage operation error rate

Alert state is derived from SLO status:

- `MEETING` -> `OK`
- `BREACHING` -> `OPEN`
- `UNAVAILABLE` -> `UNAVAILABLE`

Telemetry exporter posture is also surfaced as an alert when misconfigured or configured to a non-internal endpoint.

## Trace And Correlation

- incoming API requests accept and propagate `traceparent`
- API responses include `traceparent` and `X-Request-ID`
- server-side web calls propagate trace and request-correlation headers
- worker-side telemetry records include request and trace identifiers where available

## Internal Export Path

Telemetry export remains internal-only.

- `TELEMETRY_EXPORT_MODE=none` disables exporter delivery
- `otlp_http` mode requires an internal endpoint
- exporter status values:
  - `DISABLED`
  - `MISCONFIGURED`
  - `BLOCKED_PUBLIC_ENDPOINT`
  - `CONFIGURED_INTERNAL`

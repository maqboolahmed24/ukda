# Telemetry Privacy Rules

Telemetry exists for operator diagnostics. It is not a second audit ledger and not a data exhaust.

## Never Log

- auth tokens
- session cookies
- passwords or secrets
- raw document content
- transcript text
- raw file bytes
- unrestricted request bodies
- user emails or free-text input as metric labels

## Allowed Telemetry Fields

Operational logs and timeline entries are limited to safe fields such as:

- `request_id`
- `trace_id`
- route template
- HTTP method
- status code
- latency
- coarse readiness/auth/audit counters
- bounded, sanitized error class names

`project_id` is allowed only when available as a path-level identifier and remains bounded/sanitized.

## Scrubbing Rules

The telemetry scrubber:

- removes keys containing sensitive fragments (`token`, `password`, `secret`, `cookie`, `authorization`, `raw`, `content`, `bytes`, `credential`)
- strips control characters and normalizes whitespace
- bounds key and value lengths
- sanitizes nested objects and lists

## Metric Label Rules

- labels use low-cardinality dimensions only (`route_template`, `method`)
- no dynamic user identifiers
- no dynamic document identifiers
- no arbitrary free text

## Trace Attribute Rules

- trace propagation relies on `traceparent`
- trace IDs are used for correlation only
- no payload content is attached to trace attributes

## Telemetry Vs Audit Events

Telemetry:

- mutable, operational signal stream for health/troubleshooting
- aggregate-focused
- can be reset per process lifecycle

Audit events:

- append-only governance record
- event-for-event actor history
- integrity chain and audit-specific retention semantics

Telemetry must never be treated as a substitute for audit evidence.

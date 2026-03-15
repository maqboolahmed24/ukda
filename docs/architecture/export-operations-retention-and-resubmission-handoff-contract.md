# Export Operations, Retention, And Resubmission Handoff Contract

Status: Prompt 82  
Scope: Phase 8.3 operational sustainability hooks for long-running governed export programs

## Canonical timing fields

`export_requests` remains the single canonical projection for queue and operations timing:

- `first_review_started_at`
- `sla_due_at`
- `last_queue_activity_at`
- `retention_until`

These fields are persisted and updated from canonical lifecycle transitions:

- request submission and resubmission
- review claim/start/decision
- gateway receipt attachment
- append-only reminder/escalation events
- retention-policy maintenance updates

## Reminder and escalation behavior

Reminder and escalation are append-only request events:

- `REQUEST_REMINDER_SENT`
- `REQUEST_ESCALATED`

Guardrails:

- reminders only apply to open requests (`SUBMITTED`, `RESUBMITTED`, `IN_REVIEW`)
- escalations require persisted SLA timestamps and threshold breach
- cooldown windows prevent repetitive reminder/escalation spam loops
- each appended reminder/escalation updates `last_queue_activity_at`

## Resubmission lineage

Resubmission semantics remain immutable and project-scoped:

- only `RETURNED` revisions are eligible for resubmission
- successor rows use incremented `request_revision`
- predecessor/successor linkage remains explicit through supersession fields
- successor revisions materialize fresh review rows and fresh review etags
- predecessor request/review events remain immutable history

## Retention boundaries

Retention maintenance is explicit and non-destructive in this phase:

- stale open requests can be assigned policy retention windows
- terminal requests (`APPROVED`, `EXPORTED`, `REJECTED`, `RETURNED`) receive policy retention defaults when missing
- maintenance does not delete request rows, review rows, receipt rows, or append-only audit evidence
- destructive cleanup remains out of scope until policy-driven purge controls are added for non-audit-critical artifacts only

## Operations handoff surface

`GET /admin/operations/export-status` provides the operations-grade handoff summary:

- open queue count
- aging buckets and stale-open count
- reminder/escalation due and sent totals
- retention pending count/window
- terminal exported/approved/rejected/returned counts
- active policy thresholds used for deterministic calculations

RBAC:

- `ADMIN` and read-only `AUDITOR` can read this route
- each read is self-audited with `OPERATIONS_EXPORT_STATUS_VIEWED`

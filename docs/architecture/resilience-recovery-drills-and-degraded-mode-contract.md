# Resilience, Recovery Drills, And Degraded-Mode Contract (Prompt 96)

This document defines the Phase 11.2 resilience and recovery implementation contract.

## Scope

- queue retry/dead-letter posture and replay visibility
- snapshot and restore strategy visibility
- admin-managed recovery drill lifecycle and evidence retrieval
- degraded-mode semantics on long-running workspaces
- operations timeline recovery evidence panels with auditor-safe redaction

## Recovery Persistence

Recovery drill state is persisted in `recovery_drills` with append-only drill events in `recovery_drill_events`.

`recovery_drills` fields:

- `id`
- `scope`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `started_by`
- `started_at`
- `finished_at`
- `canceled_by`
- `canceled_at`
- `evidence_summary_json`
- `failure_reason`
- `evidence_storage_key`
- `evidence_storage_sha256`
- `created_at`
- `updated_at`

`recovery_drill_events` is append-only and records lifecycle transitions:

- `DRILL_CREATED`
- `DRILL_STARTED`
- `DRILL_FINISHED`
- `DRILL_FAILED`
- `DRILL_CANCELED`

## API Surface And RBAC

Admin-only recovery APIs:

- `GET /admin/recovery/status`
- `GET /admin/recovery/drills`
- `POST /admin/recovery/drills`
- `GET /admin/recovery/drills/{drillId}`
- `GET /admin/recovery/drills/{drillId}/status`
- `GET /admin/recovery/drills/{drillId}/evidence`
- `POST /admin/recovery/drills/{drillId}/cancel`

RBAC:

- all recovery APIs are backend-enforced `ADMIN` only
- `AUDITOR` does not access live recovery status or drill evidence endpoints

## Drill Lifecycle

Canonical transitions:

- `QUEUED -> RUNNING`
- `RUNNING -> SUCCEEDED`
- `RUNNING -> FAILED`
- `QUEUED -> FAILED` (execution error before start completion)
- `QUEUED -> CANCELED`
- `RUNNING -> CANCELED`

Transition behavior is deterministic and idempotent: repeated requests against already-terminal drills return terminal state without mutating history.

## Evidence And Storage

- drill execution emits evidence payloads with replay/snapshot/restore/chaos checks
- evidence payloads are persisted under controlled derived storage:
  - `controlled/derived/recovery/drills/{scope}/{drillId}/evidence.json`
- SHA-256 is persisted on `recovery_drills.evidence_storage_sha256`
- evidence endpoint returns persisted payload plus append-only drill events

## Snapshot And Restore Strategy

Recovery evidence includes machine-readable strategy metadata for:

- DB snapshots (`logical-dump` posture)
- controlled object-store snapshots (`filesystem-copy` posture)
- model role restore order:
  - `PRIVACY_RULES`
  - `TRANSCRIPTION_FALLBACK`
  - `TRANSCRIPTION_PRIMARY`
  - `ASSIST`
  - `PRIVACY_NER`
  - `EMBEDDING_SEARCH`

Recovery gates enforce internal-only model service restore endpoints and no public-network fetches.

## Queue Replay And Dead-Letter Posture

Recovery status and drill evidence include:

- queue depth
- dead-letter count (`FAILED` rows at max attempts)
- replay-eligible count (`FAILED`/`CANCELED` unsuperseded rows)
- dead-letter sample metadata for operator triage

## Degraded-Mode UX Semantics

Long-running run-status surfaces (preprocessing, layout, transcription) poll recovery status and show a recovery-mode banner when degraded mode is active.

Semantics:

- degraded recovery mode is explicit and non-catastrophic
- degraded recovery mode is not treated as data-loss confirmation
- polling degradation messages remain distinct from run failure state

## Operations Timeline Recovery Evidence

Operations timelines include recovery drill entries.

For `ADMIN`:

- timeline panels include drill links, evidence key/sha, and evidence JSON summaries when present

For `AUDITOR`:

- recovery-linked timeline entries are redacted to:
  - `drill_id`
  - `status`
  - `started_at`
  - `finished_at`
  - `summary`
- excluded fields include:
  - `evidence_summary_json`
  - evidence storage keys/hashes
  - raw failure details

## Audit Events

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

# Jobs Framework And Worker Runtime (Phase 0.4 / Prompt 09)

This document defines the implemented jobs and worker runtime contract for UKDE.

## Scope

- Jobs persistence in Postgres (`jobs` and append-only `job_events`)
- Deterministic dedupe for logical jobs
- Retry lineage as append-only rows
- Worker-safe state transitions with lease recovery
- Project-scoped API surfaces and web routes
- Storage-prefix boundary posture for controlled and safeguarded tiers

## Jobs Persistence Contract

`jobs` rows persist:

- `id`
- `project_id`
- `attempt_number`
- `supersedes_job_id`
- `superseded_by_job_id`
- `type` (`NOOP`, ingest, preprocessing, and layout-analysis job families)
- `dedupe_key`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `attempts` (worker delivery attempts inside the row)
- `max_attempts`
- `payload_json`
- `created_by`
- `created_at`
- `started_at`
- `finished_at`
- `canceled_by`
- `canceled_at`
- `error_code`
- `error_message` (sanitized)

Worker-safety operational fields:

- `cancel_requested_by`
- `cancel_requested_at`
- `lease_owner_id`
- `lease_expires_at`
- `last_heartbeat_at`

`job_events` is append-only with:

- `event_type` (`JOB_CREATED | JOB_STARTED | JOB_SUCCEEDED | JOB_FAILED | JOB_CANCELED | JOB_RETRY_APPENDED`)
- `from_status`
- `to_status`
- `actor_user_id`
- `details_json`
- `created_at`

History is read from `job_events`; it is not reconstructed from mutable `jobs.status`.

## State Machine

Centralized transitions:

- `QUEUED -> RUNNING`
- `QUEUED -> CANCELED`
- `RUNNING -> SUCCEEDED`
- `RUNNING -> FAILED`
- `RUNNING -> CANCELED`
- `RUNNING -> QUEUED` (delivery retry when `attempts < max_attempts`)

Invalid transitions are rejected.

## Dedupe And Idempotency

- `dedupe_key` is deterministic from `(project_id, job_type, logical_key)`.
- If an unsuperseded same-key row is `QUEUED` or `RUNNING`, enqueue/retry returns that row.
- If an unsuperseded same-key row is already `SUCCEEDED`, enqueue/retry returns that row.
- Retry lineage uses append-only rows with:
  - new `attempt_number`
  - `supersedes_job_id` on the new row
  - `superseded_by_job_id` on the replaced row

## Cancellation

- `POST .../cancel` on `QUEUED` transitions directly to `CANCELED`.
- `POST .../cancel` on `RUNNING` sets cooperative cancel intent (`cancel_requested_*`).
- Worker finalization applies `RUNNING -> CANCELED` when cancel intent is present.
- Terminal rows reject cancel/retry mutation attempts.

## Worker Runtime

Implemented worker path:

- `ukde-worker run`:
  - polling loop with configurable interval and iteration cap
  - required for continuous queue draining in runtime environments
- `ukde-worker run-once`:
  - claim one queued job
  - apply heartbeat lease
  - execute typed handler (`NOOP`, ingest, preprocessing, layout, transcription)
  - finalize state

Stale-running recovery:

- Claim flow reclaims expired `RUNNING` leases.
- Expired running rows are transitioned to `QUEUED`, `FAILED`, or `CANCELED` according to attempts/cancel intent.
- This prevents permanently stuck `RUNNING` rows.

## APIs

Project-scoped routes:

- `GET /projects/{projectId}/jobs`
- `POST /projects/{projectId}/jobs` (Phase 0 NOOP enqueue)
- `GET /projects/{projectId}/jobs/summary`
- `GET /projects/{projectId}/jobs/{jobId}`
- `GET /projects/{projectId}/jobs/{jobId}/status`
- `GET /projects/{projectId}/jobs/{jobId}/events`
- `POST /projects/{projectId}/jobs/{jobId}/retry`
- `POST /projects/{projectId}/jobs/{jobId}/cancel`

RBAC:

- read: `PROJECT_LEAD | RESEARCHER | REVIEWER` (and explicit `ADMIN` override)
- retry/cancel/enqueue: `PROJECT_LEAD | REVIEWER` (and explicit `ADMIN` override)

Audit events:

- `JOB_LIST_VIEWED`
- `JOB_RUN_CREATED`
- `JOB_RUN_STARTED`
- `JOB_RUN_FINISHED`
- `JOB_RUN_FAILED`
- `JOB_RUN_CANCELED`
- `JOB_RUN_VIEWED`
- `JOB_RUN_STATUS_VIEWED`

## Web Surfaces

- `/projects/:projectId/jobs`
- `/projects/:projectId/jobs/:jobId`

Behavior:

- list view with status, attempts, timestamps, and safe error fields
- detail view with lineage and append-only event timeline
- status polling uses `/projects/:projectId/jobs/:jobId/status` route handler
- action controls (run/retry/cancel) are role-gated

## Storage Prefix Boundary Posture

Configured prefixes:

- `controlled/raw/`
- `controlled/derived/`
- `safeguarded/exports/`

Access intent:

- app identity: may write `controlled/raw/` and `controlled/derived/`
- export-gateway identity: reserved writer for `safeguarded/exports/`

Current implementation exposes this policy via `api/app/core/storage_boundaries.py`.

## Local Validation

Start API and worker:

```bash
source .venv/bin/activate
set -a && source .env && set +a
cd api
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
source .venv/bin/activate
set -a && source .env && set +a
ukde-worker run
```

Diagnostic single-pass check:

```bash
source .venv/bin/activate
set -a && source .env && set +a
ukde-worker run-once
```

Current implementation includes executable handlers for ingest extraction/thumbnail jobs, preprocessing orchestration/page/finalize jobs, layout analysis orchestration/page/finalize jobs, and transcription orchestration/page/finalize jobs.

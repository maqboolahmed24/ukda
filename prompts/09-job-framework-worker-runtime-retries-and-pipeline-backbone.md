You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed phase files before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first on each run.

## Mandatory first actions
1. Inspect the relevant repository areas and any existing implementation this prompt may extend.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-01-ingest-document-viewer-v1.md` for route ownership of `/projects/:projectId/jobs`
   - `/phases/phase-02-preprocessing-pipeline-v1.md` for future pipeline compatibility only
   - `/phases/phase-03-layout-segmentation-overlays-v1.md` for future pipeline compatibility only
   - `/phases/phase-04-handwriting-transcription-v1.md` for future pipeline compatibility only
   - `/phases/phase-05-privacy-redaction-workflow-v1.md` for future pipeline compatibility only
3. Then review the current repository generally — code, configs, scripts, tests, docs, containers, infra, workers, and packages already present in the repo — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second jobs framework, a second worker runtime, or conflicting retry semantics.

## Source-of-truth hierarchy
Use this precedence order when implementing:
1. The specific `/phases` files listed in this prompt for product behavior and acceptance logic.
2. `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md` when this prompt depends on web-first execution semantics.
3. `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` when this prompt depends on recall-first, rescue, token-anchor, search-anchoring, or conservative-masking semantics.
4. `/phases/blueprint-ukdataextraction.md`, `/phases/README.md`, and `/phases/ui-premium-dark-blueprint-obsidian-folio.md` as supporting product context when they are listed or clearly relevant.
5. This prompt for task scope and deliverables.
6. Current repository state for reconciling implementation details.
7. Official external docs for implementation mechanics only.

Treat current repository state as implementation context, not as the primary source of product truth.

## Conflict-resolution rule
- `/phases` wins for job semantics, RBAC, audit requirements, pipeline ownership, storage boundaries, and acceptance logic.
- Official docs win only for runtime mechanics, worker/process wiring, database locking patterns, HTTP polling behavior, and web implementation details.
- If a phase file uses older desktop-oriented wording, preserve the intent and implement the browser-native equivalent.

## Objective
Implement Phase 0 Iteration 0.4: the job framework, worker service, retries, and pipeline-ready backbone.

This prompt owns:
- jobs persistence
- valid job state transitions
- dedupe and idempotency rules
- retry lineage
- cancellation
- worker runtime
- job status APIs
- project jobs pages in the browser
- minimal project overview integration for job status
- storage skeleton prefixes and access posture
- safe local/dev execution path

This prompt does not own:
- actual ingest/document-processing implementation
- actual preprocessing/layout/transcription/privacy logic
- full broker infrastructure unless the repo already uses one
- full object-storage implementation beyond the required skeleton and boundaries
- export flow behavior
- full operations/metrics dashboards beyond what is needed to make jobs observable and safe

## Phase alignment you must preserve
From Phase 0 Iteration 0.4:

### Iteration Objective
Background work can be enqueued, executed, retried safely, and monitored in UI.

### Required job persistence contract
Implement or reconcile a `jobs` table/model with the following required fields:
- `id`
- `project_id`
- `attempt_number`
- `supersedes_job_id` (nullable when this is the first attempt)
- `superseded_by_job_id` (nullable)
- `type` (start with `NOOP`)
- `dedupe_key`
- `status`: `QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`
- `attempts`
- `max_attempts`
- `payload_json`
- `created_by`
- `created_at`
- `started_at`
- `finished_at`
- `canceled_by` (nullable)
- `canceled_at` (nullable)
- `error_code`
- `error_message` (sanitized)

Idempotency rule:
- deterministic `dedupe_key` per logical job
- worker avoids re-running jobs already succeeded

### Required project-scoped APIs
Preserve or implement the following:
- `GET /projects/{projectId}/jobs`
- `GET /projects/{projectId}/jobs/{jobId}`
- `GET /projects/{projectId}/jobs/{jobId}/status`
- `POST /projects/{projectId}/jobs/{jobId}/retry`
  - appends a new job row
  - increments `attempt_number`
  - sets `supersedes_job_id`
  - records the forward link on the replaced row via `superseded_by_job_id`
  - preserves the original failed row
  - recomputes `dedupe_key`
- `POST /projects/{projectId}/jobs/{jobId}/cancel`

Because the phase also requires E2E creation of a test job, if the repo does not yet have a consistent enqueue entrypoint, add the smallest correct Phase 0 route necessary to enqueue a `NOOP` test job. Keep it clearly Phase-0-scoped and safe to extend.

### Required RBAC
- `PROJECT_LEAD`, `RESEARCHER`, and `REVIEWER` can read project job status
- `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can retry or cancel eligible jobs

### Required audit events
Emit or reconcile:
- `JOB_LIST_VIEWED`
- `JOB_RUN_CREATED`
- `JOB_RUN_STARTED`
- `JOB_RUN_FINISHED`
- `JOB_RUN_FAILED`
- `JOB_RUN_CANCELED`
- `JOB_RUN_VIEWED`
- `JOB_RUN_STATUS_VIEWED`

### Required storage skeleton posture
Create or reconcile prefixes and access posture for:
- `controlled/raw/`
- `controlled/derived/`
- `safeguarded/exports/` (empty until later phases)

Access rules:
- app may write `controlled/raw` and `controlled/derived`
- only future export-gateway identity may write `safeguarded/exports`

## Implementation scope

### 1. Jobs state machine and persistence
Implement a central jobs model/service with valid transitions only.

Requirements:
- no invalid transitions
- state changes are centralized, not scattered ad hoc in route handlers
- error messages are sanitized
- retries do not mutate historical failed rows
- cancellation never silently deletes work history
- the job model is future-ready for Phase 1-5 job families without pretending those job types are already implemented

If the repo already has a jobs model, migrate or refine it to match the phase contract instead of replacing it wholesale.

### 2. Dedupe, idempotency, and retry lineage
Implement the dedupe and retry behavior rigorously.

Requirements:
- deterministic `dedupe_key`
- prevent duplicate execution of already-succeeded logical jobs
- failed jobs remain preserved
- retry creates a new row and links the lineage both backward and forward
- retry semantics are explicit and testable
- detail views can show the lineage clearly

### 3. Worker runtime
Implement the least disruptive reliable worker runtime for the current repo.

Rules:
- if the repo already uses a consistent broker, extend it
- if no broker exists yet, implement a DB-backed queue/worker polling model first
- do not introduce heavyweight infrastructure just for this prompt

Requirements:
- acquire work safely
- avoid duplicate concurrent execution
- support clean state transition from `QUEUED -> RUNNING -> terminal state`
- support cancellation before execution where eligible
- recover safely across worker restarts
- do not leave permanently stuck `RUNNING` jobs
- if minimal lease/heartbeat fields are required for safe recovery, add them carefully and document why

Start with one implemented worker handler:
- `NOOP` test job
- deterministic, safe, and easy to validate in E2E

Do not implement actual Phase 1+ document-processing handlers yet.

### 4. Job APIs and polling model
Implement or refine the project-scoped job APIs.

Requirements:
- job list view is paged or bounded if needed
- job detail payload is consistent and safe
- live status polling uses the status endpoint rather than repeatedly refetching the full detail payload
- authorization is centralized
- API contracts are typed and consistent with `/packages/contracts` if that package exists

### 5. Web jobs surfaces
Implement or refine:
- `/projects/:projectId/jobs`
- `/projects/:projectId/jobs/:jobId`

Requirements:
- calm, dark, serious operational UI
- job list with type, status, timestamps, actor, and safe error summaries
- detail page with lineage, attempts, timestamps, and current status
- clear retry and cancel controls only for authorized roles
- no flashy dashboard behavior
- no noisy auto-refresh gimmicks
- polling must be efficient and bounded

If useful, add a minimal “Run test job” action for the Phase 0 `NOOP` path so the E2E flow is real.

### 6. Project overview integration
Refine the project overview surface so it can show:
- `jobs running: N`
- last job status

Do not turn the overview page into a fake analytics dashboard.

### 7. Storage skeleton and configuration
Create or reconcile the minimum storage/config foundation needed for:
- raw artefacts
- derived artefacts
- future export boundary

This may be config, adapter, infra placeholder, and docs if full backing infrastructure is not yet available.
Do not build the full storage product in this prompt.
Do make the boundaries explicit and enforceable.

### 8. Documentation
Document:
- job lifecycle
- retry lineage semantics
- dedupe rules
- worker runtime path
- cancellation behavior
- storage prefix posture
- local/dev startup path for worker execution
- any deliberate limitations of the current Phase 0 implementation

## Required deliverables

### Backend / workers
- jobs model / migration
- job state-machine service
- queue enqueue path for `NOOP` if absent
- worker runtime
- retry and cancel endpoints
- status endpoint
- tests

### Web
- `/projects/:projectId/jobs`
- `/projects/:projectId/jobs/:jobId`
- minimal job creation/test trigger if needed
- overview status integration

### Shared contracts
- job DTOs / enums / state contracts if useful

### Docs
- job framework / worker runtime doc
- any README updates required for local validation

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if a small UI refinement is required for consistent job status presentation
- root config/task files
- `README.md`
- `docs/**`
- `infra/**` only where needed for storage or worker/runtime coherence

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- actual ingest processing
- preprocessing logic
- layout segmentation
- transcription logic
- privacy workflow logic
- export gateway behavior
- full broker platform rollout if a lighter correct path exists
- a noisy “operations dashboard” that duplicates the observability and operations surfaces
- a second unrelated jobs system

## Testing and validation
Before finishing:
1. Verify valid state transitions only.
2. Verify dedupe blocks duplicate execution.
3. Verify enqueue -> worker pickup -> success for the `NOOP` job.
4. Verify retry flow:
   - first failure
   - retry
   - success
   - preserved lineage fields
5. Verify cancellation of a queued job prevents execution.
6. Verify worker restart does not leave permanently stuck `RUNNING` jobs.
7. Verify job detail pages poll the status endpoint, not the full detail endpoint.
8. Verify RBAC on read/retry/cancel.
9. Verify audit events are emitted for job reads and job state changes.
10. Verify docs match actual commands and paths.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- a real jobs table/model exists
- the state machine is valid and centralized
- dedupe/idempotency is real
- retry lineage is preserved correctly
- worker execution is real
- queued jobs can be canceled safely
- the browser has real jobs list/detail surfaces
- the project overview reflects job activity
- storage boundaries are explicitly scaffolded
- one centralized job registration and execution path is used by all implemented job types
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

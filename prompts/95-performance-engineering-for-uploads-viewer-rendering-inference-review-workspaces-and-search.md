You are the implementation agent for UKDE. Work directly in the repository. Do not ask clarifying questions. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: assume zero chat memory and reread the repo plus the listed phase files before changing anything.
- Sequenced: if the repo already contains partial implementation from earlier prompts, extend and reconcile it instead of restarting from scratch.

The actual product source of truth is the extracted `/phases` directory in repo root. Do not mention or expect a zip. Read `/phases` first on every run.

## Mandatory first actions
1. Inspect the full repository tree.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — upload paths, viewer rendering, worker inference paths, caches, search/indexing paths, admin capacity routes, performance tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second capacity-testing framework, a second cache-control model, or conflicting degraded-state semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for capacity-test records, performance evidence, degraded-state messaging, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that performance claims are backed by persisted evidence, not one-off benchmark screenshots.

## Objective
Execute performance engineering for uploads, viewer rendering, inference pipelines, review workspaces, and search.

This prompt owns:
- capacity-test scenario definitions
- capacity-test run persistence and results retrieval
- GPU batching and warmup strategy hooks where coherent
- thumbnail/overlay/search caching and tuning
- degraded-state messaging for heavy workloads
- benchmark, load, and soak evidence surfaces
- performance budget and p95 evidence across key user flows

This prompt does not own:
- observability dashboards themselves
- recovery drills
- security hardening
- a second capacity-testing framework
- new product features unrelated to performance

## Phase alignment you must preserve
From Phase 11 Iteration 11.1:

### Required backend work
- GPU inference batching
- model warmup strategy for approved VLM and LLM roles
- thumbnail and overlay caching
- search and index tuning
- capacity model for storage, CPU, GPU, model-service concurrency, and queue depth
- separate capacity envelopes for:
  - `transcription-vlm`
  - `assist-llm`
  - `privacy-ner`
  - `privacy-rules`
  - `transcription-fallback`
  - `embedding-search`

### Required persisted records
`capacity_test_runs`:
- `id`
- `test_kind` (`LOAD | SOAK | BENCHMARK`)
- `scenario_name`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `results_key`
- `results_sha256`
- `started_by`
- `started_at`
- `finished_at`
- `created_at`

### Required APIs
- `POST /admin/capacity/tests`
- `GET /admin/capacity/tests`
- `GET /admin/capacity/tests/{testRunId}`
- `GET /admin/capacity/tests/{testRunId}/results`

### RBAC
- creation is `ADMIN` only
- reads are `ADMIN` and read-only `AUDITOR`
- backend handlers enforce role checks server-side

### Required web routes
- `/admin/capacity/tests`
- `/admin/capacity/tests/:testRunId`

### Required gates
- sustained throughput meets target
- 24-hour soak test without memory leaks
- p95 latency tracked for critical user flows
- GPU utilization and model warm-start behavior meet documented SLOs
- capacity evidence persists through the admin APIs

## Implementation scope

### 1. Canonical capacity-test runner
Implement or refine the capacity-test orchestration.

Requirements:
- admin-triggered scenario execution
- persisted `capacity_test_runs`
- deterministic scenario naming and results storage
- no out-of-band database inserts
- no second benchmark runner path

### 2. Performance tuning hooks
Implement or refine platform tuning in the existing architecture.

Requirements:
- GPU batching where relevant
- model warmup strategy for approved roles
- thumbnail and overlay caching
- search/index tuning
- storage/CPU/GPU/model-service/queue capacity modeling
- changes remain measurable and tied to test evidence

### 3. Capacity envelopes
Persist and surface capacity expectations.

Requirements:
- separate envelopes for the required model/service roles
- evidence remains attached to named scenarios
- no hand-wavy “fast enough” flags
- capacity evidence is typed and retrievable

### 4. Admin capacity surfaces
Implement or refine the admin web routes.

Requirements:
- list of benchmark/load/soak runs
- detail route with result summaries and artifacts
- calm, dense operations-grade UI
- read-only `AUDITOR` access
- exact pending/running/succeeded/failed/canceled states

### 5. Degraded-state messaging
Refine user-facing degraded states for heavy jobs.

Requirements:
- long-running workspaces and heavy pipelines show honest degraded-state messaging
- no fake progress
- no unnecessary full-page blocking
- degraded-state messaging remains distinct from failure or data-loss states

### 6. Audit and regression
Use the canonical audit path and add coverage.

At minimum cover:
- capacity-test creation and status updates
- persisted results retrieval
- role-based access
- p95 tracking on critical flows
- soak evidence handling
- degraded-state messaging correctness
- no second capacity-testing path

### 7. Documentation
Document:
- capacity-test scenario model
- performance evidence expectations
- degraded-state rules
- what later recovery/security/release prompts can assume from this evidence

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / workers / contracts
- capacity-test runner
- performance tuning hooks
- capacity evidence storage and APIs
- tests

### Web
- admin capacity list/detail routes
- degraded-state messaging refinements where needed

### Docs
- performance and capacity engineering doc
- degraded-state messaging and evidence doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small degraded-state or admin capacity refinements are needed
- caches/perf helpers used by the repo
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- observability dashboard work
- recovery drills
- security findings workflows
- a second capacity framework
- new unrelated product features

## Testing and validation
Before finishing:
1. Verify capacity tests can be created through the admin API.
2. Verify load, soak, and benchmark results persist and are retrievable.
3. Verify p95 latency evidence is captured for critical flows.
4. Verify GPU warmup and batching evidence is measurable where relevant.
5. Verify `ADMIN` vs `AUDITOR` access boundaries.
6. Verify degraded-state UX is honest and distinct from failure states.
7. Verify docs match the implemented capacity and performance behavior.
8. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- performance and capacity evidence is real
- capacity-test runs are real
- degraded-state messaging is real
- admin/auditor capacity surfaces are real
- the platform now has repeatable performance evidence instead of anecdotes
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

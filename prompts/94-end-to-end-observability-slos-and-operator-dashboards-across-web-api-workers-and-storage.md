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
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — metrics/traces/logging, admin operations routes, storage/model-service instrumentation, alerting hooks, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second observability stack, a second SLO model, or conflicting alert-state semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for metrics/SLO/alert requirements, route ownership, RBAC, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that operations truth is measured, traced, and dashboarded across API, workers, storage, and model services; `AUDITOR` remains read-only on allowed operations surfaces.

## Objective
Establish end-to-end observability, SLOs, and operator dashboards across web, API, workers, and storage.

This prompt owns:
- metrics, traces, and privacy-safe operational logs for critical paths
- SLO definitions and alert thresholds
- operations overview, export-status, SLO, alerts, and timelines APIs
- admin operations dashboards and read-only auditor operational timelines/export-status
- synthetic threshold-breach tests and alert-state coverage
- typed status contracts for operations surfaces

This prompt does not own:
- capacity/load testing
- recovery drills
- security findings workflow
- a second observability stack
- public status pages

## Phase alignment you must preserve
From Phase 11 Iteration 11.0:

### Required metrics
Instrument and expose:
- jobs per minute
- queue latency
- GPU utilization
- model-service request latency and warm/cold-start duration by deployment unit
- per-model error rate and fallback invocation rate
- export-review latency
- error rates

### Required APIs
- `GET /admin/operations/overview`
- `GET /admin/operations/export-status`
- `GET /admin/operations/slos`
- `GET /admin/operations/alerts?state={state}`
- `GET /admin/operations/timelines?scope={scope}`

### RBAC
- `overview`, `slos`, and `alerts` are `ADMIN` only
- `export-status` and `timelines` are readable by `ADMIN` and read-only `AUDITOR`
- `AUDITOR` timeline reads are summary-only and exclude admin-only recovery drill evidence payloads
- recovery-linked timeline rows shown to `AUDITOR` are limited to `drill_id`, `status`, `started_at`, `finished_at`, and short `summary`
- recovery-linked timeline rows shown to `AUDITOR` must exclude `evidence_summary_json`, evidence storage keys, and raw failure details
- backend handlers must enforce role checks server-side

### Required web routes
- `/admin/operations`
- `/admin/operations/export-status`
- `/admin/operations/slos`
- `/admin/operations/alerts?state={state}`
- `/admin/operations/timelines?scope={scope}`

### Required audit events
- `OPERATIONS_OVERVIEW_VIEWED`
- `OPERATIONS_EXPORT_STATUS_VIEWED`
- `OPERATIONS_SLOS_VIEWED`
- `OPERATIONS_ALERTS_VIEWED`
- `OPERATIONS_TIMELINE_VIEWED`

## Implementation scope

### 1. Canonical metrics and trace baseline
Implement or refine one coherent observability layer.

Requirements:
- instrumentation across API, workers, storage, and model services
- privacy-safe logs and tags
- trace correlation across critical paths
- no second metrics stack or shadow dashboards
- stable naming and units for all required signals

### 2. SLO definitions and thresholds
Implement or refine SLO configuration and serving.

Requirements:
- explicit SLO definitions
- alert thresholds
- machine-readable status
- no “hand-wavy” health claims
- SLOs remain linked to actual measured metrics

### 3. Operations APIs
Implement or refine the canonical operations read surfaces.

Requirements:
- typed payloads
- overview aggregates key platform health
- export-status remains readable by `AUDITOR`
- timelines remain readable by `AUDITOR`
- alerts and SLOs are `ADMIN` only
- no parallel operations API family

### 4. Operations web surfaces
Implement or refine the operations UI.

Requirements:
- admin overview dashboard
- SLO page
- alerts page
- timelines page
- export-status page
- calm, dense, exact operational UI
- no NOC-wall gimmicks or noisy graphs for their own sake

### 5. Alert-state and threshold testing
Add or refine synthetic threshold-breach testing.

Requirements:
- tests can drive alert state transitions
- failures are reviewable and deterministic
- no flaky alert simulation
- alert and SLO surfaces update coherently

### 6. Audit and documentation
Use the canonical audit path and document the stack.

Requirements:
- audit events for operations surfaces
- privacy-safe observability docs
- route and RBAC docs
- no second audit path

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- metrics and trace baseline
- SLO/alert definitions
- operations APIs
- tests

### Web
- operations overview, SLOs, alerts, timelines, and export-status routes
- role-aware visibility and read-only auditor surfaces

### Docs
- observability and SLO baseline doc
- operations dashboard and RBAC doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small operations/status-chart refinements are needed
- observability/config helpers used by the repo
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- capacity testing
- recovery tooling
- security findings workflow
- a second observability or status stack
- public status pages

## Testing and validation
Before finishing:
1. Verify instrumentation exists on every critical path required by the phase.
2. Verify SLO definitions and alert thresholds are exposed through the canonical APIs.
3. Verify `ADMIN` vs `AUDITOR` route and API access boundaries, including summary-only auditor timeline reads.
4. Verify `AUDITOR` timeline payloads include only allowed recovery-summary fields (`drill_id`, `status`, `started_at`, `finished_at`, `summary`).
5. Verify `AUDITOR` timeline payloads exclude `evidence_summary_json`, evidence storage keys, and raw failure details.
6. Verify synthetic threshold breaches surface through alerts correctly.
7. Verify operations pages render truthful and bounded states.
8. Verify docs match the implemented observability and SLO behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- end-to-end observability is real
- SLOs and alert thresholds are real
- operator dashboards are real
- auditor read-only export-status/timeline access is real
- the platform now has measured operational truth instead of anecdotes
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

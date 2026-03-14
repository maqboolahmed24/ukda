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
   - `/phases/phase-08-safe-outputs-export-gateway.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — export request schemas, queue surfaces, operations/admin routes, reminder/escalation hooks, review events, CI/ops tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second operations queue, a second retention model, or conflicting resubmission semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for SLA fields, aging rules, resubmission lineage, retention behavior, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that export operations are sustainable, observable, and append-only; retention must never destroy audit-critical evidence.

## Objective
Add retention, resubmission, aging, and export-operations handoff hooks for long-running governed programs.

This prompt owns:
- SLA timestamp computation and persistence
- reminder and escalation event flows
- resubmission lineage hardening
- requester/project history surfaces
- retention rules and retention-job scaffolding
- export-operations handoff signals for ops/admin surfaces
- queue-aging indicators and stale-request escalation support
- audit-complete operational lifecycle for long-running export programs

This prompt does not own:
- reviewer decision semantics
- gateway receipt enforcement
- provenance or bundle workflows
- a second operations dashboard outside existing admin/operations surfaces

## Phase alignment you must preserve
From Phase 8 Iteration 8.3 and related Phase 8 request rules:

### Existing operational fields
Use or reconcile:
- `first_review_started_at`
- `sla_due_at`
- `last_queue_activity_at`
- `retention_until`

These must be computed and persisted from:
- queue entry
- review claim
- review start
- reminder
- escalation
- decision
- receipt attachment
- retention-policy events

### Existing request lineage rules
- only `RETURNED` requests can be resubmitted
- resubmission creates a new request revision
- predecessor remains terminal for its own revision
- successor revision gets fresh review rows and etags
- supersession is explicit

### Existing access rules
- `RESEARCHER` can view own requests and resubmit only own `RETURNED` request revisions
- `PROJECT_LEAD` and `ADMIN` can view project requests and resubmit `RETURNED` request revisions project-wide
- `REVIEWER` and `AUDITOR` are read-only for requester-side resubmission mutations

### Existing operational goal
Make the export workflow safe, observable, and operable at steady state.

### Existing UI expectations
- queue aging indicators
- decision notes panel
- export history by project and requester

## Implementation scope

### 1. Canonical timing and aging computation
Implement or refine deterministic timing fields.

Requirements:
- compute and persist `first_review_started_at`, `sla_due_at`, `last_queue_activity_at`, and `retention_until`
- update these fields only from canonical request/review/receipt/retention events
- no client-local timing state
- queue-aging and ops views read the canonical persisted values

### 2. Reminder and escalation eventing
Implement or refine reminder/escalation hooks.

Requirements:
- append request-level events for reminder and escalation
- do not mutate request history in place
- reminders and escalations update `last_queue_activity_at`
- escalation conditions are deterministic and documented
- no noisy reminder spam loops

### 3. Resubmission lineage hardening
Refine the returned-request resubmission path.

Requirements:
- resubmission remains append-only and explicit
- fresh review rows and review etags are created on successor revisions
- prior request and review history remain immutable
- request history across revisions is easy to inspect
- same-candidate resubmissions and replacement-candidate resubmissions both stay safe and project-scoped

### 4. Retention rules and jobs
Implement or scaffold retention safely.

Requirements:
- retention policies apply to stale, rejected, returned, approved, and exported requests according to the repo’s policy configuration
- retention jobs do not delete audit-critical records
- terminal request history, review history, receipts, and audit evidence remain preserved per policy
- retention scheduling and expiry are explicit and typed
- actual destructive cleanup, if any, is constrained to non-audit-critical artefacts only and must be policy-driven

If the repo is not ready for actual purge behavior, implement the scheduling, state, and no-delete guarantees first.

### 5. Export history by project and requester
Refine list and detail reads.

Requirements:
- export history can be filtered by requester and status
- project-wide and requester-specific views remain coherent with existing RBAC
- resubmission chains are visible
- aging and retention indicators are present where useful
- no second history system is introduced

### 6. Operations handoff hooks
Integrate export operations into existing admin/ops surfaces where they already exist.

Requirements:
- expose queue aging summaries
- expose escalation counts
- expose retention-pending counts
- expose terminal exported / rejected / returned counts
- if the repo already has `/admin/operations/export-status`, extend it rather than creating a parallel route
- keep the UI calm, exact, and operations-grade

### 7. Audit and tests
Use the canonical audit path and add operational coverage.

At minimum cover:
- SLA due calculation consistency
- reminder/escalation event creation
- `last_queue_activity_at` updates on claim and operational events
- resubmission chain integrity
- retention jobs do not delete audit-critical records
- requester/project history filtering remains correct

### 8. Documentation
Document:
- SLA and aging semantics
- reminder and escalation behavior
- retention boundaries
- resubmission lineage
- operations handoff fields and how later hardening prompts will use them

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- timing field computation
- reminder/escalation eventing
- retention scaffolding or jobs
- history filter/read improvements
- tests

### Web
- queue aging indicators
- requester/project history refinements
- export operations handoff summaries where existing ops routes support them

### Docs
- export operations, SLA, and retention doc
- resubmission and long-running governance workflow doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**` if reminder/escalation/retention jobs need worker support
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small aging/history/status refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- gateway receipt enforcement
- provenance or bundle workflows
- a second ops queue
- destructive deletion of audit-critical records

## Testing and validation
Before finishing:
1. Verify SLA timers compute consistently.
2. Verify reminder and escalation events append correctly.
3. Verify claim/start/reminder/escalation update `last_queue_activity_at`.
4. Verify resubmissions create new request revisions and fresh review rows.
5. Verify only allowed roles can resubmit and only for `RETURNED` request revisions.
6. Verify ownership and scope boundaries: `RESEARCHER` can resubmit only own `RETURNED` revisions, while `PROJECT_LEAD` and `ADMIN` can resubmit `RETURNED` revisions project-wide.
7. Verify requester/project history filters work correctly.
8. Verify retention jobs do not delete audit-critical records.
9. Verify docs match the implemented operational and retention behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- aging and SLA behavior are real
- reminder and escalation hooks are real
- resubmission lineage is hardened
- retention behavior is explicit and safe
- export operations have meaningful handoff hooks
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

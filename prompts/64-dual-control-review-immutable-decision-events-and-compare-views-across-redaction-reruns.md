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
   - `/phases/phase-05-privacy-redaction-workflow-v1.md`
3. Then review the current repository generally — privacy routes, run-review APIs, page-review APIs, compare APIs, decision-event tables, workspace shells, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second run-review workflow, a second compare system for redaction reruns, or hidden approval semantics outside the canonical append-only events.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. current repository state as the implementation reality to reconcile with
  2. this prompt
  3. the precise `/phases` files listed above
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for dual-control rules, immutable decision history, compare-route ownership, run-review locking, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that approvals and second reviews are append-only, same-user dual review is disallowed when required, and compare across reruns never mutates source runs.

## Objective
Add dual-control review, immutable decision events, and compare views across redaction reruns.

This prompt owns:
- dual-control page and run review enforcement
- same-user second-review rejection
- run-level start-review / complete-review flows
- append-only review and decision history surfaces
- compare route and compare read APIs across redaction reruns
- review-state locking on approved runs
- compare-driven reviewer analysis across reruns without silent merges
- role-aware run completion and compare UX

This prompt does not own:
- detector logic
- masking engine logic
- preview generation logic
- manifest or export workflows
- a second decision-history system
- public or external compare sharing

## Phase alignment you must preserve
From Phase 5 Iteration 5.3 and existing Phase 5 tables/APIs:

### Review rules
- `Complete review` stays disabled until every page is approved, every required second review is complete, and all page previews are `READY`
- overrides require a reason
- high-risk overrides require second review when:
  - the override changes a finding to `FALSE_POSITIVE`
  - the override introduces or replaces a conservative `area_mask_id`
  - the finding category is dual-review-required by the pinned policy snapshot
  - the finding had detector disagreement or ambiguous overlap recorded in `basis_secondary_json`
- required second review must be performed by a user different from `first_reviewed_by`
- `REVIEWER`, `PROJECT_LEAD`, or `ADMIN` can approve pages and apply overrides
- `AUDITOR` does not participate in Phase 5 review actions

### Existing canonical tables
Use or reconcile:
- `redaction_decision_events`
- `redaction_page_reviews`
- `redaction_page_review_events`
- `redaction_run_reviews`
- `redaction_run_review_events`
- `document_redaction_projections`

### Existing APIs
Use or refine:
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/review`
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/start-review`
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/complete-review`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/events`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`

### Required immutable behavior
- run approval persists `approved_snapshot_key` and `approved_snapshot_sha256`
- once `review_status = APPROVED`, finding decisions, page reviews, and area-mask revisions are immutable
- any further reviewer changes require a new successor run instead of mutating the approved decision set in place

## Implementation scope

### 1. Dual-control enforcement
Implement or refine dual-control logic end to end.

Requirements:
- page review can require second review
- same-user first and second review attempts are rejected when `requires_second_review = true`
- page approval eligibility remains deterministic
- run completion is blocked until all page-level review requirements are satisfied
- the UI and APIs both surface the dual-control requirement truthfully

### 2. Run review lifecycle
Implement or refine the canonical run review flow.

Requirements:
- `start-review` moves a run from `NOT_READY` to `IN_REVIEW` only when eligible
- `complete-review` can transition only to `APPROVED` or `CHANGES_REQUESTED`
- approval persists immutable snapshot metadata and lock state
- same-run edits are blocked after approval
- the review detail surface shows exact lock and approval status

### 3. Immutable event and history surfaces
Refine read surfaces so reviewers can inspect history without reconstructing it from mutable rows.

Requirements:
- run event timeline uses append-only sources
- page event timeline uses append-only sources
- decision history is inspectable and ordered deterministically
- compare and review surfaces can reference this history coherently
- no parallel shadow history model is introduced

### 4. Compare across reruns
Implement or refine compare views across redaction reruns.

Requirements:
- compare base and candidate redaction runs through the canonical compare route
- surface differences in:
  - finding counts
  - decision status changes
  - review-state changes
  - preview readiness deltas
- no silent promotion or merge
- compare remains read-only and analytic
- deep links can point to a page/finding context cleanly

### 5. Review locking semantics
Harden lock behavior.

Requirements:
- once approved, later finding decision writes are rejected
- once approved, later page-review writes are rejected
- once approved, later area-mask revisions are rejected
- lock state is visible and exact
- no hidden bypass path exists through alternate APIs

### 6. Web review and compare surfaces
Refine or extend the UI minimally but coherently.

Requirements:
- run review summary surface
- second-review indicators
- compare route shell for reruns
- calm, dense, exact presentation
- no giant governance dashboard
- reviewer can understand why approval is blocked and what remains unresolved

### 7. Audit and regression
Use the canonical audit path and add coverage.

At minimum cover:
- dual-control blocks single-reviewer completion when required
- same-user second review rejection
- approval snapshot persisted on approve
- approved runs reject later mutations
- compare route works across reruns
- immutable event timelines remain truthful
- stale review state is handled safely

### 8. Documentation
Document:
- dual-control rules
- run-review lifecycle
- immutable approval snapshot and locking
- rerun compare semantics
- what Prompt 65 will deepen around reviewed artefacts and downstream readiness

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- dual-control enforcement
- run-review lifecycle hardening
- compare-read refinements for reruns
- lock semantics
- tests

### Web
- run review surfaces
- compare across reruns
- blocker and lock-state presentation

### Docs
- dual-control and run-review doc
- privacy rerun compare and approval-lock doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small review/compare/timeline refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- detector changes
- masking engine changes
- manifest/export workflows
- a second compare system
- any mutation of approved runs
- public sharing of compare data

## Testing and validation
Before finishing:
1. Verify same-user second-review attempts are rejected when required.
2. Verify page approval eligibility is deterministic.
3. Verify run completion is blocked until page approvals, second reviews, and previews are ready.
4. Verify approval persists immutable snapshot and lock state.
5. Verify approved runs reject later finding, page-review, and area-mask mutations.
6. Verify compare across reruns works and remains read-only.
7. Verify event timelines are append-only and ordered deterministically.
8. Verify docs match the implemented dual-control and compare behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- dual-control review is real
- approved-run locking is real
- compare views across redaction reruns are real
- event history remains append-only and trustworthy
- reviewers can understand blockers and lineage clearly
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

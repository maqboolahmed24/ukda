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
   - `/phases/phase-05-privacy-redaction-workflow-v1.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — privacy detection/decision/review pipelines, synthetic test fixtures, preview generation, browser tests, CI gates, audit code, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second regression framework, a second synthetic disclosure corpus, or duplicate browser/accessibility stacks for the privacy tranche.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for privacy gates, reviewer-safety requirements, activation blockers, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that privacy activation requires robust regression against disclosure leaks, reviewer hazards, and accessibility/interaction failures.

## Objective
Ship privacy regression packs, synthetic disclosure tests, and reviewer-safety checks before activation.

This prompt owns:
- the canonical privacy regression pack
- synthetic disclosure and near-miss fixtures
- regression gates across detection, masking, preview generation, and review locking
- reviewer-safety browser checks
- accessibility, keyboard, and visual regression for the privacy workspace and compare/review surfaces
- CI wiring and artefact review workflow for privacy regressions
- explicit activation blockers tied to failed privacy gates

This prompt does not own:
- new detector features
- new masking features
- governance/export features
- a second test harness
- noisy or flaky test suites that create more churn than signal

## Phase alignment you must preserve
From Phase 5 and Phase 11:

### Existing required privacy tests
- deterministic span extraction
- detector coverage and recall floors
- deterministic overlap resolution
- safeguarded invariant: masked values cannot leak raw originals
- preview hash changes only when resolved decisions change
- token-linked and area-mask-backed findings render correctly
- dual-control blocks invalid review completion
- approved runs reject later mutation
- visual regression for workspace states
- accessibility and keyboard coverage for review flows

### Reviewer-safety expectations
- bounded controlled scrolling in workspace and dialogs
- clear focus visibility
- no keyboard traps
- calm conflict and lock-state UX
- no misleading preview readiness or approval states
- reviewer actions remain auditable and exact

### Production-hardening direction
- gates must be deterministic, explainable, CI-friendly
- failure artefacts must be reviewable
- privacy regressions must block activation or promotion when they undermine safe output guarantees

## Implementation scope

### 1. Canonical privacy regression pack
Implement or refine one canonical regression pack for the privacy tranche.

Requirements:
- synthetic disclosure fixtures
- direct-identifier fixtures
- near-miss fixtures
- unreadable-risk fixtures
- overlapping-span fixtures
- dual-review-required override fixtures
- fixture metadata is durable and reviewable
- no public data dependencies

### 2. Disclosure leak tests
Add explicit leakage checks.

Requirements:
- masked values cannot leak raw originals into safeguarded preview artefacts
- run-level output manifest and preview artefacts do not reintroduce raw originals
- token-linked and area-mask-backed cases are both covered
- false positives and overrides do not create accidental disclosure paths
- failures identify the exact fixture and slice

### 3. Reviewer-safety browser checks
Add browser-level reviewer safety coverage.

At minimum cover:
- privacy workspace default, selected-finding, override, modal, and preview states
- next-unresolved navigation
- page-approval and complete-review gating states
- compare route states if present
- lock/approved-state surfaces
- keyboard-only review flow
- focus visibility and no-trap behavior
- reflow/zoom safety in bounded regions

### 4. Activation and approval blockers from failed gates
Wire regression truth into the repo’s operational model.

Requirements:
- failed privacy gates block activation-ready state in CI and local release checks
- docs explain which failures are hard blockers
- no one-off hidden suppression path
- approved run activation should not be represented as production-safe in docs or release checks when privacy gates are red

This can be implemented as CI/release gating plus explicit documentation and status output. Do not invent a runtime block if the repo’s release model already treats these as build/release gates.

### 5. Deterministic visual and accessibility baselines
Expand the browser suite coherently.

Requirements:
- visual baselines for privacy workspace, preview modes, override states, and lock states
- accessibility scans on privacy routes
- keyboard regression coverage
- artefacts are reviewable
- no second browser test framework

### 6. Decision/review/integrity regression
Add end-to-end coverage for the canonical review lifecycle.

At minimum cover:
- finding decisions append events
- page review state transitions
- dual-control rejection when the same user attempts second review
- approved-run immutability
- preview status transitions
- run-level output manifest readiness when applicable

### 7. CI integration and artefact workflow
Wire the suite into the existing pipeline.

Requirements:
- privacy regressions run in CI
- visual and functional failures produce useful artefacts
- fixture and baseline update workflow is documented
- commands match the repo
- no giant flaky browser matrix

### 8. Documentation
Document:
- synthetic disclosure corpus ownership
- hard-blocking privacy gates
- reviewer-safety checks
- baseline update process
- how later governance/export prompts should treat these gates as prerequisites

## Required deliverables
Create or refine the closest coherent equivalent of:

### Tests / fixtures / CI
- canonical privacy regression pack
- synthetic disclosure tests
- reviewer-safety browser checks
- visual and accessibility baselines
- CI wiring and artefact flow

### Docs
- privacy regression and disclosure-safety doc
- reviewer-safety and activation-blocker doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**` only if tiny deterministic test hooks are needed
- `/api/**` only if tiny deterministic test hooks are needed
- `/web/**` only if tiny deterministic UI test hooks are needed
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- new detector logic
- new masking logic
- governance/export features
- a second regression framework
- broad unstable browser matrices
- noisy flaky tests

## Testing and validation
Before finishing:
1. Verify the synthetic disclosure pack runs deterministically.
2. Verify disclosure leaks are caught for token-linked and area-mask-backed cases.
3. Verify reviewer-safety keyboard and focus checks pass.
4. Verify dual-control and approved-run immutability regressions are covered.
5. Verify visual baselines exist for key privacy workspace states.
6. Verify accessibility scans run on the privacy surfaces.
7. Verify CI wiring produces useful failure artefacts.
8. Verify docs match the implemented privacy gate and baseline process.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- privacy regression packs are real
- synthetic disclosure tests are real
- reviewer-safety checks are real
- CI can block unsafe privacy regressions
- failing regression runs emit structured artefacts and runbook-linked error codes for reviewer triage
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

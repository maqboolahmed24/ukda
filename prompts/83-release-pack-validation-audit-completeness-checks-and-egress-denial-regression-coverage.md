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
   - `/phases/phase-08-safe-outputs-export-gateway.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — export request/review schemas, release-pack artifacts, candidate snapshots, receipt logic, route-permission matrix, CI/security tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second validation framework, a second release-pack serializer, or a second egress-denial test stack.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for release-pack content, audit completeness, no-bypass egress, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that release packs are deterministic, reviewable, and unable to leave the system except through the single export gateway.

## Objective
Ship release-pack validation, audit-completeness checks, and egress-denial regression coverage.

This prompt owns:
- deterministic validation of request-scoped release packs
- audit-completeness verification across request submission, review, approval, receipt, and export events
- route-permission and storage-level egress-denial regression suites
- request-detail validation summaries where useful
- CI hard-blockers for invalid release packs or egress bypasses
- deterministic failure artefacts for engineers and operators

This prompt does not own:
- export request creation semantics
- reviewer dashboard UX
- provenance proof or bundle generation
- a second release-pack pipeline
- a second security regression stack

## Phase alignment you must preserve
From Phase 8 and Phase 11:

### Existing release-pack rules
Release pack includes:
- file list, sizes, and hashes
- candidate snapshot ID and request revision
- baseline policy snapshot hash or Phase 7 policy version
- candidate source-artifact kind and immutable source-artifact reference
- approved model references by role
- approved model checksums or immutable version references for every included role
- redaction counts by category
- reviewer override count
- conservative area-mask count
- risk flags and classifier reason codes
- manifest hash and integrity status
- pinned governance manifest and ledger references
- release-review checklist

### Existing egress rules
- direct candidate-download routes for external release are blocked
- only approved export requests can write to `safeguarded/exports`
- only internal gateway service account can attach receipts
- there is no user-facing `GET /download` bypass route
- receipt reads do not create a bypass download route

### Existing hardening intent
- route-permission matrix denies non-gateway export paths by default
- failure artefacts must be useful and reviewable
- unsafe release regressions must block promotion

## Implementation scope

### 1. Canonical release-pack validator
Implement or refine a deterministic release-pack validation layer.

Requirements:
- validates required fields and pinned lineage
- checks internal consistency between:
  - candidate snapshot
  - request revision
  - risk classification
  - governance pins
  - model lineage
  - redaction metrics
- validates manifest integrity references
- validates that the frozen request pack has not drifted from its pinned candidate snapshot
- no second serializer or parallel pack model is introduced

### 2. Audit-completeness checker
Implement a deterministic checker over append-only histories.

Requirements:
- validates that request submission, review actions, terminal decision, receipt attachment, and export completion histories are complete and coherent for each request state
- detects missing or contradictory request/review/receipt events
- validates that request projections match underlying append-only histories
- no one-off manual inspection is needed to prove audit completeness

### 3. Egress-denial regression suite
Expand hardening coverage.

Requirements:
- candidate direct-download attempts fail closed
- bundle or request-based download bypasses fail closed
- only gateway identity can write to `safeguarded/exports`
- user-facing receipt mutation attempts fail closed
- denied attempts are logged safely
- results are CI-friendly and reviewable

### 4. Validation summaries
Expose the results where low churn and useful.

Requirements:
- request detail or ops surfaces can show release-pack validity and audit-completeness status
- validation-summary reads must follow the existing request-detail and ops-surface RBAC for the underlying export request; do not widen access
- no giant admin console required
- invalid states remain exact and blockable
- summaries are typed and machine-readable as well as human-readable

### 5. CI and failure artefacts
Wire the suite into existing quality gates.

Requirements:
- release-pack validation failures block the relevant pipeline
- audit-completeness failures block the relevant pipeline
- egress-denial regressions block the relevant pipeline
- failure summaries identify exact request/fixture/route/storage violation
- no second CI stack

### 6. Documentation
Document:
- release-pack validation rules
- audit-completeness expectations
- egress-denial test scope
- operational meaning of failures
- what Prompt 84–86 will assume from these gates

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / tests / CI
- release-pack validator
- audit-completeness checker
- egress-denial regression tests
- CI wiring and failure artefacts

### Web
- only small validation summary surfaces if useful and coherent

### Docs
- release-pack validation and audit-completeness doc
- egress-denial regression and hard-blocker doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**` only if tiny validation helpers are needed
- `/web/**` only if small validation summary refinements are useful
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- export request creation
- reviewer dashboard features
- provenance or bundle generation
- a second validator stack
- a second egress-denial framework

## Testing and validation
Before finishing:
1. Verify release packs validate deterministically against pinned request and candidate lineage.
2. Verify audit completeness catches missing or contradictory request/review/receipt events.
3. Verify request projections stay consistent with append-only histories.
4. Verify candidate/download/receipt bypass attempts fail closed.
5. Verify only gateway identity can write to `safeguarded/exports`.
6. Verify validation-summary surfaces enforce the same request/ops RBAC boundaries as their parent routes.
7. Verify CI wiring blocks unsafe regressions.
8. Verify docs match the implemented validation and egress-denial behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- release-pack validation is real
- audit-completeness checks are real
- egress-denial regression coverage is real
- unsafe export regressions become hard blockers
- later provenance and bundle phases can assume trustworthy export inputs
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

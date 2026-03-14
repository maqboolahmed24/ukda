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
   - `/phases/phase-06-redaction-manifest-ledger-v1.md`
   - `/phases/phase-07-policy-engine-v1.md`
3. Then review the current repository generally — policy routes, privacy rerun hooks, governance-ready checks, compare routes, shared UI/data-layer primitives, regression fixtures, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second rerun engine, a second rollback mechanism, or hidden activation gates outside the canonical policy and privacy run contracts.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for rerun prerequisites, compare behavior, regression gates, and activation safety.
- Official docs win only for implementation mechanics.
- Preserve the rule that policy evolution creates new outputs and readable diffs instead of mutating history, and that validated draft revisions may be used for comparison-only reruns without activating them.

## Objective
Implement policy reruns, regression packs, rollback paths, and activation gates without workflow confusion.

This prompt owns:
- document-scoped policy rerun orchestration
- compare-ready rerun candidates against approved governance-ready source runs
- regression packs and pre-activation warnings for risky policy changes
- safe rollback path by creating a new draft revision from a prior validated revision rather than mutating history
- document-scoped privacy compare route integration from policy pages
- clear separation between comparison-only reruns and policy activation

This prompt does not own:
- policy editor UX itself
- detector or masking engine internals
- export/governance workflows beyond the prerequisite checks
- a second compare system
- silent policy rollback or silent policy promotion

## Phase alignment you must preserve
From Phase 7 Iteration 7.3:

### Required APIs
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/rerun?policyId={policyId}`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`
- `POST /projects/{projectId}/policies/{policyId}/rollback-draft?fromPolicyId={fromPolicyId}` (or closest coherent equivalent that creates a new rollback-seeded `DRAFT` lineage)
- rollback identifier mapping is deterministic: route `{policyId}` anchors the policy lineage/context for the new draft, and `fromPolicyId` names the prior validated revision used as the rollback seed

### Required rerun rules
- rerun available only to `PROJECT_LEAD` and `ADMIN`
- source run must be:
  - approved under Phase 5 review
  - governance-ready under Phase 6
- target `policyId` must:
  - belong to same project
  - be either current `ACTIVE` or a validated `DRAFT` revision in the same lineage
  - have `validation_status = VALID`
  - have `validated_rules_sha256` matching current `rules_json`
- reruns against validated `DRAFT` revisions are comparison-only candidates and do not activate the draft policy or change `project_policy_projections.active_policy_id`

### Existing compare route
- `/projects/:projectId/documents/:documentId/privacy/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}&page={pageNumber}&findingId={findingId}&lineId={lineId}&tokenId={tokenId}`

### Required warnings and gates
- changed-pages summary
- compare runs by policy version
- pre-activation warnings for broad allow rules or inconsistent thresholds
- deterministic rerun reproducibility from same approved decisions + same target policy

## Implementation scope

### 1. Canonical rerun orchestration
Implement or refine the canonical policy-rerun path.

Requirements:
- rerun uses prior approved reviewed decisions plus explicit target policy
- source run remains immutable
- new redaction run lineage is append-only
- rerun candidate is clearly tagged with:
  - `policy_id`
  - `policy_family_id`
  - `policy_version`
- no route-local ad hoc rerun path

### 2. Governance-ready and validation gates
Harden rerun entry checks.

Requirements:
- reject reruns from non-approved or non-governance-ready source runs
- reject invalid, retired, or cross-project target policies
- reject stale validated drafts whose current rules no longer match their validated hash
- error surfaces are exact and typed
- no hidden override path

### 3. Comparison-only draft reruns
Support safe experimentation.

Requirements:
- validated `DRAFT` revisions can produce comparison-only rerun candidates
- these reruns do not activate the target draft revision
- the UI makes this distinction explicit
- comparison-only candidates remain immutable and auditable
- users cannot mistake compare-ready output for active-policy output

### 4. Document-scoped compare integration
Refine the compare path and navigation.

Requirements:
- policy pages can link into document-scoped privacy compare once a rerun candidate exists
- compare surfaces show policy-version context clearly
- changed-pages summary is present
- broad allow or inconsistent-threshold warnings surface before activation
- compare remains read-only and analytic

### 5. Safe rollback path
Implement a non-destructive rollback flow.

Requirements:
- rollback does not reactivate or mutate a historical revision in place
- rollback creates a new `DRAFT` revision in the route `{policyId}` lineage/context, seeded from prior validated `fromPolicyId` revision in that same lineage/context
- that new draft can be validated, rerun-compared, and then activated through the normal guarded flow
- rollback lineage is explicit and auditable
- no “instant rollback” that bypasses validation or compare

### 6. Regression packs and pre-activation gates
Add policy-regression coverage.

Requirements:
- reproducibility tests for reruns from same approved decisions + same target policy
- diff summaries match underlying safeguarded preview, manifest, and ledger changes
- guardrails for broad allow rules and inconsistent thresholds are deterministic
- pre-activation warnings are clear and typed
- policy pages can surface regression outcomes without creating a second testing UI

### 7. Audit and role behavior
Use the canonical audit path.

Requirements:
- `POLICY_RERUN_REQUESTED`
- `POLICY_RUN_COMPARE_VIEWED`
- role behavior:
  - `PROJECT_LEAD` and `ADMIN` can request reruns
  - `REVIEWER` and `AUDITOR` are read-only on compare surfaces
- no second audit path

### 8. Documentation
Document:
- rerun prerequisites
- comparison-only draft reruns
- rollback path semantics
- regression-pack expectations
- what Prompt 77 will deepen around lineage, approvals, and explainability

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- policy rerun orchestration
- rerun gating and error contracts
- compare-ready rerun candidate handling
- rollback-seeded draft creation path
- regression-pack hooks
- tests

### Web
- policy-to-privacy compare navigation
- compare-run policy context
- rollback path UX
- pre-activation warnings

### Docs
- policy rerun and rollback doc
- regression-pack and activation-gate doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**` if rerun orchestration needs worker integration
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small compare/warning/rollback refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- policy editor itself
- policy engine internals
- export/governance features beyond gating prerequisites
- a second compare surface
- silent rollback or silent activation

## Testing and validation
Before finishing:
1. Verify reruns are blocked unless source run is approved and governance-ready.
2. Verify validated `DRAFT` revisions can be rerun for comparison without activation.
3. Verify invalid or retired targets are rejected.
4. Verify rollback creates a new draft lineage instead of mutating historical revisions.
5. Verify compare surfaces show correct policy-version context and changed-pages summaries.
6. Verify broad-allow and inconsistent-threshold warnings are surfaced deterministically.
7. Verify `PROJECT_LEAD` and `ADMIN` can rerun while `REVIEWER` and `AUDITOR` remain read-only.
8. Verify docs match the implemented rerun, rollback, and regression behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- policy reruns are real
- comparison-only draft reruns are real
- rollback is safe and non-destructive
- regression and activation gates are real
- compare and activate paths use distinct UI controls and API permissions with explicit status labels
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

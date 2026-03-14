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
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — accessibility suites, governance/provenance/privacy/export gates, search/index quality checks, bundle verification, route-permission matrices, CI workflows, docs, and current admin surfaces — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second readiness-audit framework, a second evidence matrix, or duplicate hardening gates outside the canonical CI and admin/ops evidence paths.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for cross-phase safety requirements, admin/auditor role boundaries, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that production readiness is not claimed until accessibility, governance, privacy, provenance, and egress controls all have concrete evidence.

## Objective
Run cross-phase production-readiness audits for accessibility, governance, privacy, provenance, and egress controls.

This prompt owns:
- a canonical readiness-audit matrix spanning the implemented product
- CI and machine-readable evidence collection for:
  - accessibility
  - governance artefact integrity
  - privacy leakage and review safety
  - provenance proof and bundle verification
  - no-bypass egress
  - search/index and derivative safety
- admin/operator-readable readiness summaries
- hard-blocking failure semantics for release readiness

This prompt does not own:
- new product features
- a second testing stack
- new export, governance, or search behavior beyond surfacing audit truth
- a public status page or marketing launch checklist

## Phase alignment you must preserve
From the Blueprint, UI contract, and Phase 11 completion posture:

### Cross-phase readiness themes to audit
- accessibility and keyboard-first interaction on critical routes and dense workspaces
- governance artefact integrity:
  - manifest
  - ledger
  - readiness projection
  - candidate lineage
- privacy controls:
  - no disclosure leaks
  - dual-control and lock semantics
  - safeguarded preview safety
- provenance:
  - proof generation
  - bundle verification
  - replay/recovery confidence
- egress:
  - no bypass around the export gateway
  - no direct download or storage-write escapes
- discovery/search:
  - token-anchor activation gates
  - derivative suppression and anti-join gates

### Role boundaries
- readiness evidence is primarily an `ADMIN` concern
- read-only audit visibility may be surfaced to `AUDITOR` where the repo already has a safe operations/readiness path
- do not widen reviewer or researcher access to governance or security-only evidence

### Phase 11 intent
- claims must be backed by measured evidence
- restore/failover/recovery must be rehearsed, not merely documented
- security hardening includes tracked remediation
- go-live must be justified by evidence, not by optimism

## Implementation scope

### 1. Canonical readiness-audit matrix
Implement or refine one machine-readable readiness matrix.

Requirements:
- explicit categories and pass/fail status
- evidence references for each category
- no hidden spreadsheet or manual-only checklist as the source of truth
- suitable for CI and admin review
- no second matrix for the same platform state

### 2. Cross-phase CI gate aggregation
Aggregate existing gates and add missing integrations.

Requirements:
- accessibility gate results
- privacy leak and review-safety results
- governance manifest/ledger integrity results
- provenance replay and verification results
- egress-denial results
- search/index quality and derivative safety results
- capacity/recovery/security status where already implemented
- failures remain attributable and reviewable

### 3. Admin/operator readiness summary
Expose the readiness truth coherently.

Requirements:
- summary can be surfaced through an existing admin operations/readiness surface if the repo already has one
- otherwise create the smallest coherent admin-only summary route or extend the existing operations overview
- no second admin shell
- no vague “green/red” only; evidence links and blocker details are available

### 4. Auditor-readable readiness slices
Where safe and already aligned to role boundaries, expose read-only readiness evidence to `AUDITOR`.

Requirements:
- safe auditor slices are limited to category-level pass/fail plus evidence references for accessibility, governance artefact integrity, privacy gate status (without raw disclosure artefacts), provenance verification, egress-denial, and discovery safety checks
- no widening into live recovery or admin-only security mutation paths
- exact role enforcement server-side

### 5. Evidence and artifact storage
Persist or package readiness evidence coherently.

Requirements:
- readiness evidence references test and validation outputs deterministically
- artifact references do not depend on mutable temporary filenames alone
- evidence can be reviewed after the fact
- no public storage exposure

### 6. Documentation
Document:
- readiness categories
- evidence sources
- blocking vs warning-level failures
- how Prompt 99 and 100 consume the readiness result for release automation and launch review

## Required deliverables
Create or refine the closest coherent equivalent of:

### CI / contracts / ops surfaces
- readiness-audit matrix
- CI gate aggregation
- admin readiness summary
- tests or checks to verify evidence references are coherent

### Docs
- cross-phase readiness audit doc
- release-readiness evidence and blocker policy doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- CI/workflow files
- `/api/**` only if a tiny admin/readiness read helper is needed
- `/web/**` only if a small admin readiness summary extension is needed
- `/packages/contracts/**` only if tiny typed readiness structures help
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- a second test stack
- new product workflows
- public status/reporting
- a second admin shell
- broad role-access changes

## Testing and validation
Before finishing:
1. Verify the readiness matrix is machine-readable and backed by actual evidence.
2. Verify all required cross-phase categories are represented.
3. Verify failing evidence produces hard-blocking readiness output where appropriate.
4. Verify evidence references are stable and reviewable.
5. Verify any auditor-readable readiness slices remain within safe role boundaries.
6. Verify auditor-readable readiness slices do not expose raw disclosure artefacts or admin-only recovery/security evidence payloads.
7. Verify docs match the implemented readiness audit behavior.
8. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- cross-phase readiness audits are real
- release-blocking evidence is aggregated coherently
- admin/operator readiness visibility is real
- readiness claims are backed by actual evidence, not anecdotes
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

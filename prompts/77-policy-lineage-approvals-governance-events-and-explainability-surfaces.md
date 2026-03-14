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
   - `/phases/phase-07-policy-engine-v1.md`
3. Then review the current repository generally — policy tables, policy events, policy compare surfaces, rerun routes, governance artefacts, pseudonym registry routes, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second policy-history store, a second approval trail, or a separate explainability model that drifts from canonical policy lineage.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for policy lineage, snapshot hashes, event history, approval semantics, and explainability boundaries.
- Official docs win only for implementation mechanics.
- Preserve the rule that policy history is append-only, rule snapshots are immutable, and local LLM assistance remains reviewer-visible metadata rather than authoritative policy logic.

## Objective
Persist policy lineage, approvals, governance events, and explainability surfaces end to end.

This prompt owns:
- end-to-end policy lineage surfaces
- immutable rule snapshot and approval trail presentation
- policy usage lineage across policy-rerendered outputs and governance artefacts
- explainability surfaces that show why the policy would choose a given action without exposing hidden reasoning
- policy approval/activation summaries and auditability
- linkage between policy revisions, reruns, manifests, ledgers, and pseudonym registry behavior
- typed history/explainability APIs and UI

This prompt does not own:
- policy editor UX
- rerun orchestration itself
- pseudonym or generalisation engine internals
- export workflows
- a second lineage or explanation store

## Phase alignment you must preserve
From Phase 7 Iterations 7.0–7.3:

### Existing immutable lineage
- `policy_events` are append-only
- each create/edit/validate/activate/retire event stores exact `rules_sha256` and `rules_snapshot_key`
- policy history must be reconstructable from events, not mutable rows
- activation retires previous active revision and updates `project_policy_projections`
- policy reruns extend `redaction_runs` with explicit `policy_id`, `policy_family_id`, and `policy_version`

### Existing explainability boundaries
- indirect-identifier handling must be explainable, reviewable, and regression-tested
- local LLM assistance may explain or group risk signals, but policy rules remain authoritative
- reviewer explanation mode is part of policy rules
- no hidden reasoning text should be persisted or shown

### Existing role surfaces
- `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, and read-only `AUDITOR` can read policy list/detail/compare
- only `PROJECT_LEAD` and `ADMIN` can create/edit/validate/activate/retire
- lineage/usage/explainability/snapshot read contracts inherit the same read roles (`PROJECT_LEAD`, `REVIEWER`, `ADMIN`, read-only `AUDITOR`)

### Required lineage and explainability read contracts
Use or refine (or the closest coherent equivalent preserving one canonical read contract):
- `GET /projects/{projectId}/policies/{policyId}/lineage`
- `GET /projects/{projectId}/policies/{policyId}/usage`
- `GET /projects/{projectId}/policies/{policyId}/explainability`
- `GET /projects/{projectId}/policies/{policyId}/snapshots/{rulesSha256}`
- `/projects/:projectId/policies/:policyId` as the canonical route hosting lineage, usage, approval, and explainability reads

## Implementation scope

### 1. Canonical policy lineage reads
Implement or refine the canonical policy-lineage read model.

Requirements:
- policy detail can show lineage:
  - seeded baseline origin
  - supersedes and superseded-by
  - active / retired state
  - validation history
  - activation history
- no second history source outside `policy_events` and canonical policy rows
- lineages remain reconstructable and exact

### 2. Immutable rule snapshot access
Make rule snapshots inspectable.

Requirements:
- current policy detail can expose exact rule snapshot references and hashes
- history views can inspect prior snapshots without depending on mutable draft state
- no raw mutable draft edits are presented as historical truth
- retrieval remains internal-only and typed

### 3. Policy usage lineage
Expose where a policy revision has been used.

Requirements:
- show which redaction reruns used a given policy revision
- show which governance artefacts (manifest/ledger) were produced from outputs rendered under that policy
- show policy family/version context in these usage links
- no need to create export workflows here
- usage lineage remains read-only and exact

### 4. Approval and activation summaries
Surface the authoritative approval trail.

Requirements:
- who validated
- when validated
- what rules hash was validated
- who activated
- when activated
- whether the active policy differs from the currently viewed revision
- retire summaries remain exact and explain impact without hype

### 5. Explainability surfaces
Implement reviewer-visible explainability.

Requirements:
- explainability surface shows:
  - category action rules
  - confidence thresholds
  - reviewer requirements
  - escalation flags
  - pseudonymisation / generalisation controls
  - explanation mode settings
- where useful, show policy examples or rule traces using deterministic sample cases or real rerun comparisons already present in the repo
- local LLM grouping/explanation remains clearly secondary and non-authoritative
- no hidden reasoning or chain-of-thought is surfaced

### 6. Pseudonym and transform linkage summaries
Policy affects registries and transforms.

Requirements:
- show linked pseudonym strategy settings and alias strategy version where useful
- show generalisation specificity ceilings and transform settings where useful
- do not build a second registry or transform UI
- remain consistent with canonical policy rules and route ownership

### 7. Audit and tests
Use the canonical audit path and add coverage.

At minimum cover:
- policy history is reconstructable from append-only events
- exact rule snapshots can be traced at create/edit/validate/activate/retire steps
- policy usage lineage points to correct reruns and governance artefacts
- explainability surfaces remain deterministic and do not surface hidden reasoning
- RBAC for read vs mutate surfaces remains correct

### 8. Documentation
Document:
- policy lineage model
- approval and activation history semantics
- policy usage lineage
- explainability boundaries
- how later governance/export/provenance phases can consume these policy lineage surfaces

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- policy-lineage and usage read surfaces
- immutable rule snapshot access
- typed explainability contracts
- tests

### Web
- policy detail lineage surface
- approval/activation summary
- usage lineage links
- explainability surface

### Docs
- policy lineage and explainability doc
- policy usage lineage and approval-trail doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small lineage/history/explainability refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- policy editor UX
- rerun orchestration
- pseudonym engine logic
- export workflows
- a second history or explanation system

## Testing and validation
Before finishing:
1. Verify policy history is reconstructable from append-only events.
2. Verify exact rule snapshots are traceable at every lifecycle event.
3. Verify policy usage lineage points to correct reruns and governance artefacts.
4. Verify explainability surfaces stay deterministic and bounded.
5. Verify no hidden reasoning text is shown or persisted.
6. Verify RBAC boundaries remain correct.
7. Verify docs match the implemented lineage and explainability behavior.
8. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- policy lineage is real and inspectable
- approvals and governance events are explicit
- policy usage lineage is real
- explainability surfaces are useful and bounded
- later phases can consume stable policy lineage without extra reconstruction
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

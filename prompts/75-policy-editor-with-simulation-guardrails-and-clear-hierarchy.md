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
   - `/phases/phase-07-policy-engine-v1.md`
3. Then review the current repository generally — policy routes, policy compare surfaces, shared UI primitives, typed contracts, event timelines, current data layer, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second policy route family, a second draft-edit flow, or conflicting compare navigation semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for policy fields, lifecycle, compare rules, RBAC, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that policy authoring is project-scoped, draft-first, validation-gated, activation-safe, and never buried inside a document workflow.

## Objective
Craft the policy editor as a sleek expert web tool with simulation, guardrails, and clear hierarchy.

This prompt owns:
- the policy editor experience on top of the canonical Phase 7 model
- draft editing UX
- validation and activation guardrails
- compare and baseline-diff navigation inside the editor flow
- simulation panels that explain likely rule effects without triggering a real rerun
- stale-write protection and unsaved-change handling
- history and impact surfaces for policy authors

This prompt does not own:
- policy rerun orchestration
- rerun compare across actual privacy runs
- pseudonym registry implementation
- indirect-identifier engine implementation
- export/governance workflows

## Phase alignment you must preserve
From Phase 7 Iteration 7.0 and 7.2:

### Existing routes and access
- `/projects/:projectId/policies`
- `/projects/:projectId/policies/active`
- `/projects/:projectId/policies/:policyId`
- `/projects/:projectId/policies/:policyId/compare?against={otherPolicyId}`
- `/projects/:projectId/policies/:policyId/compare?againstBaselineSnapshotId={baselineSnapshotId}`

Read access:
- `PROJECT_LEAD`
- `REVIEWER`
- `ADMIN`
- read-only `AUDITOR`

Mutating access:
- `PROJECT_LEAD`
- `ADMIN`

### Existing policy model
Rules JSON must support:
- category actions
- confidence thresholds
- reviewer requirements
- escalation flags
- pseudonymisation mode and aliasing rules
- generalisation transforms by category and specificity ceiling
- reviewer explanation mode for local LLM-assisted risk summaries

### Existing lifecycle rules
- draft revisions are editable
- `PATCH` requires current `version_etag`
- editing a draft clears validation state
- activation is blocked unless the latest successful validation still matches the current rules
- retire action applies only to `ACTIVE` revisions
- compare requests must include exactly one target

### Required UX intent
- expert-facing, dense, calm, high-trust
- dark, minimal, operational
- no giant form-wall
- no “AI policy copilot” gimmicks
- simulation explains impact, but does not mutate state and does not trigger document reruns

## Implementation scope

### 1. Canonical editor surface
Implement or refine the policy editor on the canonical policy detail route or the repo’s closest coherent equivalent.

Requirements:
- one coherent policy detail/editor surface
- clear read-only vs editable draft state
- grouped rule sections with strong hierarchy
- exact save/validate/activate/retire affordances
- role-aware controls
- no second policy UI elsewhere

### 2. Draft editing UX
Implement or refine draft editing for:
- category actions
- confidence thresholds
- reviewer requirements
- escalation flags
- pseudonymisation mode
- generalisation specificity ceilings
- reviewer explanation mode

Requirements:
- editing only on `DRAFT`
- clear dirty-state handling
- stale-write protection using `version_etag`
- validation state visibly resets after edits
- no silent autosave

### 3. Simulation and guardrails
Implement a non-destructive simulation panel.

Requirements:
- simulation uses deterministic sample or representative inputs available from the repo’s current policy context
- no live document rerun is triggered here
- simulation can show likely action outcomes such as:
  - mask
  - pseudonymise
  - generalise
  - needs review
- broad allow rules, contradictory thresholds, unsupported combinations, or overly specific transformations are surfaced clearly
- simulation remains advisory; validation rules remain authoritative

### 4. Validation and activation guardrails
Refine the policy action workflow.

Requirements:
- validate action runs through the canonical validation API
- activation is blocked unless validation matches the exact current draft rules
- retire flow shows explicit impact summary
- compare links are available before activation so authors can inspect changes
- error and warning states are calm, exact, and useful

### 5. Compare and baseline context inside the editor
Integrate compare surfaces into the authoring workflow.

Requirements:
- compare with previous revision
- compare with seeded baseline snapshot when allowed
- only one compare target at a time
- deep-link-safe navigation
- changed sections are easy to inspect
- compare does not become a second editor

### 6. History and timeline surface
Use append-only policy events coherently.

Requirements:
- policy history timeline visible in detail view
- events for create/edit/validate/activate/retire are readable and exact
- event timeline remains separate from mutable current draft state
- history can show actor, time, and rules snapshot hash/key metadata where useful

### 7. Browser and accessibility quality
Harden the editor UX.

Requirements:
- keyboard-safe form and toolbar navigation
- visible focus
- no keyboard traps
- bounded scrolling in dense panels
- reduced-motion/high-contrast behavior remains coherent
- visual baselines for:
  - read-only active policy
  - editable draft
  - validation errors
  - compare-linked draft state
  - retire-impact summary

### 8. Documentation
Document:
- policy editor ownership
- simulation boundaries
- validation and activation guardrails
- compare navigation rules
- how Prompt 76 will use this editor in safe rerun and rollback workflows

## Required deliverables
Create or refine the closest coherent equivalent of:

### Web
- policy editor on the canonical policy detail route
- simulation panel
- validation and activation guardrails
- timeline/history surface
- browser tests and visual baselines

### Backend / contracts
- only tiny helper/typed read refinements if strictly needed for simulation or editor coherence

### Docs
- policy editor UX contract doc
- policy simulation and guardrail doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/web/**`
- `/api/**` only if tiny helper/typed read refinements are strictly needed
- `/packages/contracts/**`
- `/packages/ui/**`
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- policy rerun orchestration
- rerun compare across actual redaction runs
- pseudonym registry logic
- indirect-identifier transform engine
- a second policy editor route family

## Testing and validation
Before finishing:
1. Verify only `DRAFT` policies are editable.
2. Verify stale `version_etag` writes are rejected safely.
3. Verify editing invalidates prior validation.
4. Verify simulation is non-destructive and does not create reruns.
5. Verify compare navigation uses exactly one comparison target.
6. Verify role boundaries for read vs mutate actions.
7. Verify keyboard, focus, and visual states are coherent.
8. Verify docs match the implemented editor and simulation behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the policy editor is real
- simulation and guardrails are real
- validation and activation flows are clear and safe
- compare and history are integrated coherently
- the editor remains dense, dark, calm, and expert-grade
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

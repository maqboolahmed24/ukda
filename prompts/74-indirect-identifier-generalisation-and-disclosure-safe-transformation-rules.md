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
   - `/phases/phase-07-policy-engine-v1.md`
   - `/phases/phase-08-safe-outputs-export-gateway.md`
   - `/phases/phase-10-granular-data-products.md`
3. Then review the current repository generally — policy schemas, privacy finding models, pseudonym registry foundations, preview/output generation paths, compare shells, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second transformation engine, a second specificity model, or conflicting disclosure-safe derivative semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. current repository state as the implementation reality to reconcile with
  2. this prompt
  3. the precise `/phases` files listed above
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for generalisation rules, specificity ceilings, indirect-risk heuristics, reviewer explanation boundaries, and downstream safeguarded-output compatibility.
- Official docs win only for implementation mechanics.
- Preserve the rule that indirect-identifier handling is deterministic, explainable, policy-controlled, and auditable; local assist may explain but may not exceed policy specificity ceilings or bypass deterministic policy evaluation.

## Objective
Add indirect-identifier generalisation and disclosure-safe transformation rules for higher-risk outputs.

This prompt owns:
- deterministic generalisation transforms
- indirect-risk heuristics and grouping
- policy-controlled specificity ceilings
- reviewer-visible explanation metadata for why generalisation fired
- transformation support for:
  - exact date -> month/year or year only
  - town -> county or region
  - exact age -> age band
- run/result metadata needed to preserve transformed-output lineage
- compare-ready output distinctions between masked, pseudonymized, and generalized values
- downstream-safe derivative compatibility for later Phase 8 and Phase 10 consumers

This prompt does not own:
- the policy editor UX
- full policy rerun orchestration
- export-request workflows
- derivative index generation
- external LLM services
- a second transformation engine

## Phase alignment you must preserve
From Phase 7 Iteration 7.2 and downstream compatibility expectations:

### Required transformations
Support generalisation actions:
- exact date -> month/year or year only
- town -> county or region
- exact age -> age band

### Indirect-risk heuristics
Support heuristic combinations such as:
- place + rare occupation + exact date
- uncommon kinship term + small locality

Optional assist:
- local LLM assistance may group or explain ambiguous indirect-risk combinations for reviewers
- policy rules remain authoritative for the final action applied to the output
- local LLM explanations cannot request a more specific output than the active policy allows

### Output and lineage rules
- policy reruns remain document-scoped and emit new `redaction_runs`, `redaction_manifests`, and `redaction_evidence_ledgers`
- prior runs are never mutated
- generalized output never exceeds the configured specificity ceiling
- later Phase 8 and Phase 10 consumers must be able to read the resulting transformed outputs and lineage without reinterpretation

### Required web behavior
- policy controls for granularity by category
- reviewer-facing explanation of why a generalisation rule fired
- run comparison view showing masked vs pseudonymized vs generalized output

### Required tests
- date, place, and age banding rules are deterministic
- generalized output never exceeds the configured specificity ceiling
- local LLM-assisted explanations cannot request a more specific output than the active policy allows
- indirect-risk findings can be rerendered under new policy versions without mutating prior runs
- local LLM-assisted grouping remains reviewer-visible metadata and does not bypass deterministic policy evaluation

## Implementation scope

### 1. Canonical generalisation engine
Implement or refine one canonical transformation engine for indirect identifiers.

Requirements:
- deterministic date/place/age-band transforms
- policy-driven specificity ceilings
- no second hidden transform path in route handlers
- no silent “best effort” behavior outside explicit policy rules
- transformed outputs remain auditable and lineage-safe

### 2. Indirect-risk heuristic layer
Implement or refine indirect-risk grouping and escalation.

Requirements:
- support the policy-described risk combinations
- group related evidence into a reviewer-visible explanation payload
- keep the heuristic output explicit and typed
- do not auto-apply more specificity than policy allows
- no opaque scoring system with no explainable rationale

### 3. Policy evaluation support
Extend policy evaluation coherently.

Requirements:
- generalisation transforms are evaluated through the canonical policy rules
- category granularity is explicit
- specificity ceiling enforcement is deterministic
- pseudonymisation and masking remain distinct actions
- outputs preserve which action was actually applied

### 4. Reviewer-visible explanation metadata
Implement bounded explanation metadata.

Requirements:
- reviewer-facing explanation of why a generalisation rule fired
- optional local assist grouping notes remain reviewer-visible metadata only
- hidden reasoning or chain-of-thought is never stored
- explanation payloads are separate from the final transformed value
- explanation cannot authorize a more specific or less safe output than policy permits

### 5. Output and compare integration
Prepare outputs for later reruns and compare surfaces without overstepping rerun orchestration.

Requirements:
- transformed outputs remain distinguishable as masked, pseudonymized, or generalized
- compare-ready metadata exists so later rerun compare can show those distinctions clearly
- no mutation of prior run outputs
- downstream Phase 8 and Phase 10 consumers can interpret transformed outputs without guessing

### 6. Minimal web integration
Implement only the smallest useful web/read-path refinements.

Requirements:
- reviewer-visible explanation display in relevant compare or detail surfaces where low churn and coherent
- category granularity presentation where useful
- honest not-yet-rerun or not-yet-available states if full rerender compare is not yet live
- no broad policy editor UX in this prompt

### 7. Audit and regression
Use the canonical audit path where appropriate and add regression coverage.

At minimum cover:
- deterministic date/place/age transforms
- specificity ceiling enforcement
- local assist explanation cannot exceed policy limits
- indirect-risk grouped cases remain reviewer-visible metadata only
- transformed outputs remain lineage-safe and non-destructive
- no hidden reasoning is persisted

### 8. Documentation
Document:
- deterministic generalisation rules
- specificity ceilings
- indirect-risk heuristic semantics
- reviewer-visible explanation boundaries
- downstream compatibility with safeguarded outputs and derivative products
- what Prompt 75 and 76 will deepen next

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- generalisation transform engine
- indirect-risk heuristic support
- policy-evaluation extensions
- typed explanation metadata
- tests

### Web
- only minimal truthful explanation/granularity read surfaces if low churn and coherent

### Docs
- indirect-identifier generalisation doc
- specificity ceiling and explanation-boundary doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/packages/contracts/**`
- `/web/**` only if small explanation/read refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- full policy editor UX
- policy rerun orchestration
- export workflows
- derivative index generation
- external LLM services
- a second transformation engine

## Testing and validation
Before finishing:
1. Verify date, place, and age-banding rules are deterministic.
2. Verify generalized output never exceeds the configured specificity ceiling.
3. Verify local assist explanations cannot request or imply a more specific output than policy allows.
4. Verify indirect-risk grouped cases remain reviewer-visible metadata and do not bypass deterministic policy evaluation.
5. Verify transformed outputs stay lineage-safe and do not mutate prior runs.
6. Verify docs match the implemented transformation and explanation behavior.
7. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- indirect-identifier generalisation is real
- specificity ceilings are real and enforced
- reviewer-visible explanation metadata is bounded and safe
- transformed-output distinctions remain lineage-safe
- later policy rerun, export, and derivative prompts can build on a stable transformation contract
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

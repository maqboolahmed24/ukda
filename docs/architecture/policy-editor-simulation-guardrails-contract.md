# Policy Editor Simulation And Guardrails Contract

## Scope

Phase 7 Prompt 75 defines the canonical expert editor for policy authoring on:

- `/projects/{projectId}/policies/{policyId}`

This contract covers:

- editor ownership and route boundaries
- draft editing semantics and stale-write behavior
- simulation boundaries
- validation/activation/retire guardrails
- compare navigation rules for policy authors
- Prompt 76 handoff expectations

## Editor Ownership

The policy detail route is the single canonical authoring surface.

- There is no second draft editor route family.
- Policy list and compare views are supporting surfaces.
- Timeline history remains append-only and separate from mutable draft state.

## Draft Editing Model

Draft edits are grouped into explicit sections:

- policy identity and explanation mode
- category actions and category thresholds
- defaults and reviewer/escalation gates
- pseudonymisation mode and alias prefix
- date/place/age generalisation specificity ceilings

Rules:

- only `DRAFT` revisions are editable
- no autosave; save is explicit form submit
- save requires current `version_etag`
- stale `version_etag` writes are rejected and surfaced as `stale-etag`
- editing a draft invalidates prior validation until validation reruns

## Simulation Boundaries

The editor includes a deterministic simulation panel with representative sample inputs.

Simulation properties:

- advisory-only output (mask, pseudonymise, generalise, needs review, escalate, allow/review)
- deterministic for the same draft values
- non-destructive: does not patch policy state
- non-executing: does not trigger privacy reruns or document jobs

Guardrail issues surfaced in-editor include:

- broad allow rules
- threshold contradictions
- unsupported actions or pseudonym modes
- over-specific generalisation ceilings

Validation APIs remain authoritative for activation safety.

## Validation, Activation, And Retire Guardrails

Lifecycle controls in detail view enforce canonical gates:

- `Validate` available only for persisted `DRAFT` content
- `Activate` blocked unless revision is `DRAFT`, validation is `VALID`, and draft is not locally dirty
- `Retire` available only for `ACTIVE` revisions
- retire action shows explicit impact summary before submission

Failure statuses are routed into calm explicit notices:

- `stale-etag`
- `conflict`
- `forbidden`
- `action-failed`

## Compare Navigation Rules

Authoring flow includes in-context compare links:

- compare with previous revision (`supersedes_policy_id`)
- compare with seeded baseline snapshot when available

Compare semantics remain canonical:

- exactly one compare target per request (`against` xor `againstBaselineSnapshotId`)
- compare remains read-only and does not become an editor
- changed sections are summarized for faster inspection

## Timeline Separation

Policy history is rendered from append-only `policy_events` and is not inferred from mutable draft fields.

Timeline event families remain:

- create
- edit
- validate valid/invalid
- activate
- retire

## Prompt 76 Handoff

Prompt 76 should build on this editor rather than replacing it.

Expected integration points:

- reuse editor guardrail outputs to surface pre-rerun and pre-activation warnings
- keep rerun and rollback orchestration outside editor mutation paths
- retain compare links from policy authoring into document-scoped rerun compare workflows
- preserve strict separation between advisory simulation and real rerun execution

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
3. Then review the current repository generally — baseline policy snapshot logic, privacy rerun foundations, governance artefacts, shared UI primitives, current routes, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second policy store, a second active-policy projection system, or conflicting policy-lineage semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. current repository state as the implementation reality to reconcile with
  2. this prompt
  3. the precise `/phases` files listed above
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for policy versioning, activation rules, compare behavior, baseline seeding, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that Phase 7 explicit policies start a new lineage and never rewrite historical Phase 5 baseline-snapshot runs.

## Objective
Build the policy model, versioning scheme, activation workflow, and project-assignment rules.

This prompt owns:
- the canonical policy schema and projection model
- project-scoped policy routes and typed APIs
- draft/active/retired lifecycle
- policy validation workflow
- activation and retirement gates
- baseline-snapshot seeded lineage origin
- compare views between revisions and against the seeded baseline snapshot
- policy history events and immutable snapshot keys
- minimal policy list/detail/compare surfaces

This prompt does not own:
- the polished policy editor UX
- pseudonym registry implementation
- generalisation transforms
- policy rerun orchestration
- a second policy system outside the canonical routes and tables

## Phase alignment you must preserve
From Phase 7 Iteration 7.0:

### Required tables
Implement or reconcile:
- `redaction_policies`
- `project_policy_projections`
- `policy_events`

`redaction_policies` fields to preserve:
- `id`
- `project_id`
- `policy_family_id`
- `name`
- `version`
- `seeded_from_baseline_snapshot_id`
- `supersedes_policy_id`
- `superseded_by_policy_id`
- `rules_json`
- `version_etag`
- `status` (`DRAFT | ACTIVE | RETIRED`)
- `created_by`
- `created_at`
- `activated_by`
- `activated_at`
- `retired_by`
- `retired_at`
- `validation_status` (`NOT_VALIDATED | VALID | INVALID`)
- `validated_rules_sha256`
- `last_validated_by`
- `last_validated_at`

`project_policy_projections`:
- `project_id`
- `active_policy_id`
- `active_policy_family_id`
- `updated_at`

`policy_events`:
- `event_type` (`POLICY_CREATED | POLICY_EDITED | POLICY_VALIDATED_VALID | POLICY_VALIDATED_INVALID | POLICY_ACTIVATED | POLICY_RETIRED`)
- `rules_sha256`
- `rules_snapshot_key`
- actor / reason / timestamps

### Core rules
- one active policy lineage per project in v1
- the first explicit lineage may be seeded from the attached Phase 0 `baseline_policy_snapshot_id`
- new draft revisions share the same `policy_family_id` and point `supersedes_policy_id` at the prior revision
- activating a new revision retires any previous `ACTIVE` revision and updates `project_policy_projections`
- historical Phase 5 runs keep their pinned baseline snapshots and are never rewritten to point at later explicit policies
- editing a draft clears validation until re-validated
- activation is rejected unless:
  - target revision is still `DRAFT`
  - `validation_status = VALID`
  - `validated_rules_sha256` still matches the current `rules_json`

### Rules-json support
Policy rules must support:
- category actions
- confidence thresholds
- reviewer requirements
- escalation flags
- pseudonymisation mode and aliasing rules
- generalisation transforms by category and specificity ceiling
- reviewer explanation mode for local LLM-assisted risk summaries

### Required APIs
- `GET /projects/{projectId}/policies`
- `GET /projects/{projectId}/policies/active`
- `POST /projects/{projectId}/policies`
- `GET /projects/{projectId}/policies/{policyId}`
- `GET /projects/{projectId}/policies/{policyId}/events`
- `PATCH /projects/{projectId}/policies/{policyId}`
- `GET /projects/{projectId}/policies/{policyId}/compare?against={otherPolicyId}`
- `GET /projects/{projectId}/policies/{policyId}/compare?againstBaselineSnapshotId={baselineSnapshotId}`
- `POST /projects/{projectId}/policies/{policyId}/validate`
- `POST /projects/{projectId}/policies/{policyId}/activate`
- `POST /projects/{projectId}/policies/{policyId}/retire`

### RBAC
- list, detail, compare readable by `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, and read-only `AUDITOR`
- create/edit/validate/activate/retire restricted to `PROJECT_LEAD` and `ADMIN`
- `RESEARCHER` has no Phase 7 policy-authoring access

### Web routes
- `/projects/:projectId/policies`
- `/projects/:projectId/policies/active`
- `/projects/:projectId/policies/:policyId`
- `/projects/:projectId/policies/:policyId/compare?against={otherPolicyId}`
- `/projects/:projectId/policies/:policyId/compare?againstBaselineSnapshotId={baselineSnapshotId}`

## Implementation scope

### 1. Canonical policy schema and projections
Implement or refine the canonical Phase 7 policy schema.

Requirements:
- one authoritative policy store
- one active-policy projection per project
- append-only event history
- no hidden environment-only policy state
- no second policy family model for v1

### 2. Draft lifecycle and optimistic concurrency
Implement the draft-edit path.

Requirements:
- `PATCH` only against `DRAFT` revisions
- stale `version_etag` values are rejected safely
- editing clears validation status until revalidated
- `ACTIVE` and `RETIRED` revisions are immutable

### 3. Validation and activation workflow
Implement the validation and activation path.

Requirements:
- validation persists `validation_status`, `validated_rules_sha256`, and actor/timestamp
- activation is blocked unless validation still matches the exact current rules
- activating a revision retires prior active revision in the same project
- activation updates `project_policy_projections`
- historical runs are not rewritten

### 4. Compare behavior
Implement the compare surfaces.

Requirements:
- exactly one comparison target allowed:
  - another policy revision
  - or the seeded baseline snapshot
- cross-project or cross-family comparisons are rejected
- baseline compare only allowed when the target lineage was seeded from that exact baseline snapshot
- compare output is typed and stable
- no parallel compare contract

### 5. Web list/detail/active/compare surfaces
Implement minimal but coherent policy surfaces.

Requirements:
- list of revisions
- active policy view
- policy detail
- compare view
- version diff and activation summary
- policy history timeline backed by append-only `policy_events`
- calm empty/loading/error/not-ready states

### 6. Audit and tests
Use the canonical audit path and add coverage.

At minimum cover:
- malformed rules rejected
- editing a draft invalidates prior validation
- only one active policy per project
- stale draft edits rejected without current `version_etag`
- history timeline reconstructs create/edit/validate/activate/retire from append-only events
- compare requests reject ambiguous inputs
- RBAC is enforced correctly

### 7. Documentation
Document:
- policy lineage and projection model
- seeded baseline origin behavior
- activation and validation gates
- compare rules
- what Prompt 73–76 deepen next

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- policy schema and projections
- validation and activation workflow
- compare APIs
- append-only event history
- tests

### Web
- policy list/detail/active/compare surfaces
- history timeline
- activation summary

### Docs
- policy model and activation workflow doc
- policy compare and baseline-seeding doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small list/detail/compare/history refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- polished policy editor UX
- pseudonym registries
- generalisation transforms
- policy rerun workflows
- a second policy system

## Testing and validation
Before finishing:
1. Verify one active policy lineage per project.
2. Verify draft edits require current `version_etag` and invalidate prior validation.
3. Verify activation is blocked unless validation matches current rules exactly.
4. Verify historical Phase 5 runs remain pinned to baseline snapshots and are not rewritten.
5. Verify compare routes accept exactly one target and reject ambiguous input.
6. Verify policy history is reconstructable from append-only events.
7. Verify RBAC boundaries for read vs mutate actions.
8. Verify docs match the implemented policy model and activation behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the explicit Phase 7 policy model is real
- policy versioning and activation are real
- baseline-seeded lineage is real
- compare behavior is real and safe
- policy history is append-only and auditable
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

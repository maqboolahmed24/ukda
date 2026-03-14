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
3. Then review the current repository generally — derivative index scaffolding, policy transforms, candidate snapshot scaffolding, suppression logic, anti-join checks, shared UI/data-layer primitives, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second derivative index path, a second suppression schema, or conflicting candidate-freeze semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for safeguarded derivative semantics, suppression policy checks, anti-join disclosure gates, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that safeguarded derivatives remain internal until they are explicitly frozen as immutable Phase 8 candidate snapshots; no derivative endpoint becomes an external release path.

## Objective
Implement safeguarded derivative indexes with suppressed-field contracts and disclosure gates.

This prompt owns:
- safeguarded derivative index generation
- `derivative_snapshots` and `derivative_index_rows`
- policy-aware field suppression
- anti-join disclosure checks
- derivative preview reads and historical snapshot scope
- candidate-freeze flow from derivative snapshot to immutable Phase 8 candidate snapshot
- activation gates for derivative index generations
- derivative routes and UI for safe internal preview

This prompt does not own:
- export request creation from derivative candidates
- search UI
- broad data-product analytics
- public derivative delivery
- a second derivative framework

## Phase alignment you must preserve
From Phase 10 Iteration 10.3:

### Required tables
Implement or reconcile:
- `derivative_snapshots`
  - `id`
  - `project_id`
  - `derivative_index_id`
  - `derivative_kind`
  - `source_snapshot_json`
  - `policy_version_ref`
  - `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
  - `supersedes_derivative_snapshot_id`
  - `superseded_by_derivative_snapshot_id`
  - `storage_key`
  - `snapshot_sha256`
  - `candidate_snapshot_id`
  - timestamps and failure reason
- `derivative_index_rows`
  - `id`
  - `derivative_index_id`
  - `derivative_snapshot_id`
  - `derivative_kind`
  - `source_snapshot_json`
  - `display_payload_json`
  - `suppressed_fields_json`
  - `created_at`

### Required APIs
- `GET /projects/{projectId}/derivatives?scope={scope}`
  - `scope=active` by default
  - `scope=historical` may include unsuperseded successful snapshots from prior derivative-index generations
- `GET /projects/{projectId}/derivatives/{derivativeId}`
- `GET /projects/{projectId}/derivatives/{derivativeId}/status`
- `GET /projects/{projectId}/derivatives/{derivativeId}/preview`
- `POST /projects/{projectId}/derivatives/{derivativeId}/candidate-snapshots`
- `POST /projects/{projectId}/derivative-indexes/{indexId}/activate`

### Core rules
- previews are served only from rows attached to the requested `derivative_snapshot_id` under that snapshot’s own `derivative_index_id`
- policy-aware field suppression is mandatory
- anti-join checks block reconstructable outputs
- repeated candidate-freeze requests for the same unsuperseded snapshot return the existing `candidate_snapshot_id`
- queued, running, failed, or incomplete derivative snapshots cannot be frozen
- unsuperseded successful historical snapshots remain previewable and freezable even after a newer derivative index becomes active
- any derivative intended for release becomes a Phase 8 candidate snapshot and re-enters full export approval; derivative endpoints themselves do not release data

### Activation rule
- `POST /projects/{projectId}/derivative-indexes/{indexId}/activate` is rejected unless the candidate generation passes:
  - suppression-policy checks
  - anti-join disclosure checks
  - snapshot completeness gates

### RBAC
- derivative preview readable by `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, and `ADMIN` when caller already has access to the underlying safeguarded derivative
- candidate-freeze restricted to `PROJECT_LEAD`, `REVIEWER`, or `ADMIN`

### Web routes
- `/projects/:projectId/derivatives`
- `/projects/:projectId/derivatives/:derivativeId`
- `/projects/:projectId/derivatives/:derivativeId/status`
- `/projects/:projectId/derivatives/:derivativeId/preview`

## Implementation scope

### 1. Canonical derivative generation
Implement or refine safeguarded derivative generation.

Requirements:
- derivative snapshots are versioned and append-only
- derivative rows are tied to one `derivative_snapshot_id` and one `derivative_index_id`
- no ad hoc preview rows outside the canonical generation
- generation is deterministic enough for rebuild comparison and hashing

### 2. Suppression and anti-join gates
Implement the Phase 10 safety checks.

Requirements:
- suppressed fields are explicit in `suppressed_fields_json`
- no raw identifier fields remain in preview payloads
- anti-join checks block reconstructable outputs
- blocked snapshots remain truthful and cannot be activated or frozen
- no second suppression policy engine

### 3. Preview and historical snapshot behavior
Implement or refine derivative preview routes.

Requirements:
- `scope=active` and `scope=historical` behave exactly as documented
- historical unsuperseded successful snapshots remain previewable
- preview rows do not mix generations
- no public or raw storage URLs
- no implied exportability from preview routes

### 4. Candidate-freeze path
Implement the bridge from safeguarded derivative to immutable Phase 8 candidate snapshot.

Requirements:
- candidate freeze is idempotent for the same unsuperseded successful snapshot
- freeze rejected for incomplete, failed, or superseded snapshots
- frozen candidate lineage points at the exact derivative snapshot and policy context
- no direct release path is created

### 5. Derivative index activation
Refine or implement activation gates.

Requirements:
- only `SUCCEEDED` derivative index generations can activate
- suppression, anti-join, and completeness gates must pass
- failed generations do not replace the active derivative index pointer
- rollback remains explicit re-activation of an older successful index generation

### 6. Web derivative surfaces
Implement or refine the derivative list/detail/status/preview UI.

Requirements:
- calm internal preview surfaces
- clear suppressed-field presentation
- clear candidate-freeze affordance for allowed roles
- no false implication of public release
- empty/loading/error/no-active-index states remain honest

### 7. Audit and regression
Use the canonical audit path and add coverage.

At minimum cover:
- no raw identifier field leaks in safeguarded derivative outputs
- anti-join checks block reconstructable combinations
- candidate freeze is idempotent
- superseded snapshots cannot be frozen
- preview rows remain scoped to one snapshot and one index generation
- candidate freeze emits `DERIVATIVE_CANDIDATE_SNAPSHOT_CREATED`
- derivative index activation emits `DERIVATIVE_INDEX_ACTIVATED`

### 8. Documentation
Document:
- safeguarded derivative model and lifecycle
- suppression and anti-join gate semantics
- preview and historical-snapshot rules
- candidate-freeze semantics and Phase 8 handoff
- what Prompt 93 will harden later around recall-first search activation and freshness

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / workers / contracts
- derivative snapshot generation
- suppression and anti-join checks
- preview APIs
- candidate-freeze path
- activation gates
- tests

### Web
- derivative list/detail/status/preview routes
- candidate-freeze UI for allowed roles
- suppressed-field and safety presentation

### Docs
- safeguarded derivative index and candidate-freeze doc
- suppression and anti-join gate doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small derivative preview/detail refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- export request creation from derivatives
- search UI
- public derivative delivery
- a second derivative framework
- broad analytics or reporting dashboards

## Testing and validation
Before finishing:
1. Verify safeguarded derivative outputs suppress raw identifier fields.
2. Verify anti-join checks block reconstructable outputs.
3. Verify preview rows remain scoped to the requested snapshot and index generation.
4. Verify historical unsuperseded successful snapshots remain previewable.
5. Verify candidate freeze is idempotent and rejected for invalid snapshot states.
6. Verify activation is blocked unless suppression, anti-join, and completeness gates pass.
7. Verify successful derivative index activation emits `DERIVATIVE_INDEX_ACTIVATED`.
8. Verify docs match the implemented derivative and candidate-freeze behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- safeguarded derivative indexes are real
- suppression and anti-join gates are real
- preview and historical snapshot behavior are real
- candidate-freeze into immutable Phase 8 lineage is real
- no derivative route becomes a release bypass
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

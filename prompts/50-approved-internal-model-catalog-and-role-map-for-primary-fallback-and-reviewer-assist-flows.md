You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed phase files before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first on each run.

## Mandatory first actions
1. Inspect the full repository tree.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-04-handwriting-transcription-v1.md`
3. Then review the current repository generally — model/runtime config, current `MODEL_STACK.md` or equivalent, API/admin/project routes, approved model or assignment tables if present, training dataset hooks if any, audit code, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second model registry, a second role-map system, or conflicting assignment semantics.

## Source-of-truth hierarchy
Use this precedence order when implementing:
1. The specific `/phases` files listed in this prompt for product behavior and acceptance logic.
2. `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md` when this prompt depends on web-first execution semantics.
3. `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` when this prompt depends on recall-first, rescue, token-anchor, search-anchoring, or conservative-masking semantics.
4. `/phases/blueprint-ukdataextraction.md`, `/phases/README.md`, `/phases/ui-premium-dark-blueprint-obsidian-folio.md`, and `/phases/phase-00-foundation-release.md` as supporting product context when they are listed or clearly relevant.
5. This prompt for task scope and deliverables.
6. Current repository state for reconciling implementation details.
7. Official external docs for implementation mechanics only.

Treat current repository state as implementation context, not as the primary source of product truth.

## Conflict-resolution rule
- `/phases` wins for approved model catalog semantics, stable model roles, assignment rules, starter defaults, RBAC, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that project workflows consume stable roles, not ad hoc free-text model picks. Role-map changes switch approved deployments behind a stable contract and do not rewrite workflow routes.

## Objective
Build the approved internal model catalog and role map for primary, fallback, and reviewer-assist flows.

This prompt owns:
- the canonical approved-model catalog
- stable transcription role map
- project-scoped model assignment flows
- model-assignment routes and APIs
- checksum and runtime-profile integrity checks
- minimal training-dataset lineage foundations from Phase 4.4
- audit and RBAC for model assignment operations
- docs that explain how stable roles map to approved internal deployments

This prompt does not own:
- primary transcription inference rollout
- fallback comparison execution
- active reviewer correction workspace
- broad governance tooling outside the transcription-facing roles
- arbitrary project-local model uploads
- public or external model services

## Phase alignment you must preserve
From Phase 4.0, Phase 4.4, and the approved starter defaults:

### Approved starter defaults
- primary transcription VLM: `Qwen2.5-VL-3B-Instruct`
- constrained assist LLM for reviewer-facing help: `Qwen3-4B`
- fallback HTR baseline: `Kraken`

Optional comparison models may be evaluated later, but they do not replace the stable role contract or run schema.

### Required approved model catalog
Implement or reconcile `approved_models`:
- `id`
- `model_type` (`VLM | LLM | HTR`)
- `model_role` (`TRANSCRIPTION_PRIMARY | TRANSCRIPTION_FALLBACK | ASSIST`)
- `model_family`
- `model_version`
- `serving_interface` (`OPENAI_CHAT | OPENAI_EMBEDDING | ENGINE_NATIVE | RULES_NATIVE`)
- `engine_family`
- `deployment_unit`
- `artifact_subpath`
- `checksum_sha256`
- `runtime_profile`
- `response_contract_version`
- `metadata_json`
- `status` (`APPROVED | DEPRECATED | ROLLED_BACK`)
- `approved_by`
- `approved_at`
- `created_at`
- `updated_at`

This is platform-level, not project-scoped.

### Required project assignment model
Implement or reconcile `project_model_assignments`:
- `id`
- `project_id`
- `model_role` (`TRANSCRIPTION_PRIMARY | TRANSCRIPTION_FALLBACK | ASSIST`)
- `approved_model_id`
- `status` (`DRAFT | ACTIVE | RETIRED`)
- `assignment_reason`
- `created_by`
- `created_at`
- `activated_by`
- `activated_at`
- `retired_by`
- `retired_at`

Rules:
- project assignments may reference only rows from `approved_models`
- stable role-map updates must not change workflow routes or run-table semantics
- they only switch the approved deployment behind the stable role contract

### Minimal training-loop foundations
Implement or reconcile `training_datasets`:
- `id`
- `project_id`
- `source_approved_model_id` (nullable)
- `project_model_assignment_id` (nullable)
- `dataset_kind` (`TRANSCRIPTION_TRAINING`)
- `page_count`
- `storage_key`
- `dataset_sha256`
- `created_by`
- `created_at`

### Required platform-scoped routes
- `/approved-models`

### Required project-scoped routes
- `/projects/:projectId/model-assignments`
- `/projects/:projectId/model-assignments/:assignmentId`
- `/projects/:projectId/model-assignments/:assignmentId/datasets`

### Required APIs
- `GET /approved-models`
- `POST /approved-models`
- `GET /projects/{projectId}/model-assignments`
- `POST /projects/{projectId}/model-assignments`
- `GET /projects/{projectId}/model-assignments/{assignmentId}`
- `GET /projects/{projectId}/model-assignments/{assignmentId}/datasets`
- `POST /projects/{projectId}/model-assignments/{assignmentId}/activate`
- `POST /projects/{projectId}/model-assignments/{assignmentId}/retire`

### Required RBAC
- `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can read approved-model catalog and assignment list/detail surfaces
- only `PROJECT_LEAD` and `ADMIN` can add approved models and add/activate/retire assignments

### Required audit events
Emit or reconcile:
- `APPROVED_MODEL_LIST_VIEWED`
- `APPROVED_MODEL_CREATED`
- `PROJECT_MODEL_ASSIGNMENT_CREATED`
- `MODEL_ASSIGNMENT_LIST_VIEWED`
- `MODEL_ASSIGNMENT_DETAIL_VIEWED`
- `TRAINING_DATASET_VIEWED`
- `PROJECT_MODEL_ACTIVATED`
- `PROJECT_MODEL_RETIRED`

## Implementation scope

### 1. Canonical approved model catalog
Implement or refine one canonical platform-approved model catalog.

Requirements:
- one authoritative `approved_models` table or equivalent canonical backing model
- stable role values:
  - `TRANSCRIPTION_PRIMARY`
  - `TRANSCRIPTION_FALLBACK`
  - `ASSIST`
- starter defaults are seeded consistently
- internal checksum and runtime-profile metadata are persisted
- no ad hoc model list hidden in route code or environment variables only

If the repo already has a `MODEL_STACK.md` or similar, reconcile it with the catalog rather than leaving parallel sources of truth.

### 2. Stable role-map contract
Implement the stable role-map behavior.

Requirements:
- projects consume stable roles, not arbitrary raw model identifiers
- changing an assignment swaps the approved deployment behind the role
- route semantics and run-table semantics stay stable
- transcription flows can ask for `TRANSCRIPTION_PRIMARY`, `TRANSCRIPTION_FALLBACK`, or `ASSIST` without hardcoding one specific deployment path in UI logic
- no project-local free-text role inventing

### 3. Project model assignments
Implement or refine project-scoped assignment flows.

Requirements:
- projects can assign approved models to stable roles
- only approved models with compatible roles can be assigned
- one role can have only its intended active assignment semantics
- draft/active/retired state transitions are explicit
- activation and retirement are auditable
- historical assignment rows remain accurate and queryable

### 4. Minimal models screen and routes
Implement or refine the project-scoped model assignment routes.

Requirements:
- list approved models by role and current project assignment
- show current status
- show run usage links where useful
- explicit activate and retire actions for eligible assignments
- dataset lineage links for approved training subsets
- calm, dense, serious UI
- no flashy “model marketplace” feel

### 5. Dataset lineage foundations
Implement the minimum viable training-dataset lineage support from Phase 4.4.

Requirements:
- `training_datasets` table or canonical equivalent
- assignment detail route can show dataset lineage if present
- no full training pipeline required in this prompt
- dataset storage metadata and checksum are typed and auditable
- groundwork is ready for later training-loop work without forcing UI or schema changes now

### 6. Integrity and compatibility checks
Harden the catalog and assignment rules.

Requirements:
- registry integrity checksums match stored model artefacts
- approved models can only be assigned into compatible transcription roles
- assignment activation/retirement paths are explicit and validated
- run records can later reference model checksum and container digest consistently
- no assignment may point to a deprecated or rolled-back model as active unless the repo explicitly supports that workflow safely

### 7. API and typed contract integration
Expose typed contracts through the canonical data layer.

Requirements:
- assignment list/detail/dataset APIs are typed
- UI consumes the canonical data layer, not route-local fetch wrappers
- no project page needs to reverse-engineer compatibility rules client-side
- empty, loading, and no-assignment states remain calm and exact

### 8. Audit and RBAC
Use the canonical audit path and enforce role boundaries.

Requirements:
- read access:
  - `PROJECT_LEAD`
  - `REVIEWER`
  - `ADMIN`
- mutate access:
  - `PROJECT_LEAD`
  - `ADMIN`
- audit events emitted through the canonical path
- no second governance or audit subsystem

### 9. Documentation
Document:
- approved model catalog ownership
- stable role-map rules
- starter defaults
- project assignment lifecycle
- dataset-lineage foundations
- how later work will consume the stable role contract for primary, fallback, and assist flows

## Required deliverables
### Backend / contracts
- approved model catalog
- project model assignments
- training dataset lineage foundation
- typed APIs
- integrity and compatibility checks
- tests

### Web
- `/projects/:projectId/model-assignments`
- `/projects/:projectId/model-assignments/:assignmentId`
- `/projects/:projectId/model-assignments/:assignmentId/datasets`
- minimal model-assignment UI with role-aware actions

### Docs
- approved-model catalog and role-map doc
- project model-assignment lifecycle doc
- any README updates required for developer usage


## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small assignment-list/detail/dataset-view refinements are needed
- root config/task files
- `README.md`
- `docs/**`
- existing model/runtime config docs or helper files only to reconcile them with the canonical catalog

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- inference rollout
- fallback comparison execution
- manual correction workspace
- arbitrary project-local model uploads
- public or external model calls
- a second model registry or role-map system

## Testing and validation
Before finishing:
1. Verify starter default models are seeded consistently into the approved catalog.
2. Verify approved-model checksum and runtime-profile integrity checks work.
3. Verify incompatible role assignments are rejected.
4. Verify approved-model catalog reads work for `PROJECT_LEAD`, `REVIEWER`, and `ADMIN`.
5. Verify catalog add actions are limited to `PROJECT_LEAD` and `ADMIN`.
6. Verify assignment-list and assignment-detail reads work for `PROJECT_LEAD`, `REVIEWER`, and `ADMIN`.
7. Verify assignment add/activate/retire actions are limited to `PROJECT_LEAD` and `ADMIN`.
8. Verify role-map updates do not alter route or run-table semantics.
9. Verify dataset-lineage surfaces are typed and consistent.
10. Verify audit events are emitted through the canonical path.
11. Verify docs match the actual catalog, role-map, and assignment behavior.
12. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the approved internal model catalog supports typed list/create flows, and project model assignments support add/activate/retire flows with audit events
- role-map updates change model resolution for the mapped role without changing workflow routes, and emit audit events
- project model assignments are persisted with typed role keys, uniqueness constraints, and role-based assignment lifecycle permissions
- RBAC and audit tests cover catalog read/add actions, assignment activate/retire actions, and project role-assignment changes
- model invocation records include typed dataset lineage reference fields (nullable where not yet populated) with documented semantics
- stable role keys and assignment fields are documented in typed contracts and validated by contract tests
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

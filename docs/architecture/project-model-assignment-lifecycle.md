# Project Model Assignment Lifecycle

## Scope

`project_model_assignments` binds project-scoped role keys to platform-approved model rows.

This keeps workflow contracts stable while allowing controlled deployment swaps.

## Data Contract

`project_model_assignments` fields:

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

Constraints:

- `approved_model_id` must reference an existing `approved_models` row
- assignment role must match the referenced approved model role
- assignment create/activate requires referenced model status `APPROVED`
- at most one `ACTIVE` row per `(project_id, model_role)` via partial unique index

## Lifecycle States

### DRAFT

- Created via `POST /projects/{projectId}/model-assignments`
- Not used for run launches

### ACTIVE

- Activated via `POST /projects/{projectId}/model-assignments/{assignmentId}/activate`
- Any existing `ACTIVE` row in the same role scope is retired automatically
- Activation writes `activated_by` and `activated_at`
- Eligible for run launch binding

### RETIRED

- Set via activation supersession of another row, or explicit
  `POST /projects/{projectId}/model-assignments/{assignmentId}/retire`
- Writes `retired_by` and `retired_at`
- Cannot be reactivated if the row is already retired

## Run Binding

Transcription runs persist both:

- `model_id` (resolved approved model)
- `project_model_assignment_id` (nullable when no project assignment was used)

This supports role-map lineage and model artifact lineage without mutating historical run rows.

## Dataset Lineage Foundation

`training_datasets` rows provide minimal Phase 4.4 lineage hooks:

- optional `source_approved_model_id`
- optional `project_model_assignment_id`
- `dataset_kind = TRANSCRIPTION_TRAINING`
- `page_count`
- `storage_key`
- `dataset_sha256`
- actor/timestamps

Surface:

- `GET /projects/{projectId}/model-assignments/{assignmentId}/datasets`

## UI Route Family

- `/projects/:projectId/model-assignments`
- `/projects/:projectId/model-assignments/:assignmentId`
- `/projects/:projectId/model-assignments/:assignmentId/datasets`

The route family is intentionally dense and governance-focused, not a general model marketplace.

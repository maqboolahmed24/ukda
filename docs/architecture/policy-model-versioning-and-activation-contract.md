# Policy Model Versioning And Activation Contract

## Scope

Phase 7 Prompt 72 defines one canonical explicit policy model for project-scoped privacy control.

This contract covers:

- `redaction_policies` schema and lifecycle fields
- `project_policy_projections` as the only active-policy projection surface
- `policy_events` as append-only policy history
- draft/edit/validate/activate/retire gates

## Canonical Tables

### `redaction_policies`

Required fields:

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
- `created_by`, `created_at`
- `activated_by`, `activated_at`
- `retired_by`, `retired_at`
- `validation_status` (`NOT_VALIDATED | VALID | INVALID`)
- `validated_rules_sha256`
- `last_validated_by`, `last_validated_at`

Constraints and behavior:

- Phase 7 v1 allows one policy lineage (`policy_family_id`) per project.
- New revisions are inserted as new rows. Existing rows are never overwritten in place.
- `PATCH` is draft-only and requires current `version_etag`.
- Editing a draft clears validation state and hash.
- `ACTIVE` and `RETIRED` rows are immutable.

### `project_policy_projections`

Fields:

- `project_id`
- `active_policy_id`
- `active_policy_family_id`
- `updated_at`

Rules:

- `GET /projects/{projectId}/policies/active` resolves from this projection row.
- Activation updates projection to the newly active revision.
- Retire clears active projection fields.

### `policy_events`

Fields:

- `id`
- `policy_id`
- `event_type`
- `actor_user_id`
- `reason`
- `rules_sha256`
- `rules_snapshot_key`
- `created_at`

Event types:

- `POLICY_CREATED`
- `POLICY_EDITED`
- `POLICY_VALIDATED_VALID`
- `POLICY_VALIDATED_INVALID`
- `POLICY_ACTIVATED`
- `POLICY_RETIRED`

History views must read `policy_events` directly instead of inferring chronology from mutable status columns.

## Lifecycle Gates

### Validate

`POST /projects/{projectId}/policies/{policyId}/validate`

- evaluates current draft rule payload
- writes validation status and validation hash
- records append-only validation event with rule snapshot hash

### Activate

`POST /projects/{projectId}/policies/{policyId}/activate`

Allowed only when all are true:

- target revision is `DRAFT`
- `validation_status == VALID`
- `validated_rules_sha256` still matches current draft `rules_json`

On activation:

- any existing active policy in the project is retired
- projection row points to new active revision
- append-only activation event is written

### Retire

`POST /projects/{projectId}/policies/{policyId}/retire`

Allowed only when all are true:

- target revision is `ACTIVE`
- target revision equals `project_policy_projections.active_policy_id`

On retirement:

- policy status becomes `RETIRED`
- projection row is cleared
- append-only retire event is written

## Baseline-Pin Invariant

Historical Phase 5 run records are not rewritten by Phase 7 activation.

Prompt 72 introduces explicit policy lineage but does not rebind historical baseline-snapshot pointers from earlier runs.

## RBAC

Read:

- `PROJECT_LEAD`
- `REVIEWER`
- `ADMIN`
- read-only `AUDITOR`

Mutate (create/edit/validate/activate/retire):

- `PROJECT_LEAD`
- `ADMIN`

No Phase 7 policy authoring for `RESEARCHER`.

## Follow-on Work

Prompt 73 to Prompt 76 extend this baseline:

- Prompt 73: pseudonym registry lineage and deterministic aliasing
- Prompt 74: indirect-identifier generalisation transforms
- Prompt 75: expert policy editor UX
- Prompt 76: policy reruns, rollback, and regression orchestration
- Prompt 77: policy lineage, usage lineage, immutable snapshots, and bounded explainability read surfaces

Prompt 76 adds canonical rollback draft creation:

- `POST /projects/{projectId}/policies/{policyId}/rollback-draft?fromPolicyId={fromPolicyId}`
- rollback creates a new `DRAFT` revision in lineage context and never mutates historical rows in place

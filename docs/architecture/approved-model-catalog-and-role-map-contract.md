# Approved Model Catalog And Role-Map Contract

## Purpose

Phase 4 Prompt 50 establishes one canonical internal model catalog and a stable role-map contract for transcription flows.

The catalog is platform-scoped and role-driven:

- workflows target stable role keys (`TRANSCRIPTION_PRIMARY`, `TRANSCRIPTION_FALLBACK`, `ASSIST`)
- approved deployments can be swapped behind those role keys without changing route families
- run records keep both resolved `model_id` and optional `project_model_assignment_id` for lineage

## Canonical Catalog

`approved_models` is the only authoritative source for transcription-facing approved deployments.

Persisted fields:

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

## Starter Defaults

Seeded approved models:

- `TRANSCRIPTION_PRIMARY`: `Qwen2.5-VL-3B-Instruct`
- `ASSIST`: `Qwen3-4B`
- `TRANSCRIPTION_FALLBACK`: `Kraken`

## Integrity And Compatibility

Catalog and assignment writes enforce:

- checksum format validation (`checksum_sha256` must be 64-char hex)
- artifact subpath boundary checks (no parent path traversal)
- role compatibility (`model_role` must match target role contract)
- assignment activation only for `APPROVED` models
- no activation of retired assignments

## Transcription Resolution Rules

`create_transcription_run` resolves model binding in this order:

1. explicit `project_model_assignment_id` (must be `ACTIVE`, role-compatible, and point to an `APPROVED` model)
2. explicit `model_id` (must resolve to an `APPROVED` model with compatible role)
3. active assignment for `(project_id, expected_role)` when present
4. latest approved model for expected role

Expected role comes from engine family:

- fallback engines (`KRAKEN_LINE`, `TROCR_LINE`, `DAN_PAGE`) require `TRANSCRIPTION_FALLBACK`
- other transcription engines require `TRANSCRIPTION_PRIMARY`

## APIs

Platform scope:

- `GET /approved-models`
- `POST /approved-models`

Project scope:

- `GET /projects/{projectId}/model-assignments`
- `POST /projects/{projectId}/model-assignments`
- `GET /projects/{projectId}/model-assignments/{assignmentId}`
- `GET /projects/{projectId}/model-assignments/{assignmentId}/datasets`
- `POST /projects/{projectId}/model-assignments/{assignmentId}/activate`
- `POST /projects/{projectId}/model-assignments/{assignmentId}/retire`

## RBAC And Audit

Read surfaces:

- `PROJECT_LEAD`, `REVIEWER`, `ADMIN`

Mutation surfaces:

- `PROJECT_LEAD`, `ADMIN`

Prompt 50 audit events:

- `APPROVED_MODEL_LIST_VIEWED`
- `APPROVED_MODEL_CREATED`
- `PROJECT_MODEL_ASSIGNMENT_CREATED`
- `MODEL_ASSIGNMENT_LIST_VIEWED`
- `MODEL_ASSIGNMENT_DETAIL_VIEWED`
- `TRAINING_DATASET_VIEWED`
- `PROJECT_MODEL_ACTIVATED`
- `PROJECT_MODEL_RETIRED`

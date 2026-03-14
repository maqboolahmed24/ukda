# Preprocessing Run And Projection Model

> Status: Active Prompt 37
> Scope: Canonical profile registry, immutable run/page lineage, explicit activation semantics, and downstream basis-state invalidation visibility

This document defines the persisted preprocessing model used by Phase 2 and the explicit handoff contract consumed by Phase 3 layout analysis.

## Canonical Tables

## `preprocess_profile_registry`

Canonical persisted profile registry seeded from one source definition in `/api/app/documents/preprocessing.py`.

- `profile_id`
- `profile_version`
- `profile_revision`
- `label`
- `description`
- `params_json` (expanded canonical params)
- `params_hash`
- `is_advanced`
- `is_gated`
- `supersedes_profile_id` (nullable)
- `supersedes_profile_revision` (nullable)
- `created_at`

Registry rows are append-only by `(profile_id, profile_revision)` identity.

## `preprocess_runs`

Document-scoped append-only preprocessing attempts.

- `id` (PK)
- `project_id`
- `document_id`
- `parent_run_id` (nullable)
- `attempt_number`
- `run_scope` (`FULL_DOCUMENT | PAGE_SUBSET | COMPOSED_FULL_DOCUMENT`)
- `target_page_ids_json` (nullable)
- `composed_from_run_ids_json` (nullable)
- `superseded_by_run_id` (nullable forward lineage link)
- `profile_id`
- `profile_version`
- `profile_revision`
- `profile_label`
- `profile_description`
- `profile_params_hash`
- `profile_is_advanced`
- `profile_is_gated`
- `params_json`
- `params_hash`
- `pipeline_version`
- `container_digest`
- `manifest_object_key` (nullable until persisted)
- `manifest_sha256` (nullable until persisted)
- `manifest_schema_version`
- `status`
- `created_by`
- `created_at`
- `started_at` (nullable)
- `finished_at` (nullable)
- `failure_reason` (nullable)

## `page_preprocess_results`

Per-page immutable lineage record scoped to one run.

- `run_id`
- `page_id`
- `page_index`
- `status`
- `quality_gate_status`
- `input_object_key` (nullable)
- `input_sha256` (nullable)
- `source_result_run_id` (nullable for legacy rows; run lineage source for output bytes)
- `output_object_key_gray` (nullable)
- `output_object_key_bin` (nullable)
- `metrics_object_key` (nullable)
- `metrics_sha256` (nullable)
- `metrics_json`
- `sha256_gray` (nullable)
- `sha256_bin` (nullable)
- `warnings_json`
- `failure_reason` (nullable)
- `created_at`
- `updated_at`

Rows are keyed by `(run_id, page_id)` and are never overwritten by later runs.

## `document_preprocess_projections`

Document-level explicit active run pointer and alignment metadata.

- `document_id`
- `project_id`
- `active_preprocess_run_id` (nullable)
- `active_profile_id` (nullable)
- `active_profile_version` (nullable)
- `active_profile_revision` (nullable)
- `active_params_hash` (nullable)
- `active_pipeline_version` (nullable)
- `active_container_digest` (nullable)
- `updated_at`

## Manifest Rules

Manifest object path:

- `controlled/derived/{project_id}/{document_id}/preprocess/{run_id}/manifest.json`

Manifest persistence is immutable:

- object writes are idempotent and fail closed on content mismatch
- `preprocess_runs.manifest_object_key` and `manifest_sha256` are immutable once set
- reruns append a new run and new manifest; historical manifests are not rewritten

Selective rerun semantics:

- reruns with explicit `target_page_ids` persist `run_scope = PAGE_SUBSET`
- whole-document runs persist `run_scope = FULL_DOCUMENT`
- subset membership is queryable from `target_page_ids_json` and mirrored in expanded run params

## Active Projection Contract

Projection semantics are explicit:

- no implicit "latest successful" fallback for downstream defaults
- only `SUCCEEDED` runs can be activated
- activating a run updates projection metadata to match that run's profile and runtime hashes
- activating an already-active run is idempotent
- `active_profile_id` remains aligned with `active_preprocess_run_id`
- activation rewrites only `document_preprocess_projections`; it does not rewrite historical `preprocess_runs` lineage rows

Downstream handoff contract for Phase 3:

- default layout input selection is `document_preprocess_projections.active_preprocess_run_id`
- consumers must not infer defaults from run recency or status scans
- historical runs remain immutable and queryable after supersession

## Supersession Rules

- reruns append a new `preprocess_runs` row
- reruns preserve `parent_run_id`
- reruns increment `attempt_number`
- reruns set the superseded row `superseded_by_run_id` once, at rerun creation time
- activation does not create or mutate supersession links

## Downstream Basis-State Resolution

Preprocess APIs expose explicit basis state for downstream phases:

- `layoutBasisState` compares:
  - current `document_preprocess_projections.active_preprocess_run_id`
  - `document_layout_projections.active_input_preprocess_run_id`
- `transcriptionBasisState` compares:
  - current `document_preprocess_projections.active_preprocess_run_id`
  - `document_transcription_projections.active_preprocess_run_id`

State mapping:

- `NOT_STARTED`: no downstream projection exists yet (or no downstream basis run has been activated)
- `CURRENT`: downstream projection basis run matches the resolved preprocess run
- `STALE`: downstream projection basis run differs from the resolved preprocess run

This state is emitted in canonical preprocessing responses so web clients do not infer staleness from raw rows.

## RBAC And Audit Surface

Role boundaries:

- view runs/quality/overview: `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, `ADMIN`
- mutate runs (create/rerun/cancel/activate): `PROJECT_LEAD`, `REVIEWER`, `ADMIN`

Audit events used by metadata and lineage routes:

- `PREPROCESS_RUN_VIEWED`
- `PREPROCESS_ACTIVE_RUN_VIEWED`

## Deferred Work

This model intentionally does not include:

- compare-surface visual polish beyond triage delta contracts
- advanced profile families beyond baseline registry seeding
- layout segmentation execution (Phase 3 ownership)

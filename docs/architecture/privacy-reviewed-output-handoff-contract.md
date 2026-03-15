# Privacy Reviewed Output Handoff Contract

Status: Prompt 65
Scope: Phase 5 reviewed-output artefacts handed to Phase 6 governance and Phase 8 export-candidate registration

## Canonical Phase 5 source artefact

The only supported Phase 5 downstream source artefact is the immutable run-level reviewed output manifest represented by `redaction_run_outputs`:

- `run_id`
- `status`
- `output_manifest_sha256`
- `output_manifest_key` (internal storage reference only)
- `page_count`
- lifecycle timestamps and failure metadata

Downstream systems must reference this artefact as `source_artifact_kind = REDACTION_RUN_OUTPUT` and must not reconstruct candidates from mutable `redaction_outputs` rows.

## Immutable lineage inputs

Reviewed output generation is anchored to:

- `redaction_run_reviews.approved_snapshot_key`
- `redaction_run_reviews.approved_snapshot_sha256`
- `redaction_run_reviews.locked_at`

Per-page reviewed previews are regenerated from the approved snapshot decision set and written as immutable controlled artefacts keyed by `preview_sha256`.

Run-level manifest bytes are deterministic over:

- `(page_id, preview_sha256)` rows
- approved snapshot hash linkage
- approved snapshot decision metadata required by the screening-safe manifest serializer (policy lineage, reviewer sign-off lineage, and applied-entry fields)

## Readiness gate for downstream consumers

A run is downstream-ready only when all are true:

1. `redaction_run_reviews.review_status = APPROVED`
2. `redaction_run_outputs.status = READY`
3. output readiness projection is `OUTPUT_READY` (`downstreamReady = true`)

No downstream Phase 6/8 flow may use heuristic “latest run looks ready” logic.

## API read contract

Primary read surfaces:

- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/output`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/output/status`

Response contract includes:

- `runId`
- `status`
- `reviewStatus`
- `readinessState`
- `downstreamReady`
- `outputManifestSha256`
- `pageCount`
- lifecycle timestamps

The API does not expose raw object-store keys or public download URLs.

## Event history contract

Run-level output lifecycle is append-only in `redaction_run_output_events`:

- `RUN_OUTPUT_GENERATION_STARTED`
- `RUN_OUTPUT_GENERATION_SUCCEEDED`
- `RUN_OUTPUT_GENERATION_FAILED`
- `RUN_OUTPUT_GENERATION_CANCELED`

Run timelines merge these events after decision/page-review/run-review events using stable `(created_at, precedence, event_id)` ordering.

## RBAC contract for reviewed outputs

- Read: `PROJECT_LEAD`, `REVIEWER`, `ADMIN`
- Read-only: `AUDITOR` only for approved runs
- Denied: `RESEARCHER`
- Mutation/retrigger/cancel controls remain admin-only when introduced later

# Safeguarded Derivative Index And Candidate-Freeze Contract

## Scope

This contract defines Phase 10 safeguarded derivative behavior for:

- derivative index generations (`DERIVATIVE` in `search/entity/derivative` index lineage)
- immutable derivative snapshots (`derivative_snapshots`)
- snapshot-scoped preview rows (`derivative_index_rows`)
- suppression and anti-join disclosure gates
- idempotent candidate freeze handoff into Phase 8 export-candidate lineage

Derivative preview routes are internal review surfaces only. They are not a data-release path.

## Data Model

`derivative_snapshots` is append-only per project and derivative index generation.

Required safety fields are first-class:

- `storage_key`
- `snapshot_sha256`
- `candidate_snapshot_id`
- `supersedes_derivative_snapshot_id`
- `superseded_by_derivative_snapshot_id`

`derivative_index_rows` rows are scoped to one `derivative_snapshot_id` and one `derivative_index_id`.
Preview responses never mix rows across snapshot IDs or index generations.

## Safety Gates

### Suppression policy checks

- Raw identifier-like keys must not remain in `display_payload_json`.
- `suppressed_fields_json.fields` records explicit suppression decisions.
- Activation and candidate freeze both reject snapshots with identifier leaks or malformed suppression metadata.

### Anti-join disclosure checks

- Quasi-identifier fields come from snapshot source metadata (or deterministic fallback inference).
- Group cardinality below threshold fails disclosure checks.
- Failed anti-join checks block activation and candidate freeze.

### Snapshot completeness gates

Derivative index activation requires a complete candidate generation:

- every snapshot under the target derivative index is `SUCCEEDED`
- each snapshot has `storage_key` and `snapshot_sha256`
- each snapshot has at least one materialized preview row
- index-level completeness counters (`eligible*` / `covered*`) must satisfy coverage rules

## API And Route Semantics

Implemented project-scoped API routes:

- `GET /projects/{projectId}/derivatives?scope=active|historical`
- `GET /projects/{projectId}/derivatives/{derivativeId}`
- `GET /projects/{projectId}/derivatives/{derivativeId}/status`
- `GET /projects/{projectId}/derivatives/{derivativeId}/preview`
- `POST /projects/{projectId}/derivatives/{derivativeId}/candidate-snapshots`

Web surfaces:

- `/projects/:projectId/derivatives`
- `/projects/:projectId/derivatives/:derivativeId`
- `/projects/:projectId/derivatives/:derivativeId/status`
- `/projects/:projectId/derivatives/:derivativeId/preview`

`scope=active` resolves active derivative-index snapshots only.
`scope=historical` includes unsuperseded successful snapshots from prior generations (and active lineage where applicable).

## Candidate Freeze Handoff

`POST /projects/{projectId}/derivatives/{derivativeId}/candidate-snapshots`:

- allowed roles: `PROJECT_LEAD`, `REVIEWER`, `ADMIN`
- rejected for non-`SUCCEEDED`, superseded, incomplete, or unsafe snapshots
- idempotent for the same unsuperseded snapshot
- persists `candidate_snapshot_id` linkage on derivative snapshot
- emits a Phase 8 candidate (`SAFEGUARDED_DERIVATIVE`, source `DERIVATIVE_SNAPSHOT`) with immutable lineage to:
  - derivative snapshot ID
  - derivative index ID
  - policy version reference
  - snapshot hash / storage reference
  - suppressed-field declarations

Downstream export approval remains required; freeze only prepares governed candidate lineage.

## Activation And Audit

Derivative generation activation uses the existing index activation route:

- `POST /projects/{projectId}/derivative-indexes/{indexId}/activate`

Activation remains `ADMIN`-gated and additionally enforces derivative suppression, anti-join, and completeness gates.

Audit events include:

- `DERIVATIVE_LIST_VIEWED`
- `DERIVATIVE_DETAIL_VIEWED`
- `DERIVATIVE_STATUS_VIEWED`
- `DERIVATIVE_PREVIEW_VIEWED`
- `DERIVATIVE_CANDIDATE_SNAPSHOT_CREATED`
- `DERIVATIVE_INDEX_ACTIVATED`

## Prompt 93 Follow-On

Prompt 93 hardens search/index activation around recall-first freshness checks, rollback policy, and additional audit controls. It does not redefine derivative suppression or candidate-freeze semantics established here.

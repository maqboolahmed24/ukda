# Preprocessing Artefact Versioning And Lineage

This note defines immutable preprocessing artefact lineage for Phase 2.

## Profile Versioning Rules

- Profile definitions are persisted in `preprocess_profile_registry`.
- Identity is `profile_id + profile_revision`; `profile_version` is human-readable release notation.
- `params_json` and `params_hash` are canonicalized and immutable per revision.
- Advanced/risk-gated profiles are marked with `is_advanced` and `is_gated`.
- New profile behavior requires a new registry revision rather than in-place mutation.

## Run Versioning Rules

- Each preprocessing attempt creates a new `preprocess_runs` row.
- `attempt_number` is monotonic per document.
- Run rows carry both profile metadata snapshot and expanded run params.
- `params_hash` always reflects expanded run params (including explicit overrides).
- Supersession is append-only lineage:
  - rerun creation sets `superseded_by_run_id` on the superseded run exactly once
  - activation does not alter `superseded_by_run_id` links

## Per-Page Lineage Ownership

`page_preprocess_results` is the authoritative page lineage table for one run:

- source input key and source hash
- derived output object keys and hashes
- metrics object key/hash and normalized metrics payload
- warnings, quality gate, and failure state
- `source_result_run_id` for inherited or produced bytes lineage

Historical rows remain queryable and are not rewritten by reruns.

## Manifest Integrity Rules

- Each run persists a manifest under the canonical preprocess derived prefix.
- Manifest includes source-page references, profile metadata, run params hash, runtime versioning, and per-page artefact references.
- Manifest bytes are deterministically serialized.
- Manifest object writes are idempotent and fail if content would differ.
- Run-level manifest pointers (`manifest_object_key`, `manifest_sha256`) are immutable once recorded.

## Explicit Downstream Handoff

Phase 3 default preprocessing input is resolved only from:

- `document_preprocess_projections.active_preprocess_run_id`

No downstream consumer may substitute latest-successful or inferred run selection.

Basis-state invalidation is explicit:

- layout basis state resolves as `NOT_STARTED | CURRENT | STALE` from `document_layout_projections.active_input_preprocess_run_id`
- transcription basis state resolves as `NOT_STARTED | CURRENT | STALE` from `document_transcription_projections.active_preprocess_run_id`
- changing the active preprocess projection can therefore surface downstream staleness immediately without mutating historical downstream rows

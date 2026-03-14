# Transcription Diplomatic And Normalised Versioning Contract

Status: Implemented in Prompt 54
Scope: Diplomatic correction lineage, corrected PAGE-XML projection materialization, NORMALISED variant-layer lineage, suggestion decision events, and downstream stale-basis signaling

## Separation Of Concerns

- Diplomatic transcript stays authoritative for correction history.
- NORMALISED output is a separate variant layer and never overwrites diplomatic text.
- Assist suggestions persist only reviewer-visible fields (`suggestion_text`, confidence, status, metadata) and never hidden reasoning.

## Diplomatic Version Lineage

Line corrections are append-only:

- each correction appends a new `transcript_versions` row
- previous active version is linked through `superseded_by_version_id`
- `line_transcription_results.active_transcript_version_id` is moved to the new row
- optimistic concurrency is enforced with `version_etag`
- stale `version_etag` writes are rejected as conflicts

Engine output rows remain immutable.

## Corrected PAGE-XML Projection Rules

Correction persistence materializes a corrected PAGE-XML projection per approved version:

- base run PAGE-XML remains immutable at `.../transcription/{run_id}/page/{page_index}.xml`
- corrected projection writes to:
  - `.../transcription/{run_id}/versions/{transcript_version_id}/page/{page_index}.xml`
- `transcription_output_projections` is upserted with:
  - `corrected_pagexml_key`
  - `corrected_pagexml_sha256`
  - `corrected_text_sha256`
  - preserved `source_pagexml_sha256`

Downstream phases consume `transcription_output_projections`, not ad hoc edit replay.

## Token Anchor Refresh Or Stale Marker

If correction changes token boundaries, token text, or token geometry:

- preferred path: append replacement `token_transcription_results` with `projection_basis = REVIEW_CORRECTED`
- fallback path: set `line_transcription_results.token_anchor_status = REFRESH_REQUIRED`

Activation must treat non-`CURRENT` token-anchor status as a blocker.

## NORMALISED Variant-Layer Lineage

`transcript_variant_layers` remains append-only:

- `variant_kind = NORMALISED`
- each row pins to exact diplomatic basis (`base_transcript_version_id` for single-line layers, or `base_version_set_sha256` for page/multi-line layers)
- `base_projection_sha256` preserves projection basis
- regenerated normalised outputs append new rows; no rebinding of old layers to newer diplomatic versions

## Suggestion Decision Event Model

Suggestion decisions are auditable and append-only:

- current suggestion state projection: `transcript_variant_suggestions`
- immutable decision stream: `transcript_variant_suggestion_events`
- decision route updates suggestion status and appends an event
- decisioning does not mutate diplomatic text

## Downstream Redaction Basis Invalidation

When a corrected line belongs to the active transcription run:

- set `document_transcription_projections.downstream_redaction_state = STALE`
- persist `downstream_redaction_invalidated_at`
- persist explicit `downstream_redaction_invalidated_reason`

This prevents privacy/export flows from silently treating stale transcript basis as current.

## API Surfaces

- `PATCH /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/lines/{lineId}`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/variant-layers`
- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/variant-layers/NORMALISED/suggestions/{suggestionId}/decision`

RBAC:

- read: `PROJECT_LEAD`, `REVIEWER`, `RESEARCHER`, `ADMIN`
- correction/decision mutation: `PROJECT_LEAD`, `REVIEWER`, `ADMIN`

Audit events:

- `TRANSCRIPT_LINE_CORRECTED`
- `TRANSCRIPT_EDIT_CONFLICT_DETECTED`
- `TRANSCRIPT_DOWNSTREAM_INVALIDATED`
- `TRANSCRIPT_VARIANT_LAYER_VIEWED`
- `TRANSCRIPT_ASSIST_DECISION_RECORDED`

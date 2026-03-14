# Transcription Fallback And Compare Governance Contract

Status: Implemented in Prompt 52
Scope: Governed fallback invocation, fallback-engine admission, immutable base-run preservation, compare-read access, and explicit decision-only promotion controls

## Purpose

Fallback and compare are recovery and validation paths for transcription quality. They are not implicit promotion paths.

## Fallback invocation contract

Fallback runs are created through:

- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/fallback`

Fallback invocation is gated by explicit triggers on the base run:

- `SCHEMA_VALIDATION_FAILED`
- `ANCHOR_RESOLUTION_FAILED`
- `CONFIDENCE_BELOW_THRESHOLD`

If no trigger is detected, fallback run creation is rejected.

## Engine governance contract

Fallback engines supported by the canonical run schema:

- `KRAKEN_LINE`
- `TROCR_LINE` (optional, governed)
- `DAN_PAGE` (optional, governed)

Governance rules:

- all fallback engines resolve through `TRANSCRIPTION_FALLBACK` role mapping
- fallback engines must resolve to `APPROVED` catalog entries
- `TROCR_LINE` and `DAN_PAGE` are gated until an `ACTIVE` project assignment is present
- route-local engine forks and ad hoc schema variants are not allowed

## Immutability contract

Fallback execution never mutates base run data:

- fallback creates a separate transcription run
- base run PAGE-XML, line rows, token rows, and checksums remain unchanged
- fallback invocation context is captured in fallback run `params_json`

## Compare contract

Compare reads are provided by:

- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/compare`

Compare requests are rejected unless base and candidate runs share:

- `input_preprocess_run_id`
- `input_layout_run_id`
- `input_layout_snapshot_hash`

This prevents cross-basis diffing and invalid anchor-space comparisons.

## Compare decision contract

Decisions are persisted by:

- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/compare/decisions`

Semantics:

- explicit `KEEP_BASE` or `PROMOTE_CANDIDATE` only
- projection row is optimistic-concurrency guarded with `decision_etag`
- append-only chronology is stored in `transcription_compare_decision_events`
- source runs are not mutated by decision writes
- no automatic merge path exists

## RBAC contract

Read (`fallback status`, `compare`, `run status`) roles:

- `PROJECT_LEAD`
- `RESEARCHER`
- `REVIEWER`
- `ADMIN`

Write (`fallback create/cancel`, `compare decisions`) roles:

- `PROJECT_LEAD`
- `REVIEWER`
- `ADMIN`

## Audit contract

Fallback/compare events must be emitted on the canonical audit path:

- `TRANSCRIPTION_FALLBACK_RUN_CREATED`
- `TRANSCRIPTION_FALLBACK_RUN_CANCELED`
- `TRANSCRIPTION_FALLBACK_RUN_STATUS_VIEWED`
- `TRANSCRIPTION_RUN_COMPARE_VIEWED`
- `TRANSCRIPTION_COMPARE_DECISION_RECORDED`

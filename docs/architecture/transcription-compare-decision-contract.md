# Transcription Compare Decision Contract

Status: Implemented in Prompt 52
Scope: Compare decision projection shape, concurrency, append-only event chronology, and read/write API semantics

## Canonical persistence

Decision persistence uses two tables:

- `transcription_compare_decisions` (current projection row per target tuple)
- `transcription_compare_decision_events` (append-only event stream)

Decision target identity tuple:

- `document_id`
- `base_run_id`
- `candidate_run_id`
- `page_id`
- `line_id` (nullable)
- `token_id` (nullable)

At most one current projection row is allowed per tuple.

## Decision model

Allowed values:

- `KEEP_BASE`
- `PROMOTE_CANDIDATE`

Decision writes may include optional reason text (`decision_reason`) for reviewer rationale.

## Optimistic concurrency

Decision updates require `decision_etag`.

Rules:

- create flow: `decision_etag` must be omitted
- update flow: `decision_etag` must match current row
- stale or missing etag for an existing row is rejected

Every accepted write generates a new etag.

## Append-only event chronology

Each accepted create/update writes a new event row to `transcription_compare_decision_events`:

- `from_decision` (nullable on first write)
- `to_decision`
- `actor_user_id`
- `reason`
- `created_at`

This event stream is the immutable chronology for replay and audit.

## API contract

Write endpoint:

- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/compare/decisions`

Payload semantics:

- `baseRunId`, `candidateRunId`
- one or more decision items
- each item targets page/line/token scope
- each item includes decision and optional reason/etag

Response semantics:

- returns persisted decision projection rows with updated etags
- does not mutate base/candidate transcription run outputs

## Guardrails

- compare decisions are valid only for runs that pass compare-basis checks
- decisions are explicit reviewer actions, never inferred automatically
- no hidden merge/finalization side effects are triggered by decision writes alone

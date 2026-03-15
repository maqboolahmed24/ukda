# Transcription Compare Decision Contract

Status: Updated in Prompt 57
Scope: Compare read filters, explicit decision writes, append-only chronology, snapshot-hash conflict control, and immutable finalization into composed runs

## Canonical persistence

Compare state is split into:

- `transcription_compare_decisions`: current projection row per compare target
- `transcription_compare_decision_events`: append-only decision chronology

Decision target identity tuple:

- `document_id`
- `base_run_id`
- `candidate_run_id`
- `page_id`
- `line_id` (nullable)
- `token_id` (nullable)

At most one current projection row exists per tuple. Chronology is never rewritten.

## Compare read contract

Read endpoint:

- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}&page={pageNumber}&lineId={lineId}&tokenId={tokenId}`

Behavior:

- compares only runs that share preprocess run, layout run, and layout snapshot hash
- supports optional page/line/token filtering without creating a second compare route family
- returns line and token diffs plus engine metadata
- returns decision lineage metadata:
  - `compareDecisionSnapshotHash`
  - `compareDecisionCount`
  - `compareDecisionEventCount`

## Decision write contract

Write endpoint:

- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/compare/decisions`

Rules:

- explicit decisions only (`KEEP_BASE` or `PROMOTE_CANDIDATE`)
- create path must omit `decisionEtag`
- update path must provide current `decisionEtag`
- stale/missing etag for existing target is rejected
- accepted writes update the projection row and append one immutable event row

## Snapshot-hash conflict control

Decision snapshot hash is computed from:

- filtered current decision projection rows
- matching append-only decision events

This hash is exposed in compare reads and used as optimistic-lock input for finalize operations.

## Finalize contract (`REVIEW_COMPOSED`)

Finalize endpoint:

- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/compare/finalize`

Request shape:

- `baseRunId`
- `candidateRunId`
- optional `pageIds`
- optional `expectedCompareDecisionSnapshotHash`

Behavior:

- requires explicit decisions (no silent merge path)
- rejects stale expected snapshot hash
- creates a new immutable `transcription_runs` row with `engine = REVIEW_COMPOSED`
- writes run `params_json` lineage fields:
  - `baseRunId`
  - `candidateRunId`
  - `compareDecisionSnapshotHash`
  - `pageScope`
  - `finalizedBy`
  - `finalizedAt`
- rebuilds PAGE-XML output and composed token projections
- source runs remain immutable

## Audit and governance

Canonical events:

- `TRANSCRIPTION_RUN_COMPARE_VIEWED`
- `TRANSCRIPTION_COMPARE_DECISION_RECORDED`
- `TRANSCRIPTION_COMPARE_FINALIZED`

No hidden reasoning text is persisted or surfaced by compare endpoints.

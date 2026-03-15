# Privacy Run Review Projection Model

Status: Updated through Prompt 65
Scope: Phase 5 run-review schema, dual-control enforcement, immutable approval snapshots, reviewed-output generation, append-only timelines, and downstream readiness handoff

## Canonical records

Phase 5.0 persistence surfaces are modeled by:

- `redaction_runs`
- `redaction_findings`
- `redaction_area_masks`
- `redaction_decision_events` (append-only)
- `redaction_page_reviews`
- `redaction_page_review_events` (append-only)
- `redaction_run_reviews`
- `redaction_run_review_events` (append-only)
- `document_redaction_projections`
- `redaction_outputs`
- `redaction_run_outputs`
- `redaction_run_output_events` (append-only)

## Phase 5 baseline decision engine

Phase 5 baseline decisions are masking-only:

- supported action type: `MASK`
- deferred action types: `PSEUDONYMIZE`, `GENERALIZE` (Phase 7)
- every finding decision mutation appends a `redaction_decision_events` row
- `redaction_findings` remains the current mutable projection of latest decision state

Overlap and span handling for safeguarded preview generation is deterministic:

- token-linked spans are preferred when token references are available
- overlaps are resolved by stable ordering (start offset, longer span preference on same start, token-linked precedence, deterministic tie-breakers)
- masking preserves punctuation and whitespace while redacting alphanumeric content
- area-mask-backed findings without text spans are represented as area-mask-only markers, not fake token spans

## Run lineage and immutable policy snapshot

Each `redaction_runs` row captures deterministic run inputs and policy snapshot material:

- transcription/layout basis IDs
- run kind (`BASELINE | POLICY_RERUN`)
- supersession links
- policy snapshot ID/hash/json payload at creation time
- detector version and lifecycle timestamps

Snapshot fields are run-local and immutable after creation.

## Review model and lock semantics

`redaction_run_reviews` is the run-level review projection.

- `review_status`: `NOT_READY | IN_REVIEW | APPROVED | CHANGES_REQUESTED`
- approval fields (`approved_by`, `approved_at`, snapshot references)
- `locked_at` indicates approved-run locking

Approved runs reject mutable decision paths (finding/page/area-mask update routes) through conflict handling.

## Dual-control page-review enforcement

`redaction_page_reviews` carries first-review and second-review state:

- `requires_second_review`
- `second_review_status` (`NOT_REQUIRED | PENDING | APPROVED | CHANGES_REQUESTED`)
- `second_reviewed_by`
- `second_reviewed_at`

Prompt 64 enforcement rules:

- high-risk overrides drive `requires_second_review = true`
- same-user second review is rejected when second review is required
- first-review approval on required-second-review pages keeps second review pending
- second-review approval/changes-requested append dedicated page-review events
- requirement recalculation is deterministic from high-risk override projection state

## Run-review lifecycle gates

Prompt 65 hardens run review transitions:

- `start-review` is allowed only from `NOT_READY`
- start-review requires page-review projections to exist and no page in `NOT_STARTED`
- `complete-review` is allowed only from `IN_REVIEW`
- `complete-review APPROVED` requires all of:
  - every page review is `APPROVED`
  - every required second review is `APPROVED`
- completion appends `redaction_run_review_events` and never mutates history tables in place
- reviewed output generation is system-triggered after approval and is no longer a pre-approval gate

## Immutable approval snapshot

On `APPROVED` completion, the run persists:

- `approved_snapshot_key`
- `approved_snapshot_sha256`
- `locked_at`

The snapshot payload is deterministic over locked decision-set state:

- findings (including span/token references used for masking)
- area-mask lineage refs
- page-review projection state
- run-level safeguarded output references present at lock time

Snapshot bytes are persisted as immutable controlled artefacts keyed by `approved_snapshot_sha256`.

After approval:

- finding decision writes are rejected
- page-review writes are rejected
- area-mask writes are rejected
- further reviewer changes require a successor run

Reviewed preview/output regeneration reads from the immutable approved snapshot artefact, not mutable live decision tables.

## Active projection ownership

`document_redaction_projections.active_redaction_run_id` is the only active-run selector.

Activation rules:

- run review must be approved
- required preview/readiness gates must pass
- activation updates projection ownership without mutating historical run rows
- activation also updates downstream transcription redaction state coherence for the run basis

## Output status contract

Per-page and per-run output status uses explicit finite values:

- `PENDING`
- `READY`
- `FAILED`
- `CANCELED`

Preview status and run output status are first-class API surfaces and must represent not-ready/failed states without fabrication.

Preview hash rules:

- page-level `preview_sha256` is derived from deterministic safeguarded preview content
- hash changes only when resolved masking decisions change
- review-status-only updates do not fabricate preview hashes
- run-level `output_manifest_sha256` is derived from canonical `(page_id, preview_sha256)` rows plus approved snapshot linkage when all page outputs are `READY`
- preview artefacts must never store raw unmasked source text

Run-level readiness is explicit and typed:

- `APPROVAL_REQUIRED`
- `APPROVED_OUTPUT_PENDING`
- `OUTPUT_GENERATING`
- `OUTPUT_FAILED`
- `OUTPUT_CANCELED`
- `OUTPUT_READY`

Downstream handoff (`Phase 6/8`) is true only when:

- run review is `APPROVED`
- run output status is `READY`
- readiness state is `OUTPUT_READY`

## Timeline semantics

Run/page timelines are merged from append-only event tables with stable ordering:

1. `created_at`
2. source-table precedence
3. source event ID

Run timeline precedence includes:

1. `redaction_decision_events`
2. `redaction_page_review_events`
3. `redaction_run_review_events`
4. `redaction_run_output_events`

History must not be reconstructed from mutable projection tables.

## Rerun compare semantics

`/redaction-runs/compare` is read-only and analytic across base/candidate runs.

Prompt 64 compare deltas include:

- finding-count deltas
- decision-status counts per page
- decision-status signed deltas (`candidate - base`)
- changed first-review status
- changed second-review status
- preview-status deltas and `preview_ready_delta`

Compare does not auto-merge or auto-promote decisions across runs.

## API alignment

Typed API surfaces expose the model contract for:

- run list/detail/status/active projection
- run review start/complete flows
- page findings and page review projections
- area-mask revision flow
- run/page timeline views
- compare projection
- safeguarded preview status and bytes
- run output and run output status with explicit readiness projection

Reviewed output RBAC:

- `PROJECT_LEAD`, `REVIEWER`, `ADMIN` can read reviewed outputs
- `AUDITOR` is read-only and allowed only for `APPROVED` runs
- `RESEARCHER` is denied reviewed-output artefact/status reads

Run output routes do not expose raw storage keys or public object URLs.

## Next prompt deepening

- Prompt 66 deepens privacy regression packs, synthetic disclosure checks, and reviewer-safety gates.

# Layout Activation Gates And Downstream Invalidation Contract

## Purpose
This contract defines canonical layout-run activation readiness, explicit blocker payloads, and downstream transcription-basis transitions.

## Canonical Activation Gate
Activation is evaluated against one typed gate object (`activationGate`) with:

- `eligible`
- `blockerCount`
- `blockers[]` (typed codes, counts, page IDs, page numbers, and operator-facing messages)
- `downstreamImpact` (predicted transcription basis state if activation proceeds)
- `evaluatedAt`

There is no silent fallback or hidden override path.

## Blocker Codes
The evaluator can emit these blocker codes:

- `LAYOUT_RUN_NOT_SUCCEEDED`
- `LAYOUT_RECALL_PAGE_RESULTS_MISSING`
- `LAYOUT_RECALL_STATUS_MISSING`
- `LAYOUT_RECALL_STATUS_UNRESOLVED`
- `LAYOUT_RECALL_CHECK_MISSING`
- `LAYOUT_RESCUE_PENDING`
- `LAYOUT_RESCUE_ACCEPTANCE_MISSING`

## No-Silent-Drop Enforcement
Activation remains blocked until all required recall-first conditions are explicit:

- every page has explicit recall class (`COMPLETE | NEEDS_RESCUE | NEEDS_MANUAL_REVIEW`)
- every page has persisted recall-check coverage
- no page has pending rescue candidates
- every `NEEDS_RESCUE` page has at least one accepted rescue candidate

## Projection And Downstream Behavior
On successful activation, `document_layout_projections` is the only canonical state writer:

- `active_layout_run_id`
- `active_input_preprocess_run_id`
- `active_layout_snapshot_hash`
- `downstream_transcription_state`
- `downstream_transcription_invalidated_at`
- `downstream_transcription_invalidated_reason`

Downstream transcription state resolution:

- `NOT_STARTED` when no active transcription basis exists
- `CURRENT` when active transcription projection already matches the activated layout run + snapshot
- `STALE` when activation supersedes the transcription basis

## Superseding Reasons
Reason strings distinguish invalidation origins:

- activation supersession: `LAYOUT_ACTIVATION_SUPERSEDED: ...`
- manual edit supersession: `LAYOUT_MANUAL_EDIT_SUPERSEDED: ...`

## API Surfaces
Typed gate data is exposed through existing routes:

- run detail/list payloads (`DocumentLayoutRun.activationGate`)
- activate response (`ActivateDocumentLayoutRunResponse.activationGate`)
- activation conflict response (`409`) with `activationGate` and `blockers`

Projection payloads expose canonical downstream basis fields so consumers never infer from latest-run heuristics.


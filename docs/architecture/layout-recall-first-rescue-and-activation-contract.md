# Layout Recall-First, Rescue, and Activation Contract

> Status: Active (Prompt 44)
> Scope: Second-stage missed-text recall checks, rescue-candidate persistence, typed read APIs, activation blockers, and Phase 4 handoff preparation

This contract defines the normative recall-first sequence for Phase 3 layout runs:

1. segment layout geometry
2. run missed-text recall checks
3. persist rescue candidates where risk exists
4. require explicit page recall resolution before any downstream activation

## Explicit Page Recall Classes

Every successful page result resolves to exactly one value:

- `COMPLETE`
- `NEEDS_RESCUE`
- `NEEDS_MANUAL_REVIEW`

No hidden fallback class is allowed.

## Persisted Data Model

## `layout_recall_checks`

One versioned recall-check record per run/page pair:

- `run_id`
- `page_id`
- `recall_check_version`
- `missed_text_risk_score`
- `signals_json`
- `created_at`

Current version: `layout-recall-v1`.

## `layout_rescue_candidates`

Persisted candidate rows generated during recall checks:

- `id`
- `run_id`
- `page_id`
- `candidate_kind` (`LINE_EXPANSION | PAGE_WINDOW`)
- `geometry_json`
- `confidence`
- `source_signal`
- `status` (`PENDING | ACCEPTED | REJECTED | RESOLVED`)
- `created_at`
- `updated_at`

## API Surfaces

Read APIs:

- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/recall-status`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/rescue-candidates`

`recall-status` includes:

- `page_recall_status`
- `recall_check_version`
- `missed_text_risk_score`
- `signals_json`
- per-status rescue counts
- blocker reason codes
- unresolved count

## Activation Blockers

A layout run activation is rejected when any of these conditions is true:

- run status is not `SUCCEEDED`: `LAYOUT_RUN_NOT_SUCCEEDED`
- page results missing: `LAYOUT_RECALL_PAGE_RESULTS_MISSING`
- explicit recall class missing: `LAYOUT_RECALL_STATUS_MISSING`
- page status unresolved (not `SUCCEEDED`): `LAYOUT_RECALL_STATUS_UNRESOLVED`
- recall check missing: `LAYOUT_RECALL_CHECK_MISSING`
- `NEEDS_RESCUE` page without accepted candidate: `LAYOUT_RESCUE_ACCEPTANCE_MISSING`
- pending candidate still open: `LAYOUT_RESCUE_PENDING`

Activation APIs surface blockers through typed `activationGate` payloads. UI does not reconstruct blockers from raw tables.

Blocked activation emits the canonical audit event `LAYOUT_ACTIVATION_BLOCKED`.

## Audit Events

Recall/rescue read surfaces emit:

- `LAYOUT_RECALL_STATUS_VIEWED`
- `LAYOUT_RESCUE_CANDIDATES_VIEWED`

## Phase 4 Handoff Boundaries

Prompt 44 prepares handoff but does not run rescue transcription:

- rescue candidates provide stable references and explicit geometry for Phase 4 source selection (`RESCUE_CANDIDATE`/`PAGE_WINDOW` usage)
- ordinary line-based pages remain available through `layout_line_artifacts`
- `NEEDS_MANUAL_REVIEW` stays explicit and is never treated as rescued
- token anchors remain deferred to later prompts

## Non-Goals In This Contract

- rescue transcription execution
- token-anchor materialization
- privacy masking decisions
- search indexing activation logic

# Transcription Activation Token-Anchor Prerequisites And Downstream Use

Scope: Activation-time token-anchor readiness rules and how downstream phases consume activated token anchors.

## Activation Prerequisites

A transcription run can activate only when:
- run status is `SUCCEEDED`
- layout basis still matches active layout projection
- every page not marked `NEEDS_MANUAL_REVIEW` has token anchors
- every eligible line has `token_anchor_status = CURRENT`
- persisted token anchors are structurally valid (safe source references, valid source linkage, geometry present)

## Explicit Blockers

Activation is rejected with explicit conflict reasons when:
- eligible pages are missing token anchors
- eligible lines have stale/refresh-required token anchor status
- token anchors are invalid for source/reference/geometry integrity (`TOKEN_ANCHOR_INVALID`)

This prevents silent promotion of runs that cannot support exact downstream linking.

## Why This Gate Exists

Phase 4 outputs are downstream inputs. Activated transcription must expose stable anchors that support:
- correction refresh and anchor reconciliation in later correction workflows
- precise privacy finding-to-token attachment in Phase 5+
- exact search/highlight anchoring in later search/index prompts

## Downstream Consumption Expectations

Activated token anchors provide:
- deterministic `token_id` for stable references
- geometry for viewport highlighting and mask placement
- typed source provenance (`source_kind`, `source_ref_id`) for ordinary line vs rescue-path distinction

Downstream consumers should treat these as immutable run-level evidence anchors, not UI-derived coordinates.

## Ownership Boundaries

This contract covers only activation gating and anchor readiness.

Owned by later prompts/phases:
- manual correction authoring workflows
- transcript-normalization variants
- privacy decision logic
- search index build/sync orchestration

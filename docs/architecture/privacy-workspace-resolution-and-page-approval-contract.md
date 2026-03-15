# Privacy Workspace Resolution And Page Approval Contract

Status: Established in Prompt 63
Scope: Phase 5.3 workspace interaction model for finding decisions, page approval gating, deep-link semantics, and high-risk override signalling

## Ownership

Prompt 63 owns the privacy workspace fast-resolution layer on:

- `/projects/:projectId/documents/:documentId/privacy/workspace?page={pageNumber}&runId={runId}&findingId={findingId}&lineId={lineId}&tokenId={tokenId}`

Prompt 63 explicitly includes:

- deterministic `Next unresolved` navigation
- finding decision actions: approve, override, false-positive
- required reason capture for override and false-positive decisions
- page approval gating (`Approve page` disabled while unresolved count > 0)
- controlled versus safeguarded mode switching in the same bounded shell
- transcript/finding/canvas synchronization with line and token deep-link restore

Prompt 63 explicitly does not complete dual-control run completion or rerun compare expansion.

## Deep-Link Semantics

Canonical URL state:

- `page={pageNumber}` is 1-based and maps to canonical page order (`page_index + 1`).
- `runId={runId}` pins review state to one redaction run.
- `findingId={findingId}` focuses a finding decision target.
- `lineId={lineId}` focuses transcript line context.
- `tokenId={tokenId}` focuses token-linked context where available.
- `mode=controlled|safeguarded` preserves view mode.
- `highlights=off` persists highlight suppression in safeguarded mode.

`Next unresolved` resolution order is deterministic:

1. unresolved findings remaining after current finding on the current page
2. first unresolved finding on the next unresolved page in canonical page order, with wrap
3. no-op with truthful empty state when no unresolved findings remain

## Finding Resolution Flow

Workspace finding actions call the canonical API:

- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/findings/{findingId}`

Rules enforced by Prompt 63:

- `decisionEtag` is required for optimistic concurrency.
- `reason` is required when `decisionStatus` is `OVERRIDDEN` or `FALSE_POSITIVE`.
- stale writes return conflict and surface a calm workspace error; no silent overwrite.
- immutable approved-run locks surface as conflict; no post-approval mutation path.

## Page Approval Gating

Workspace page approval uses:

- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/review`

Rules:

- `Approve page` remains disabled while `unresolvedCount > 0`.
- `reviewEtag` is required and stale writes surface conflict.
- rail and inspector immediately reflect review status after successful update.

## High-Risk Override UX

Prompt 63 surfaces high-risk conditions without implementing full dual-control completion here.

High-risk signals displayed to reviewers include:

- decision changes to `FALSE_POSITIVE`
- area-mask-backed context
- policy snapshot category signals for dual-review-required categories
- detector disagreement or ambiguous-overlap markers in `basis_secondary_json`
- existing backend `overrideRiskClassification = HIGH`

When high-risk signals are present, the workspace explicitly warns that second review is required downstream.

## Prompt 64 Handoff

Prompt 64 deepens:

- mandatory second-review enforcement with distinct reviewer identity
- run-level completion gates using required second-review state
- compare across reruns and decision lineage differentials

Prompt 63 remains scoped to fast page-level resolution and safe, auditable reviewer ergonomics.

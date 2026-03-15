# Transcription Rescue Activation Gates

Status: Added in Prompt 58  
Scope: Recall-first rescue transcription readiness, manual-resolution controls, and activation blocking semantics

## Goal

Activation of a transcription run must be truthful:

- pages marked `NEEDS_RESCUE` cannot silently promote when accepted rescue sources are not transcribed
- pages marked `NEEDS_MANUAL_REVIEW` cannot silently promote without explicit manual resolution
- token-anchor prerequisites remain mandatory before promotion

## Source semantics

Rescue-backed transcription output remains first-class and explicit:

- `sourceKind = RESCUE_CANDIDATE` for `LINE_EXPANSION` rescue candidates
- `sourceKind = PAGE_WINDOW` for `PAGE_WINDOW` rescue candidates
- `sourceRefId` remains the stable rescue candidate ID
- line-backed output (`sourceKind = LINE`) and rescue-backed output can coexist on the same page

No remapping of rescue text onto line anchors is performed during readiness checks.

## Rescue readiness APIs

The canonical read/write surfaces are:

- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/rescue-status`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/rescue-sources`
- `PATCH /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/rescue-resolution`

Responses expose typed readiness values:

- `readinessState`: `READY | BLOCKED_RESCUE | BLOCKED_MANUAL_REVIEW | BLOCKED_PAGE_STATUS`
- `blockerReasonCodes`:
  - `RESCUE_SOURCE_MISSING`
  - `RESCUE_SOURCE_UNTRANSCRIBED`
  - `MANUAL_REVIEW_RESOLUTION_REQUIRED`
  - `PAGE_TRANSCRIPTION_NOT_SUCCEEDED`

Resolution writes are typed as:

- `resolutionStatus = RESCUE_VERIFIED | MANUAL_REVIEW_RESOLVED`

## Activation behavior

`POST /.../transcription-runs/{runId}/activate` now enforces rescue readiness before projection promotion.

If blocked, the endpoint returns `409` with:

- `detail` (human-readable conflict reason)
- `blockerCodes` (typed activation blockers)
- `blockerCount`
- `rescueStatus` snapshot when available

Activation blocker codes include:

- run-level: `RUN_NOT_SUCCEEDED`, `RUN_LAYOUT_BASIS_STALE`, `RUN_LAYOUT_SNAPSHOT_STALE`, `RUN_LAYOUT_PROJECTION_MISSING`
- anchor-level: `TOKEN_ANCHOR_MISSING`, `TOKEN_ANCHOR_INVALID`, `TOKEN_ANCHOR_STALE`
- rescue/manual-review-level: `RESCUE_SOURCE_MISSING`, `RESCUE_SOURCE_UNTRANSCRIBED`, `MANUAL_REVIEW_RESOLUTION_REQUIRED`, `PAGE_TRANSCRIPTION_NOT_SUCCEEDED`

No silent override path is available.

## RBAC

Read surfaces:

- `PROJECT_LEAD`
- `REVIEWER`
- `RESEARCHER`
- `ADMIN`

Rescue-resolution writes and activation mutations:

- `PROJECT_LEAD`
- `REVIEWER`
- `ADMIN`

## Audit events

Canonical events:

- `TRANSCRIPTION_RESCUE_STATUS_VIEWED`
- `TRANSCRIPTION_RESCUE_RESOLUTION_UPDATED`
- `TRANSCRIPTION_RUN_ACTIVATION_BLOCKED`

These are emitted through the existing audit pipeline with allowlisted metadata only.

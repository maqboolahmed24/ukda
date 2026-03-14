# Transcription Reviewer Routing And Hotspot Ranking

## Purpose
This contract defines deterministic reviewer routing for uncertain transcription pages.

## Ranking Model
Each triage page row includes:
- `rankingScore`
- `rankingRationale`
- `issues`

Ranking is deterministic and stable using explicit factors:
- failed page status
- low-confidence line count
- minimum confidence
- structured validation failures
- segmentation mismatch signals
- token-anchor refresh requirements

Tie-break order:
1. descending `rankingScore`
2. ascending `pageIndex`
3. ascending `pageId`

## Reviewer Assignment
Assignment route:
- `PATCH /projects/{projectId}/documents/{documentId}/transcription/triage/pages/{pageId}/assignment`

Payload:
- `runId` (optional)
- `reviewerUserId` (optional; unset clears assignment)

Row fields:
- `reviewerAssignmentUserId`
- `reviewerAssignmentUpdatedBy`
- `reviewerAssignmentUpdatedAt`

## RBAC
View triage/metrics/workspace confidence surfaces:
- `PROJECT_LEAD`, `REVIEWER`, `RESEARCHER`, `ADMIN`

Mutate reviewer assignment:
- `PROJECT_LEAD`, `REVIEWER`, `ADMIN`

## Audit Events
- `TRANSCRIPTION_TRIAGE_VIEWED`
- `TRANSCRIPTION_TRIAGE_ASSIGNMENT_UPDATED`

## Workspace Routing Hooks
Workspace route deep links support page and uncertainty context:
- `runId`
- `page`
- `lineId`
- `tokenId`
- `sourceKind`
- `sourceRefId`

Low-confidence review hooks:
- toggle highlight for low-confidence lines
- selected-line confidence inspector
- optional per-character cue preview when char-box payload exists
- keyboard `Next low-confidence line` action

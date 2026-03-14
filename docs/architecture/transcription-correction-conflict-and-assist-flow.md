# Transcription Correction, Conflict, And Assist Flow

Status: Implemented for Prompt 56
Scope: Diplomatic line correction lifecycle, optimistic-concurrency conflicts, and assist-suggestion decisioning

## Diplomatic correction flow

Correction writes are append-only and version-gated.

Primary write endpoint:

- `PATCH /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/lines/{lineId}`

Request contract:

- `textDiplomatic`
- `versionEtag`
- optional `editReason`

Response contract includes:

- updated line snapshot
- active transcript version
- output projection snapshot
- downstream invalidation flags (`downstreamRedactionInvalidated` and related fields)

## Optimistic concurrency and conflict handling

If `versionEtag` is stale, the API returns conflict and the workspace must:

- show an explicit conflict state
- avoid silent overwrite
- offer a reload action for latest line/token state
- preserve local draft visibility so reviewer can reconcile safely

No automatic merge is performed.

## Save/discard workflow behavior

Workspace supports:

- per-line save
- save-all dirty lines
- per-line discard
- discard-all local drafts
- local undo/redo stacks per line

Save status remains visible as one of:

- all edits saved
- unsaved edits present
- saving in progress
- conflict detected

## Assist suggestion decision flow

Assist decisions are explicit reviewer actions and do not auto-apply.

Decision endpoint:

- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/variant-layers/NORMALISED/suggestions/{suggestionId}/decision`

Request contract:

- `decision` (`ACCEPT` or `REJECT`)
- optional `reason`

Rules:

- diplomatic text remains primary editable source
- normalised layer remains separate and auditable
- hidden reasoning text is never surfaced

## Workspace-read context fetches

Workspace line fetches pass context to preserve deep-link provenance and emit workspace-view audit events:

- `GET /.../lines?workspaceView=true&lineId=...&tokenId=...&sourceKind=...&sourceRefId=...`

Tokens fetch remains:

- `GET /.../tokens`

## Audit events

Correction/conflict/assist activity maps to canonical events:

- `TRANSCRIPTION_WORKSPACE_VIEWED`
- `TRANSCRIPT_LINE_CORRECTED`
- `TRANSCRIPT_EDIT_CONFLICT_DETECTED`
- `TRANSCRIPT_ASSIST_DECISION_RECORDED`
- `TRANSCRIPT_DOWNSTREAM_INVALIDATED` (when correction invalidates downstream redaction basis)

Each event records route and run/page/line context for reviewer lineage.

## Security and governance guardrails

- correction and assist decisions are restricted to reviewer-capable roles
- view routes remain role-gated but broader (`PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, `ADMIN`)
- no raw model reasoning payloads are shown in workspace UI
- provenance remains append-only through transcript versions and audit chain

# Transcription Correction, Conflict, And Assist Flow

Status: Updated in Prompt 57
Scope: Diplomatic correction writes, transcript-version lineage reads, compare conflict control, and assist-suggestion decisioning

## Canonical correction flow

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

Version history reads are first-class reviewer surfaces:

- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/lines/{lineId}/versions`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/lines/{lineId}/versions/{versionId}`

Lineage payloads include:

- transcript version fields (`editorUserId`, `createdAt`, `editReason`, `baseVersionId`, `supersededByVersionId`)
- `isActive` marker for current projection
- `sourceType` (`ENGINE_OUTPUT`, `REVIEWER_CORRECTION`, `COMPARE_COMPOSED`)

## Optimistic concurrency and conflict handling

If `versionEtag` is stale, the API returns conflict and the workspace must:

- show an explicit conflict state
- avoid silent overwrite
- offer a reload action for latest line/token state
- preserve local draft visibility so reviewer can reconcile safely

No automatic merge is performed.

Compare finalization uses the same trust model via snapshot-hash conflict control:

- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/compare/finalize`
- `expectedCompareDecisionSnapshotHash` is optional but recommended
- stale expected hash returns conflict and requires compare refresh before retry
- no silent overwrite of newly recorded compare decisions

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

Conflict surfaces remain bounded and keyboard-safe:

- explicit conflict panel with reload action
- local draft state remains visible after conflict
- save status badges remain stable while retrying

## Assist suggestion decision flow

Assist decisions are explicit reviewer actions and do not auto-apply.

Decision endpoint:

- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/variant-layers/NORMALISED/suggestions/{suggestionId}/decision`

Request contract:

- `decision` (`ACCEPT` or `REJECT`)
- optional `reason`

Rules:

- diplomatic text remains primary editable source
- normalised layer remains separate, auditable, and lineage-linked via `baseTranscriptVersionId`
- hidden reasoning text is never surfaced

## Compare decision + finalize flow

Compare decisions are explicit reviewer writes:

- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/compare/decisions`
- allowed decisions: `KEEP_BASE` and `PROMOTE_CANDIDATE`
- create must omit `decisionEtag`; updates require current `decisionEtag`
- each accepted write appends immutable decision-event chronology

Finalization creates immutable composed output:

- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/compare/finalize`
- creates a new `REVIEW_COMPOSED` run
- source runs remain immutable
- composed run `params_json` records `baseRunId`, `candidateRunId`, `compareDecisionSnapshotHash`, `pageScope`, `finalizedBy`, `finalizedAt`

## Workspace-read context fetches

Workspace line fetches pass context to preserve deep-link provenance and emit workspace-view audit events:

- `GET /.../lines?workspaceView=true&lineId=...&tokenId=...&sourceKind=...&sourceRefId=...`

Tokens fetch remains:

- `GET /.../tokens`

## Audit events

Correction/conflict/assist activity maps to canonical events:

- `TRANSCRIPTION_WORKSPACE_VIEWED`
- `TRANSCRIPTION_RUN_COMPARE_VIEWED`
- `TRANSCRIPTION_COMPARE_DECISION_RECORDED`
- `TRANSCRIPTION_COMPARE_FINALIZED`
- `TRANSCRIPT_LINE_CORRECTED`
- `TRANSCRIPT_LINE_VERSION_HISTORY_VIEWED`
- `TRANSCRIPT_LINE_VERSION_VIEWED`
- `TRANSCRIPT_EDIT_CONFLICT_DETECTED`
- `TRANSCRIPT_ASSIST_DECISION_RECORDED`
- `TRANSCRIPT_DOWNSTREAM_INVALIDATED` (when correction invalidates downstream redaction basis)

Each event records route and run/page/line context for reviewer lineage.

## Security and governance guardrails

- correction and assist decisions are restricted to reviewer-capable roles
- view routes remain role-gated but broader (`PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, `ADMIN`)
- compare decision writes and compare finalize are restricted to (`PROJECT_LEAD`, `REVIEWER`, `ADMIN`)
- no raw model reasoning payloads are shown in workspace UI
- provenance remains append-only through transcript versions and audit chain

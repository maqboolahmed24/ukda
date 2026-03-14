# Layout Edit Downstream Transcription Invalidation

## Purpose
Manual layout edits can change the active transcription basis. This contract ensures downstream state is never silently left `CURRENT` after active-run geometry changes.

## Invalidation Rule
When `PATCH .../layout-runs/{runId}/pages/{pageId}/elements` saves an edit:
- If `{runId}` is the document projection's active layout run:
  - set `document_layout_projections.downstream_transcription_state = STALE`
  - set `downstream_transcription_invalidated_at`
  - set `downstream_transcription_invalidated_reason`
- If `{runId}` is not active, downstream transcription state is not promoted to stale by that edit.

## Persistence Path
- Invalidation is written through the canonical projection model (`document_layout_projections`).
- No parallel flags or side channels are used.

## API/UX Surface
`PATCH .../elements` response includes:
- `downstreamTranscriptionInvalidated`
- `downstreamTranscriptionState`
- `downstreamTranscriptionInvalidatedReason`

Workspace save messaging surfaces this state directly after edit save.

Reason strings are prefixed so operators can distinguish source:

- manual page edits: `LAYOUT_MANUAL_EDIT_SUPERSEDED: ...`
- activation supersession: `LAYOUT_ACTIVATION_SUPERSEDED: ...`

## Audit Events
- `LAYOUT_EDIT_APPLIED` always for successful edit save.
- `LAYOUT_DOWNSTREAM_INVALIDATED` when the save marks active transcription basis stale.

## Phase 4 Alignment
Phase 4 activation can restore downstream state to `CURRENT` only after a transcription run is activated against the current layout snapshot. This prevents stale-basis transcription drift.

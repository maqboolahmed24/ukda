# Transcription Workspace UX Contract

Status: Implemented for Prompt 56
Scope: Canonical correction workspace for source, transcript, confidence, and reviewer actions in one deep-linkable browser route

## Ownership

The transcription workspace is owned by one route family only:

- `/projects/:projectId/documents/:documentId/transcription/workspace`

This route is the only editable diplomatic-transcript workspace. No second correction surface is allowed.

## Route and deep-link context

Workspace context is URL-driven and reload-safe:

- `page` (1-based page focus)
- `runId` (transcription run focus)
- `mode` (`reading-order` or `as-on-page`)
- `lineId` (optional selected line)
- `tokenId` (optional selected token)
- `sourceKind` and `sourceRefId` (optional provenance context for rescue/page-window anchors)

Context restoration requirements:

- refresh restores run/page/mode and optional line/token/source focus
- back/forward preserves review navigation history
- no hidden client-only state is allowed to compete with URL state

## Workspace composition

The route renders one bounded workspace shell with three coordinated panes:

- left rail: page filmstrip
- center: source image with line/token overlays
- right panel: transcript editor

The workspace follows shell-state choreography (`Expanded`, `Balanced`, `Compact`, `Focus`) and uses drawers when side panels are collapsed.

## Editor contract

The transcript panel must support:

- mode switch: `Reading order` and `As on page`
- virtualized line list
- inline per-line editing
- per-line edited/saved indicators
- selected-line confidence inspector
- line crop preview

Keyboard-first controls:

- `Enter`: save and next line (from line editor)
- `Ctrl/Cmd+S`: save selected line
- `Up/Down`: line navigation (outside text-entry targets)
- `Alt+N`: jump to next low-confidence line
- `Ctrl/Cmd+Z`, `Ctrl/Cmd+Shift+Z`: local undo/redo

## Confidence and hotspot behavior

Workspace highlights and routing remain reviewer-focused:

- low-confidence lines are visibly flagged
- `Next issue` moves to next low-confidence line
- selected line shows confidence value, band, and basis
- character-level cues are shown only when payload preview is present
- missing char cues are surfaced explicitly (not silently implied)

## Assist and variant behavior

When NORMALISED variant layers are available:

- assist panel is collapsible
- suggestions list includes status, confidence, and reason metadata
- accept/reject decisions are explicit reviewer actions
- diplomatic remains the primary editable view
- normalised view is read-only

When variant layers are unavailable, the assist area must show an explicit unavailable/empty state.

## Accessibility and interaction safety

The workspace must preserve:

- visible focus for all interactive controls
- no keyboard traps in panes or drawers
- reduced-motion behavior for overlay transitions
- calm, explicit feedback for save state and conflicts

## Audit linkage

Workspace actions are audit-visible through canonical events:

- `TRANSCRIPTION_WORKSPACE_VIEWED`
- `TRANSCRIPT_LINE_CORRECTED`
- `TRANSCRIPT_EDIT_CONFLICT_DETECTED`
- `TRANSCRIPT_ASSIST_DECISION_RECORDED`

## Out of scope for this contract

This workspace contract does not define:

- inference backend behavior
- fallback-run governance rollout details
- compare decision UX beyond existing compare route
- CER/WER evaluation harness workflows

Those are extended by later prompts and phase work.

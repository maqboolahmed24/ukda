You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed phase files before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first on each run.

## Mandatory first actions
1. Inspect the full repository tree.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-04-handwriting-transcription-v1.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` for rescue-context deep links and source semantics
3. Then review the current repository generally — transcription workspace shells, line/token APIs, correction/versioning APIs, confidence/triage outputs, variant-layer APIs, shared UI primitives, browser tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second transcription workspace, a second correction UI path, or hidden client-only state that fights the deep-linkable workspace route.

## Source-of-truth hierarchy
Use this precedence order when implementing:
1. The specific `/phases` files listed in this prompt for product behavior and acceptance logic.
2. `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md` when this prompt depends on web-first execution semantics.
3. `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` when this prompt depends on recall-first, rescue, token-anchor, search-anchoring, or conservative-masking semantics.
4. `/phases/blueprint-ukdataextraction.md`, `/phases/README.md`, `/phases/ui-premium-dark-blueprint-obsidian-folio.md`, and `/phases/phase-00-foundation-release.md` as supporting product context when they are listed or clearly relevant.
5. This prompt for task scope and deliverables.
6. Current repository state for reconciling implementation details.
7. Official external docs for implementation mechanics only.

Treat current repository state as implementation context, not as the primary source of product truth.

## Conflict-resolution rule
- `/phases` wins for workspace layout, correction ergonomics, keyboard controls, variant-layer behavior, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that this is an editor-grade, bounded, browser-native workspace with append-only provenance behind it.

## Objective
Create the transcription workspace with source, transcript, confidence, and correction in one seamless flow.

This prompt owns:
- the full Phase 4.3 workspace UX
- source image + overlay + transcript-panel composition
- deep-linkable line/token/source context restoration
- inline line editing against the append-only backend APIs
- save/discard/conflict handling
- mode switching between `Reading order` and `As on page`
- virtualized line list
- confidence display and hotspot navigation
- line crop preview
- per-line edited indicators and save status
- optional collapsed assist panel and diplomatic/normalised toggle when variant layers exist

This prompt does not own:
- primary inference backend
- fallback engine rollout
- model-governance screens
- privacy-review features
- search/export features
- a second transcription editor outside the canonical workspace route

## Phase alignment you must preserve
From Phase 4 Iteration 4.3 and 4.6:

### Workspace route
- `/projects/:projectId/documents/:documentId/transcription/workspace?page={pageNumber}&runId={runId}&lineId={lineId}&tokenId={tokenId}&sourceKind={sourceKind}&sourceRefId={sourceRefId}`

### Required workspace layout
- left rail: page filmstrip
- center canvas: image with overlays
- right panel: transcript editor

### Editor capabilities
- mode switch:
  - `Reading order`
  - `As on page`
- virtualized line list
- inline line editing
- line crop preview for precise verification

### Toolbar and ergonomics
- save status indicator
- next/previous line
- next issue navigation
- keyboard-first controls:
  - `Enter`: save and next
  - `Ctrl/Cmd+S`: save
  - `Up/Down`: line navigation
- local undo/redo
- per-line edited indicator

### Assist and normalised view
When variant-layer support exists:
- collapsed Assist panel with suggestion list and reasons
- per-suggestion accept/reject controls
- `Diplomatic` vs `Normalised` view toggle

Rules:
- assist cannot auto-apply changes
- diplomatic transcript remains primary
- normalised view is explicitly separate and auditable

### Correction semantics
- corrections are append-only
- optimistic concurrency uses `version_etag`
- save conflicts are surfaced safely
- no hidden reasoning text is shown or persisted
- editing the active transcription run can make downstream redaction state `STALE`

### Required audit events
Emit or reconcile:
- `TRANSCRIPTION_WORKSPACE_VIEWED`
- `TRANSCRIPT_LINE_CORRECTED`
- `TRANSCRIPT_EDIT_CONFLICT_DETECTED`
- `TRANSCRIPT_ASSIST_DECISION_RECORDED` when assist support exists

## Implementation scope

### 1. Canonical transcription workspace
Implement or refine:
- `/web/app/(authenticated)/projects/[projectId]/documents/[documentId]/transcription/workspace/page.tsx` or the closest equivalent

Requirements:
- bounded single-fold workspace
- canonical shell integration
- source image/overlay center surface
- transcript editor right panel
- page filmstrip left rail
- deep-link-safe routing using `page`, `runId`, `lineId`, `tokenId`, `sourceKind`, and `sourceRefId`
- dark, dense, calm, review-grade tone

### 2. Transcript editor flow
Implement or refine the core editor.

Requirements:
- virtualized line list
- inline editing
- line highlight and source sync with canvas
- line crop preview
- selected line confidence display
- per-line edited indicator
- save status indicator
- no giant full-document text area
- no page-level vertical sprawl

### 3. Mode switch
Implement the required transcript-view modes.

Requirements:
- `Reading order`
- `As on page`
- mode switching is exact and reload-safe where it belongs
- ordering uses canonical layout/transcription anchors
- no second hidden ordering model

### 4. Save/discard/conflict behavior
Use the append-only backend APIs from the repo.

Requirements:
- save against the canonical PATCH line endpoint
- `Ctrl/Cmd+S` saves
- `Enter` save-and-next where appropriate
- `Up/Down` line navigation
- local undo/redo
- stale `version_etag` conflict handling is calm and actionable
- unsaved changes are visible but not noisy
- no silent overwrite of newer work

### 5. Confidence and hotspot review
Integrate the confidence outputs.

Requirements:
- selected line confidence in the editor or inspector area
- low-confidence highlighting
- `Next low-confidence line` navigation
- confidence cues remain exact and restrained
- optional char-level cues when available
- unavailable cues are handled explicitly

### 6. Deep-link restoration
Implement deep-link restoration for review context.

Requirements:
- `lineId` highlights the intended line
- `tokenId` highlights the intended token when anchors exist
- `sourceKind` and `sourceRefId` route rescue or page-window context correctly
- page/run/line/token context survives refresh and back/forward
- no secret-bearing URLs
- no hidden client-only state fighting the route

### 7. Assist and normalised view integration
If variant-layer support exists, integrate it without compromising provenance.

Requirements:
- collapsed Assist panel
- suggestion list and reasons
- accept/reject controls that use the canonical suggestion-decision API
- `Diplomatic` vs `Normalised` view toggle
- diplomatic view remains primary
- assist never auto-applies changes
- hidden reasoning is never surfaced

If variant-layer APIs are not yet present, keep the assist area as a clear unavailable surface rather than faking it.

### 8. Workspace browser quality
Harden the UX.

Requirements:
- keyboard-first operation
- no keyboard traps
- focus remains visible and unobscured
- reduced-motion and reduced-transparency preferences are respected
- `Expanded | Balanced | Compact | Focus` states remain consistent
- filmstrip, canvas, and editor compress in a practical order
- visual regression coverage for:
  - read-only state
  - editing state
  - conflict state
  - low-confidence highlight state
  - assist panel open/closed when supported

### 9. Audit and regression
Use the canonical audit path and add workspace coverage.

At minimum cover:
- edit persists after refresh
- conflict detection surfaces correctly
- line highlight and canvas sync
- deep-link restoration for `lineId`/`tokenId`
- low-confidence navigation
- assist decisions audited when supported
- no hidden reasoning text surfaced

### 10. Documentation
Document:
- transcription workspace ownership
- deep-link context rules
- correction workflow and keyboard controls
- diplomatic vs normalised separation
- assist-panel guardrails
- what later work will extend for full comparison and evaluation

## Required deliverables
### Web
- full transcription workspace
- inline editor
- line crop preview
- mode switch
- save/discard/conflict handling
- deep-link restoration
- low-confidence navigation
- optional assist/normalised view integration when supported
- browser tests and visual baselines

### Backend / contracts
- only small helper or read/write refinements if strictly needed to support the canonical workspace consistently

### Docs
- transcription workspace UX contract doc
- correction, conflict, and assist-flow doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/api/**` only if a tiny helper/contract refinement is strictly needed
- `/packages/contracts/**`
- `/packages/ui/**`
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- primary inference backend
- fallback rollout
- model registry UI
- privacy features
- search/export features
- a second correction workspace
- automatic assist application

## Testing and validation
Before finishing:
1. Verify the workspace route is real and deep-link-safe.
2. Verify inline line editing works through the canonical append-only correction API.
3. Verify save/discard/conflict behavior is calm and correct.
4. Verify `Enter`, `Ctrl/Cmd+S`, and `Up/Down` keyboard behaviors work.
5. Verify line crop preview and line/canvas sync work.
6. Verify low-confidence highlighting and navigation work.
7. Verify `lineId`/`tokenId`/`sourceKind`/`sourceRefId` deep links restore context consistently.
8. Verify assist and normalised layers are accurate and auditable when supported.
9. Verify no hidden reasoning text is shown or persisted.
10. Verify visual and accessibility checks pass on the covered workspace states.
11. Verify docs match the implemented workspace behavior.
12. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the transcription workspace supports edit/save/discard/conflict-resolution with version checks and audit emission
- source pane, transcript pane, and confidence/correction controls stay synchronized to the selected run/page/line context
- deep-link review context (`runId`, `page`, optional `lineId`/`tokenId`) restores correctly after reload and back/forward navigation
- append-only correction behavior is preserved
- assist and normalised views remain controlled and auditable
- the workspace enforces bounded layout regions and keyboard navigation/focus behavior validated by interaction tests
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed phase files before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first on each run.

## Mandatory first actions
1. Inspect the relevant repository areas and any existing implementation this prompt may extend.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-01-ingest-document-viewer-v1.md`
3. Then review the current repository generally — viewer routes, ingest/detail routes, page/image APIs, processing-run APIs if present, shell/layout code, shared UI primitives, keyboard tests, visual-regression harnesses, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second viewer shell, a second ingest-status surface, or conflicting viewer-state choreography.

## Source-of-truth hierarchy
Use this precedence order when implementing:
1. The specific `/phases` files listed in this prompt for product behavior and acceptance logic.
2. `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md` when this prompt depends on web-first execution semantics.
3. `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` when this prompt depends on recall-first, rescue, token-anchor, search-anchoring, or conservative-masking semantics.
4. `/phases/blueprint-ukdataextraction.md`, `/phases/README.md`, and `/phases/ui-premium-dark-blueprint-obsidian-folio.md` as supporting product context when they are listed or clearly relevant.
5. This prompt for task scope and deliverables.
6. Current repository state for reconciling implementation details.
7. Official external docs for implementation mechanics only.

Treat current repository state as implementation context, not as the primary source of product truth.

## Conflict-resolution rule
- `/phases` wins for viewer workspace behavior, single-fold rules, keyboard shortcuts, ingest-status UX, failure-state honesty, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the calm, dense, browser-native Obsidian viewer contract. Do not regress into consumer gallery patterns, flashy animation, or chaotic page-height growth.

## Objective
Polish the viewer UX with skeletons, failure recovery, shortcuts, and dense but clear workspace behavior.

This prompt owns:
- the viewer polish pass across loading, ready, not-ready, and failure states
- a dedicated ingest-status route and timeline surface
- role-aware recovery affordances from detail/viewer/ingest-status surfaces
- adaptive workspace choreography across `Expanded | Balanced | Compact | Focus`
- remembered panel widths and sensible collapse order where supported
- keyboard shortcut clarity and discoverability
- focus-safe route transitions and overlay behavior
- consistent handoff between document detail, ingest status, and viewer

This prompt does not own:
- resumable upload backend mechanics
- retry-extraction backend lineage if it does not yet exist
- cross-browser performance-gate rollout
- annotation or later review overlays
- raw original delivery

## Phase alignment you must preserve
From Phase 1 Iteration 1.3 and 1.4:

### Required routes
- `/projects/:projectId/documents/:documentId`
- `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`
- `/projects/:projectId/documents/:documentId/ingest-status`

### Required viewer workspace contract
- top toolbar
- left filmstrip
- center canvas as the priority surface
- right inspector drawer or narrow-window flyout/drawer fallback
- single-fold bounded layout
- adaptive state model: `Expanded | Balanced | Compact | Focus`
- filmstrip collapses before canvas reduction
- panels retain resize constraints, snap points, and remembered widths where supported

### Required keyboard support
- left/right arrows: page navigation when canvas or filmstrip owns focus
- toolbar keeps its own roving-focus model
- `+` / `-`: zoom
- `R`: rotate

Do not invent a giant shortcut matrix.
If you add discoverability affordances, they must stay small, exact, and non-distracting.

### Required processing-status route behavior
- document processing timeline component reads append-only scan, extraction, and thumbnail attempts from the processing-runs path when available
- active attempts poll the run status endpoint instead of repeatedly reloading the entire run detail payload
- failure and canceled branches preserve the last reached stage instead of implying later stages succeeded
- retry affordances appear only for allowed roles and only when the current repo exposes a consistent retry path

### Required UX tone
- dark
- minimal
- dense but clear
- operational
- exact
- no AI-assistant chrome
- no giant empty animation panels
- no page-level vertical sprawl by default

## Implementation scope

### 1. Dedicated ingest-status route
Implement or refine:
- `/web/app/(authenticated)/projects/[projectId]/documents/[documentId]/ingest-status/page.tsx`

Requirements:
- fits the canonical project shell
- uses the shared page-header and state language
- has a calm, dense processing timeline
- shows current document ingest state accurately
- shows scan / extraction / thumbnail attempts from the canonical processing-runs source where present
- supports loading, active, failed, canceled, and completed branches
- does not fake stages that are not yet real in the repo

### 2. Processing timeline component
Build or refine one canonical processing timeline component for document ingest.

Requirements:
- append-only visual model
- stage ordering is explicit
- active states poll the status endpoint rather than the full detail payload
- failure and canceled branches stop at the last true stage
- can be reused on both document detail and ingest-status surfaces where useful
- no “happy-path-only” timeline

### 3. Viewer loading and skeleton choreography
Upgrade the viewer's state handling.

Requirements:
- shell structure stays visible while data loads
- toolbar / filmstrip / canvas / inspector skeletons are consistent
- not-ready state is explicit when page assets or metadata are still pending
- failed state is safe and actionable
- unauthorized or expired-session asset behavior does not collapse into unexplained broken-image chaos
- state changes remain bounded and do not trigger full-page layout shifts

### 4. Failure recovery UX
Refine recovery behavior across detail, ingest-status, and viewer.

Requirements:
- clear distinction between:
  - still processing
  - failed extraction
  - canceled extraction
  - missing page
  - unauthorized access
  - session expiry
- safe next-step CTAs, such as:
  - `View ingest status`
  - `Open document`
  - `Back to documents`
  - `Retry extraction` only when the role and backend support it
- no vague “something went wrong” messaging when the system knows more
- no false implication that the viewer is ready when it is not

### 5. Workspace choreography and adaptive states
Polish the viewer workspace behavior.

Requirements:
- `Expanded`: filmstrip + canvas + inspector
- `Balanced`: narrower filmstrip and compressed inspector
- `Compact`: inspector becomes drawer/flyout; filmstrip compresses
- `Focus`: canvas dominates; secondary panels are on-demand
- panel widths are bounded and sensible
- remembered widths/snap points are supported where they fit the current repo and remain consistent
- transitions respect reduced-motion and, where supported, reduced-transparency preferences
- sticky chrome does not obscure focus or content unexpectedly

### 6. Keyboard shortcuts and discoverability
Refine keyboard use without adding clutter.

Requirements:
- existing shortcuts remain stable:
  - left/right arrows
  - `+`
  - `-`
  - `R`
- shortcut behavior is context-aware
- toolbar shortcuts do not fight toolbar roving focus
- add subtle discoverability only if it fits cleanly:
  - a help hint
  - a compact shortcuts section in viewer help/overflow
  - a small internal cheatsheet surface
- do not add a giant command-sheet or modal unless it stays small and calm

### 7. Filmstrip and inspector polish
Refine the side regions.

Requirements:
- filmstrip current-page highlight is stronger and clearer
- thumbnail loading/failure states are clear
- bounded filmstrip scrolling remains intact
- inspector shows page metadata and status clearly
- narrow-window fallback remains consistent
- no region forces overall page-height growth

### 8. Route handoff and continuity
Make the viewer/document/ingest-status flow feel seamless.

Requirements:
- document detail links into viewer and ingest-status cleanly
- ingest-status links back into detail and viewer while preserving `projectId`, `documentId`, and current page context where available
- route transitions preserve shell continuity
- focus lands in sensible places after navigation
- URL state remains the canonical owner of viewer route context where already defined

### 9. Minimal backend alignment only if strictly needed
This is primarily a UX prompt.
You may add only the smallest backend/API alignment needed to support:
- the ingest-status route
- run status polling
- safe retry affordance visibility
- consistent document-state mapping

Do not turn this into a full retry-lineage or resumable-upload backend prompt unless the current repo truly cannot support the UX without a small helper.

### 10. Documentation
Document:
- ingest-status route ownership
- viewer state and failure-state choreography
- adaptive viewer panel behavior
- supported shortcuts
- what recovery actions appear under which conditions
- what later work still owns for backend hardening

## Required deliverables

### Web
- `/projects/:projectId/documents/:documentId/ingest-status`
- viewer skeleton / error / not-ready / recovery states
- timeline component
- shortcut discoverability refinement
- adaptive panel choreography refinements

### Backend / contracts
- only small helper/status alignment changes if strictly required
- tests

### Docs
- ingest-status and viewer-failure-recovery doc
- viewer shortcut and workspace-choreography doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/api/**` only for small helper/status endpoints or contract alignment strictly needed by the UX
- `/packages/contracts/**`
- `/packages/ui/**` only for small timeline/viewer-state/inspector/toolbar refinements
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- resumable upload backend
- extraction retry lineage backend unless a small helper is unavoidable
- annotation features
- compare mode deepening
- raw original delivery
- broad cross-browser performance rollout
- a second viewer shell

## Testing and validation
Before finishing:
1. Verify the ingest-status route is real and consistent.
2. Verify loading, ready, not-ready, failed, and canceled states are distinct and clear.
3. Verify active timeline polling uses the run-status path instead of full-detail reload spam.
4. Verify keyboard shortcuts work only in the intended focus contexts.
5. Verify focus remains visible and not obscured during route and panel transitions.
6. Verify adaptive-state panel behavior remains bounded and usable.
7. Verify retry affordances are role-aware and only shown when supported.
8. Verify dark/light/high-contrast and reduced-motion behavior are not broken.
9. Verify docs match the actual route and viewer recovery behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- viewer loading/network-failure states include in-place recovery actions and avoid blank-canvas dead ends
- ingest-status is a real first-class route
- shortcuts are stable and discoverable without clutter
- recovery states are clear and actionable
- the bounded single-fold workspace contract is preserved
- viewer and ingest-status surfaces use shared shell primitives and consistent state components across recovery paths
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

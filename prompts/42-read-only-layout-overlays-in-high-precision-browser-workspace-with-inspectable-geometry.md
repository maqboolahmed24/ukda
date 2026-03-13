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
   - `/phases/phase-03-layout-segmentation-overlays-v1.md`
3. Then review the current repository generally — layout workspace routes, overlay contracts, page/image APIs, shared UI primitives, toolbar/drawer primitives, browser regression harnesses, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second overlay workspace, a second geometry-rendering path, or conflicting inspector behavior.

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
- `/phases` wins for workspace ownership, overlay toggle semantics, inspector content, adaptive-state behavior, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that this workspace is a professional read-only inspection surface, not an editing canvas and not a general document viewer replacement.

## Objective
Render read-only layout overlays in a high-precision browser workspace with inspectable geometry.

This prompt owns:
- the read-only segmentation workspace behavior
- overlay layer rendering over authenticated page images
- overlay toggles for regions, lines, baselines, and reading-order arrows when available
- overlay opacity control
- region/line inspection flows with canvas and inspector sync
- run switching in the workspace
- high-precision, bounded, keyboard-safe browser interaction
- visual/accessibility regression for overlay states

This prompt does not own:
- manual correction tools
- reading-order editing
- stable crop/context artefact generation
- recall-first rescue-candidate generation
- transcription features
- a second compare or viewer shell

## Phase alignment you must preserve
From Phase 3 Iteration 3.2:

### Required workspace capabilities
- top toolbar:
  - run selector
  - overlay toggles:
    - regions
    - lines
    - baselines (if present)
    - reading order arrows (if present)
  - overlay opacity control
  - `Open triage`
- left filmstrip (collapsible)
- center canvas with image and overlay layers
- right inspector:
  - page metrics
  - warning chips
  - region tree
  - line list filtered by selected region

### Required interaction model
- hover highlights elements
- click selects and pins highlight
- inspector list selection highlights on canvas
- switching run refreshes overlay payloads, legend values, and inspector summaries from the selected run without stale data
- no editing in this prompt
- no page-level vertical sprawl in default shell states

### Required quality gates
- toggle overlays on and off
- select region and confirm inspector sync
- switch run and confirm overlay refresh
- toolbar keyboard operable
- drawer open/close focus management works
- focus remains visible and unobscured
- overlay on/off snapshots
- inspector open/closed snapshots
- zoom-state snapshots

## Implementation scope

### 1. Canonical read-only layout workspace
Implement or refine:
- `/projects/:projectId/documents/:documentId/layout/workspace?page={pageNumber}&runId={runId}`

Requirements:
- use the canonical project/document shell
- bounded single-fold workspace
- layout-specific toolbar, filmstrip, center canvas, right inspector
- no second shell
- dark, minimal, dense, and operational tone
- calm loading/error/not-ready states when overlay data is absent

### 2. Overlay layer rendering
Implement or refine high-precision overlay rendering on top of the page image.

Requirements:
- consume the canonical overlay JSON contract
- render region polygons
- render line geometry
- render baselines when present
- render reading-order arrows when present
- do not invent a second geometry schema
- geometry rendering remains performant and bounded
- selection and highlight states remain crisp on dark surfaces

### 3. Toolbar controls
Implement or refine the layout workspace toolbar.

Requirements:
- run selector
- overlay toggles
- overlay opacity control
- `Open triage`
- toolbar keyboard behavior follows the canonical toolbar model
- stateful pressed/selected/disabled behavior is clear
- toggles do not trigger layout instability or shell teardown

### 4. Filmstrip behavior
Implement or refine the left filmstrip for layout review.

Requirements:
- collapsible
- current-page highlight
- keyboard-safe focus behavior
- bounded internal scrolling only
- run switching and page switching stay consistent
- no vertical shell blowout

### 5. Inspector behavior
Implement or refine the right inspector.

Requirements:
- page metrics
- warning chips
- region tree
- line list filtered by selected region
- region/line selection sync with canvas highlight
- narrow-window fallback remains consistent
- bounded internal scrolling
- no edit affordances in this prompt

### 6. Interaction model
Implement the required read-only interactions.

Requirements:
- hover highlights
- click selects and pins highlight
- inspector selection highlights the corresponding element on canvas
- clear deselect behavior
- overlay selection does not fight page navigation
- no accidental edit mode
- focus remains visible during pointer and keyboard interaction

### 7. Run switching
Implement or refine run switching inside the workspace.

Requirements:
- run selector is explicit and typed
- switching run refreshes overlay payloads, legend values, and inspector summaries from the selected run without stale data
- active/default run behavior remains consistent with the canonical layout projection rules
- stale or missing overlay data is surfaced explicitly
- no “latest successful” guessing

### 8. Accessibility and adaptive states
Harden the workspace behavior.

Requirements:
- toolbar keyboard operable
- no keyboard traps
- focus remains visible and unobscured
- reduced-motion and reduced-transparency preferences are respected
- `Expanded | Balanced | Compact | Focus` remain consistent
- side rails and inspector compress before center-canvas clarity is compromised
- reflow and zoom use controlled scrolling instead of clipping

### 9. Visual and browser regression
Add or refine browser-level coverage.

At minimum cover:
- overlay on
- overlay off
- inspector open
- inspector closed
- run switch
- zoom-state snapshots where the repo already supports them
- keyboard and Axe coverage on the workspace route

### 10. Documentation
Document:
- workspace ownership
- overlay toggle semantics
- run selector behavior
- inspector/canvas sync rules
- what later artifact and recall-first work deepens next
- what this prompt intentionally does not allow (editing)

## Required deliverables

### Web
- read-only layout workspace refinement
- overlay rendering
- toolbar toggles and opacity control
- inspector with region tree and filtered line list
- run selector and `Open triage` flow
- browser tests and visual baselines

### Backend / contracts
- only small helper or contract refinements if strictly needed to support the canonical overlay path cleanly

### Docs
- read-only layout workspace contract doc
- overlay interaction and inspector sync doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/api/**` only if a small helper/contract refinement is strictly needed
- `/packages/contracts/**`
- `/packages/ui/**` only if small workspace-toolbar/inspector/overlay primitives are needed
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- edit mode
- manual correction tools
- reading-order editing
- crop/context-window generation
- recall/rescue tooling
- transcription tools
- a second overlay workspace

## Testing and validation
Before finishing:
1. Verify overlays can be toggled on and off.
2. Verify selecting a region updates the inspector and canvas highlight to the same region ID and geometry.
3. Verify switching runs refreshes overlays correctly.
4. Verify the toolbar is keyboard operable.
5. Verify drawer/inspector open-close focus management works.
6. Verify focus remains visible and unobscured.
7. Verify the workspace remains bounded and single-fold by default.
8. Verify visual regression baselines exist for overlay on/off and inspector open/closed.
9. Verify Axe or equivalent accessibility scans pass on the workspace route.
10. Verify docs match the actual workspace and overlay behavior.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the read-only overlay workspace route renders canvas and inspector from canonical overlay payloads
- overlays render with precise inspectable geometry
- selecting a region/line in canvas updates inspector selection, and inspector selection highlights the same canvas entity
- run switching is consistent
- keyboard navigation/focus behavior and bounded scroll-region layout are validated across supported viewport sizes
- canonical overlay payloads expose downstream-required fields (`run_id`, `page_id`, `region_id`, `line_id`, geometry) without introducing additional workspace routes
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

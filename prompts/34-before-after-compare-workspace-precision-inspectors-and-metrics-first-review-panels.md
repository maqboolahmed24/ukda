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
   - `/phases/phase-01-ingest-document-viewer-v1.md`
   - `/phases/phase-02-preprocessing-pipeline-v1.md`
3. Then review the current repository generally — viewer routes, preprocessing routes, page/image APIs, typed contracts, shell/layout code, shared UI primitives, browser tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second compare surface, a second variant-delivery path, or conflicting inspector behavior.

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
- `/phases` wins for viewer compare-mode behavior, compare-route ownership, toolbar semantics, metrics-inspector ownership, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that `/preprocessing/compare` is the canonical diagnostics surface, while viewer `Compare` mode is the in-context reading aid.

## Objective
Create the before/after compare workspace with precision inspectors and metrics-first review panels.

This prompt owns:
- viewer compare mode
- toolbar mode selector
- preprocess run selector for viewer modes
- canonical compare workspace route
- metrics-first inspector for per-page quality review
- authenticated variant selection and delivery
- deep links from viewer into preprocessing diagnostics
- compare-focused keyboard and focus behavior

This prompt does not own:
- selective rerun workflows
- full run-delta triage tables
- aggressive advanced profiles
- layout/transcription/privacy features
- a second diagnostics shell outside the canonical preprocessing route family

## Phase alignment you must preserve
From Phase 2 Iteration 2.2:

### Iteration Objective
Let review users validate preprocessing impact directly in the viewer.

### Viewer workspace enhancements
- compare workspace keeps the inherited single-fold state model
- side rails and inspector compress before center-canvas functionality is reduced
- toolbar mode selector:
  - `Original`
  - `Preprocessed`
  - `Compare`
- run selector for `Preprocessed` / `Compare` modes
- existing controls remain:
  - zoom
  - fit
  - rotate
- compare rendering:
  - side-by-side split (v1)
- right inspector drawer (collapsible):
  - page metrics
  - warning chips
  - deep link to quality table
  - deep link to canonical `/preprocessing/compare` route for full run diagnostics

### Backend work
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}/variants?runId={runId}`
  - returns available variants for the selected run
  - when `runId` is omitted, the document's explicitly activated preprocess run is used
  - the request fails if no active preprocess run exists
- authenticated stream support for:
  - original image
  - preprocessed grayscale image
- variant reads emit `PREPROCESS_VARIANT_ACCESSED`

### Required gates
- switch to `Preprocessed` and verify image changes
- switch to `Compare` and verify both variants render
- open inspector and verify metrics display
- keyboard toolbar navigation is predictable
- Axe scan passes on viewer route
- no keyboard traps
- focus is visible in toolbar and drawer flows
- reflow/zoom scenarios use controlled scrolling instead of clipping
- visual regression snapshots for Original, Preprocessed, Compare, inspector open/closed

## Implementation scope

### 1. Viewer mode selector
Implement or refine the viewer mode selector inside the canonical toolbar.

Requirements:
- modes:
  - `Original`
  - `Preprocessed`
  - `Compare`
- mode changes are exact and predictable
- toolbar semantics remain ARIA-safe
- mode switching does not cause shell teardown
- current mode is visible and keyboard-reachable
- no second toolbar system

### 2. Run selector
Implement or refine the preprocess run selector.

Requirements:
- available in `Preprocessed` and `Compare` modes
- only shows runs the caller may access
- defaults to the active preprocess run when a run is not explicitly selected
- if no active preprocess run exists and no run is selected, the UI fails explicitly and safely
- integrates cleanly with typed contracts and canonical data layer
- does not leak cross-document or cross-project runs

### 3. Variant availability and delivery
Implement or refine:
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}/variants?runId={runId}`

Requirements:
- returns variant availability for the selected run
- original and preprocessed grayscale variants are supported
- if `runId` is omitted, active preprocess projection is used
- fail closed if no active preprocess run exists
- typed response contract
- authenticated asset delivery remains canonical and same-origin or equivalent internal path
- no raw storage keys or public URLs leak

### 4. Compare rendering
Implement or refine the compare workspace.

Requirements:
- side-by-side split view for v1
- clear original vs preprocessed orientation
- bounded single-fold workspace
- no vertical page sprawl
- compare mode remains calm and dense
- center comparison surfaces stay the visual priority
- side rails and inspector compress before compare content is compromised

### 5. Metrics-first inspector
Implement or refine the right inspector drawer.

Requirements:
- collapsible
- page metrics
- warning chips
- exact current run context
- deep link to quality table
- deep link to canonical `/preprocessing/compare` route
- narrow-window drawer or flyout fallback
- keyboard-safe open/close/focus behavior
- does not crowd the main compare surface

### 6. Canonical compare route
Implement or refine:
- `/projects/:projectId/documents/:documentId/preprocessing/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`

Requirements:
- remains the canonical diagnostics surface
- can open from the viewer with preserved context
- bounded compare workspace shell
- safe empty/not-ready/no-run-selected states
- does not try to swallow the entire viewer or preprocessing information architecture
- if only one preprocess run is available, the compare surface uses a single-run state rather than inventing fake alternate baselines

Use the exact query names from the phase contract.
Do not invent a conflicting route or alternate compare state model.

### 7. Viewer and compare deep-link choreography
Make the compare flow seamless.

Requirements:
- viewer `Compare` mode can deep-link into `/preprocessing/compare`
- compare route can route back into the viewer without losing consistent page context
- URL state stays small and exact
- breadcrumbs remain orientation-only
- focus lands sensibly after navigation

### 8. Keyboard and accessibility
Harden the compare interactions.

Requirements:
- toolbar keyboard behavior is predictable
- no keyboard traps
- focus remains visible in toolbar and inspector flows
- reflow and zoom use controlled scrolling rather than clipping
- reduced-motion and, where supported, reduced-transparency preferences are respected
- dark/light/high-contrast behavior stays consistent

### 9. Audit and telemetry alignment
Use the existing canonical paths.

Requirements:
- variant reads emit `PREPROCESS_VARIANT_ACCESSED`
- compare-view usage remains auditable through the existing system where already present
- no sensitive storage paths or secret-bearing URLs enter logs or metrics

### 10. Documentation
Document:
- compare-mode ownership in viewer vs preprocessing
- mode selector and run selector behavior
- variant availability contract
- compare inspector ownership
- deep-link rules between viewer and preprocessing compare

## Required deliverables

### Backend / contracts
- variant availability endpoint
- typed variant contracts
- any small authenticated variant-delivery refinements needed for compare
- tests

### Web
- viewer mode selector
- preprocess run selector
- compare split workspace
- metrics-first inspector
- canonical `/preprocessing/compare` route refinement
- deep-link choreography between viewer and compare

### Docs
- viewer compare-mode and compare-route ownership doc
- variant and metrics-inspector contract doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/api/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small compare-toolbar/inspector/viewer-shell refinements are needed
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- selective rerun UX
- run-delta triage tables
- advanced binarization profiles
- later review overlays
- public asset URLs
- raw original delivery
- a second compare shell

## Testing and validation
Before finishing:
1. Verify switching to `Preprocessed` changes the rendered image.
2. Verify switching to `Compare` renders both variants.
3. Verify the inspector displays metrics and warning chips.
4. Verify keyboard toolbar navigation is predictable.
5. Verify Axe scan passes on the viewer route.
6. Verify there are no keyboard traps.
7. Verify focus remains visible in toolbar and drawer flows.
8. Verify reflow/zoom scenarios use controlled scrolling.
9. Verify visual regression baselines exist for Original, Preprocessed, Compare, and inspector open/closed states.
10. Verify docs match the actual compare-mode and compare-route behavior.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- viewer compare mode is real
- variant selection and rendering are real
- the inspector prioritizes defined metric panels (deltas, warnings, artefact status) and binds them to the selected run/page context
- `/preprocessing/compare` remains the canonical diagnostics surface
- the compare workspace stays bounded, calm, and keyboard-safe
- the implementation preserves controlled authenticated asset delivery
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

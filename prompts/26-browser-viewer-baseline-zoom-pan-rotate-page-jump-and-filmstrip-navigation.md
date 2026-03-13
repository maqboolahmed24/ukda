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
3. Then review the current repository generally — viewer routes, page/image APIs, page metadata contracts, shell/layout code, shared UI primitives, keyboard tests, visual-regression setup, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second viewer shell, a second image-navigation model, or conflicting viewer state ownership.

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
- `/phases` wins for viewer route ownership, workspace layout, keyboard behavior, single-fold shell rules, page navigation semantics, and acceptance logic.
- Official docs win only for implementation mechanics.
- Keep the viewer serious, dense, and browser-native. Do not turn it into a consumer image gallery or a fake desktop app.

## Objective
Create the browser viewer baseline with zoom, pan, rotate, page jump, and filmstrip navigation.

This prompt owns:
- the real Phase 1 viewer baseline
- toolbar-driven zoom/pan/rotate controls
- page-to-page navigation
- filmstrip navigation
- page jump behavior
- minimal inspector integration
- persisted per-page rotation via the canonical page API
- keyboard and mouse interaction for the viewer
- accurate loading/not-ready/error states

This prompt does not own:
- deep-linkable multi-param viewer state beyond what already exists in the page query
- shareable review context restoration
- advanced compare modes
- annotation or overlay tooling
- later-phase review UX
- raw original download

## Phase alignment you must preserve
From Phase 1 Iteration 1.3:

### Required routes
- `/projects/:projectId/documents/:documentId`
- `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`

### Required viewer workspace layout
The viewer workspace inherits the Pattern D single-fold contract and adaptive states:
- top toolbar: zoom, fit width, rotate, previous/next page
- left rail: thumbnail filmstrip
- center canvas: page image as the priority surface
- right inspector drawer (v1 optional): page metadata/status

Rules:
- state transitions are driven by available browser-window size and task context, not device labels
- vertical scrolling remains bounded to high-density regions such as the filmstrip
- the full page must not sprawl vertically in default conditions

### Required keyboard support
- left/right arrows: page navigation when canvas or filmstrip owns focus
- toolbar retains its own roving-focus behavior
- `+` / `-`: zoom
- `R`: rotate

### Required quality gates
- open viewer workspace
- navigate with thumbnails
- zoom/rotate/page nav work via mouse and keyboard
- visual regression for loading, ready, and error states
- reduced-motion and, where supported, reduced-transparency behavior are respected alongside reflow-safe behavior

### Required security posture
- page images are viewed through the controlled authenticated page/image path
- no raw original download endpoint

## Implementation scope

### 1. Real viewer workspace
Implement or refine:
- `/web/app/(authenticated)/projects/[projectId]/documents/[documentId]/viewer/page.tsx`

Requirements:
- uses the canonical project shell
- occupies a bounded single-fold workspace
- has a top toolbar
- has a left thumbnail filmstrip
- has a center canvas
- has a right metadata/status inspector or drawer path
- uses the shared design system and shell primitives
- remains dark, minimal, dense, and serious

Do not let the viewer degrade into a long vertically scrolling page.

### 2. Toolbar controls
Implement or refine a real viewer toolbar.

Requirements:
- previous page
- next page
- zoom in
- zoom out
- fit width
- rotate
- page jump control
- accessible labels and keyboard behavior
- toolbar roving-focus behavior
- stateful disabled behavior at boundaries

Do not create a second toolbar system; use the canonical primitive layer.

### 3. Page navigation
Implement clear page navigation behavior.

Requirements:
- previous/next page controls
- filmstrip click/select navigation
- keyboard left/right navigation when canvas or filmstrip owns focus
- page jump field or page selector
- browser-facing `page` query remains 1-based
- safe normalization when the query is missing or invalid
- current page highlight is clear in both filmstrip and page indicator

### 4. Zoom and pan baseline
Implement the viewer's alive-path zoom and pan behavior.

Requirements:
- zoom in/out
- fit width
- bounded pan behavior for zoomed content
- no chaotic scroll/drag conflicts
- reduced-motion-safe transitions
- zoom state is clear to the user
- canvas remains the visual priority surface

This is the baseline, not the final viewer polish. Keep it reliable and controlled rather than flashy.

### 5. Rotation
Implement rotation as a real persisted viewer property.

Requirements:
- `R` keyboard shortcut
- rotate control in toolbar
- use the canonical `PATCH /projects/{projectId}/documents/{documentId}/pages/{pageId}` path or an equivalent repo path
- rotation is reflected when the page is reopened
- rotation does not mutate raw originals
- failure handling is safe and exact

### 6. Filmstrip
Implement or refine the thumbnail filmstrip.

Requirements:
- uses authenticated thumbnail delivery
- clear current-page highlight
- keyboard-safe focus behavior
- bounded scrolling only inside the filmstrip region
- collapsible or compacting behavior in narrower states
- no full-page height expansion
- loading and failure states are clear

### 7. Inspector
Implement or refine a minimal inspector.

Requirements:
- page metadata
- page status
- safe failure or not-ready information
- narrow-window drawer/flyout fallback
- does not crowd the main canvas
- no speculative later-phase review controls

### 8. Loading, ready, not-ready, and error states
Use the shared state language.

Requirements:
- loading state preserves viewer shell structure
- ready state is calm and exact
- not-ready state is clear if page assets are still pending
- failure state is safe and actionable
- missing-page and invalid-page query states degrade safely

### 9. Data integration
Use the canonical page APIs and typed contracts.

Requirements:
- page list drives filmstrip
- page metadata endpoint drives inspector details
- page image endpoint drives the canvas
- no route-local ad hoc API drift
- page status is not inferred only from image success/failure

### 10. Documentation
Document:
- viewer route ownership
- toolbar behavior
- page navigation rules
- zoom/pan/rotate baseline
- filmstrip and inspector ownership
- what later viewer URL-state work should add around shareable URLs and restoration

## Required deliverables

### Web
- real viewer workspace
- toolbar
- filmstrip
- canvas
- inspector or drawer
- page-jump control
- keyboard and mouse navigation
- persisted rotation wiring

### Backend / contracts
- any small page-metadata or rotation-alignment refinements needed to keep the viewer consistent
- tests

### Docs
- viewer baseline contract doc
- page navigation and control rules doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/api/**` only if small page/rotation contract refinements are required
- `/packages/contracts/**`
- `/packages/ui/**` only if small viewer toolbar/filmstrip/canvas/inspector primitives are needed
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- full compare mode
- annotation tools
- later-phase overlays
- raw original delivery
- shareable viewer-state URLs beyond the current page query unless necessary for coherence
- flashy image-gallery behavior

## Testing and validation
Before finishing:
1. Verify the viewer workspace opens correctly.
2. Verify thumbnail navigation works.
3. Verify previous/next and page jump work.
4. Verify `+` / `-` and toolbar zoom controls work.
5. Verify `R` and rotate control persist rotation correctly.
6. Verify left/right arrows navigate pages only in the intended focus contexts.
7. Verify loading, ready, not-ready, and error states render accurately.
8. Verify bounded work-region layout is preserved.
9. Verify no raw original path was introduced.
10. Verify docs match the implemented controls and state rules.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the viewer is a real workspace, not a placeholder
- zoom, pan, rotate, page jump, and filmstrip navigation are real
- keyboard and mouse interaction both work
- viewer shell maintains bounded layout regions with no uncontrolled page-level overflow at supported viewport sizes
- persisted page rotation is real
- the viewer stays aligned with controlled authenticated asset delivery
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

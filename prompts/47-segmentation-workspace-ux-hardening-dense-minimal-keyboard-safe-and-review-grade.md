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
3. Then review the current repository generally — layout workspace routes, shell/layout code, toolbar/menu/drawer primitives, edit-mode flows, reading-order tab, browser tests, visual baselines, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second workspace shell, a second toolbar model, or conflicting interaction patterns across inspect/edit/reading-order modes.

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
- `/phases` wins for bounded single-fold workspace behavior, dense review-grade UX, keyboard/focus rules, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the segmentation workspace as a calm, minimal, expert tool. Do not let it become a cluttered editor, fake desktop, or noisy admin console.

## Objective
Lock the segmentation workspace UX so it is dense, minimal, keyboard-safe, and review-grade on the web.

This prompt owns:
- the segmentation workspace UX hardening pass
- consistent mode choreography across inspect, reading-order, and edit states
- conflict/unsaved-change UX
- adaptive pane behavior and remembered widths
- exact toolbar hierarchy and overflow strategy
- high-density inspector/list ergonomics
- focus, keyboard, and reduced-motion polish
- visual regression and accessibility hardening for the complete workspace

This prompt does not own:
- new layout algorithms
- new backend schemas
- new edit operations
- transcription feature work
- a second shell or alternate layout-analysis UI

## Phase alignment you must preserve
From Phase 3 workspace rules and the Obsidian blueprint:

### Canonical workspace structure
- top toolbar
- left filmstrip
- center canvas
- right inspector
- single-fold bounded work region
- adaptive states:
  - `Expanded`
  - `Balanced`
  - `Compact`
  - `Focus`

### Existing layout workspace behaviors to preserve
- run selector
- overlay toggles
- overlay opacity
- `Open triage`
- read-only inspection
- edit mode
- reading-order tab
- no page-level vertical sprawl by default

### Existing interaction rules to preserve
- toolbar keyboard operable
- no keyboard traps
- focus visible and unobscured
- drawer open/close focus management works
- hover/select interactions remain precise
- inspector/canvas sync remains consistent

### Quality-gate intent
- overlay on/off states
- inspector open/closed
- zoom-state snapshots
- edit-mode states
- conflict and save/discard states
- accessibility and keyboard regression on main workspace flows

## Implementation scope

### 1. Canonical workspace mode choreography
Refine the workspace so inspect, reading-order, and edit states feel like one product.

Requirements:
- inspect mode default
- reading-order tools feel like a focused inspector extension, not a separate app
- edit mode is explicit and visually distinct
- transitions between modes are exact and predictable
- unsaved changes are surfaced clearly but quietly
- mode switching does not collapse shell continuity

### 2. Toolbar hierarchy and overflow
Lock the workspace toolbar hierarchy.

Requirements:
- primary actions are obvious
- low-frequency tools move into labeled overflow
- toggles, run selector, opacity control, save/discard, and `Open triage` remain consistent
- toolbar remains keyboard-safe
- no giant ribbon UI
- no crowding at medium widths

### 3. Pane sizing and adaptive-state hardening
Refine pane behavior.

Requirements:
- filmstrip, canvas, and inspector obey sane min/max widths
- side rails compress before center-canvas clarity is compromised
- inspector becomes a drawer or flyout in narrower states
- remembered widths or snap points are supported where they fit the repository and remain consistent
- the shell never degrades into chaotic full-page scroll

### 4. Inspector information design
Make the inspector dense and usable.

Requirements:
- tabs or sections remain clear
- region tree, line lists, metrics, warnings, reading order, and edit properties stay legible
- no giant accordion jungle
- loading/error/not-ready states are calm and exact
- bounded internal scrolling only
- selected object state is always obvious

### 5. Unsaved changes and conflict UX
Harden save/discard flows.

Requirements:
- unsaved changes indicator
- exact save/discard affordances
- optimistic-lock conflict banner or surface that is calm and actionable
- route leave warning only where it is truly justified
- refresh/reload conflict recovery path is understandable
- no theatrical warning modals

### 6. Keyboard and shortcut polish
Refine the workspace interaction model.

Requirements:
- toolbar navigation remains canonical
- overlay/edit/reading-order controls remain reachable by keyboard
- no keyboard traps
- focus remains visible in dark, light, and high-contrast modes
- reduced-motion and reduced-transparency preferences are respected
- any shortcuts added must be few, exact, and discoverable without clutter

### 7. Filmstrip and canvas polish
Harden the high-frequency regions.

Requirements:
- current-page highlight is strong and quiet
- canvas remains visually dominant
- selection/highlight styling is crisp
- zoom-state and overlay-state changes do not cause layout instability
- no hidden focus or clipped controls in compact states

### 8. Visual and accessibility gates
Expand the browser regression and accessibility coverage for the fully integrated workspace.

At minimum cover:
- inspect mode
- overlay on/off
- reading-order tab
- edit mode
- unsaved changes state
- conflict state
- inspector open/closed
- compact/focus layouts where stable
- Axe and keyboard flows on main paths

### 9. Documentation
Document:
- canonical workspace mode model
- toolbar hierarchy
- pane sizing/adaptive rules
- save/discard/conflict UX rules
- what later work must preserve when adding more layout or transcription interactions

## Required deliverables
### Web
- workspace UX hardening across inspect/edit/reading-order
- pane sizing and adaptive refinements
- conflict/unsaved-change UX
- visual and accessibility regression coverage

### Docs
- segmentation workspace UX contract doc
- workspace save/discard/conflict behavior doc
- any README updates required for developer usage


## Allowed touch points
You may modify:
- `/web/**`
- `/packages/ui/**`
- `/packages/contracts/**` only if small mode/state enums help consistency
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- new segmentation algorithms
- new layout-edit backend features
- transcription tooling
- a second workspace shell
- flashy visual redesign
- cluttered enterprise-editor aesthetics

## Testing and validation
Before finishing:
1. Verify inspect, reading-order, and edit modes feel consistent and do not fight each other.
2. Verify toolbar hierarchy remains usable across widths.
3. Verify pane sizing and adaptive states stay bounded and stable.
4. Verify unsaved-change and conflict UX are exact and calm.
5. Verify keyboard and focus behavior remain strong.
6. Verify reduced-motion and high-contrast behavior are not broken.
7. Verify visual baselines exist for key workspace states.
8. Verify accessibility checks pass on the covered workspace flows.
9. Verify docs match the implemented workspace UX contract.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the segmentation workspace enforces single-fold layout bounds, deterministic mode switching, and keyboard traversal rules
- mode choreography is consistent
- pane behavior is bounded and stable
- conflict and save/discard UX prevents silent data loss and shows deterministic outcomes for save, discard, and cancel
- keyboard and accessibility behavior are strong
- later work can extend the workspace without reworking the UX
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

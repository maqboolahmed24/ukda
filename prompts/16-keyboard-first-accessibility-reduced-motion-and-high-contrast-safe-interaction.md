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
   - `/phases/phase-01-ingest-document-viewer-v1.md` for keyboard, focus, toolbar, dialog, drawer, and shell quality gates
   - `/phases/phase-11-hardening-scale-pentest-readiness.md` for hardening-level expectations around safe user messaging and production-grade readiness
3. Then review the current repository generally — shell code, primitives, themes, focus handling, keyboard shortcuts, overlays, tests, gallery, and current routes — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second accessibility layer or leave accessibility behavior fragmented across feature folders.

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
- `/phases` wins for keyboard-first posture, focus visibility, focus-not-obscured guarantees, reduced-motion and reduced-transparency behavior where supported, shell interaction rules, and acceptance logic.
- Official docs win only for accessibility semantics and browser implementation details.
- Do not let aesthetic convenience weaken focus, reflow, or keyboard reliability.

## Objective
Implement keyboard-first accessibility, reduced-motion handling, and high-contrast-safe interaction across the shell.

This prompt owns:
- shell-wide keyboard accessibility hardening
- focus management and focus visibility guarantees
- reduced-motion and reduced-transparency behavior where supported
- high-contrast / forced-colors safety
- overlay accessibility hardening
- toolbar/nav/command interaction hardening
- accessibility regression tests and diagnostics
- documentation of the canonical interaction and accessibility contract

This prompt does not own:
- a visual redesign
- full screen-reader copywriting overhaul beyond what is needed for accessible names and announcements
- feature-specific workflows for later phases
- a second shortcut system
- decorative motion or animation systems

## Phase alignment you must preserve
From the Obsidian blueprint, Phase 0, and Phase 1:

### Accessibility contract
- keyboard-only path verification is required
- no keyboard traps
- focus visible and not obscured
- shell, nav, dialogs, drawers, flyouts, and toolbars must all remain keyboard-safe
- sticky headers, drawers, and flyouts must never fully obscure the current focus target
- shortcuts must be stable and discoverable per workspace
- reduced-motion preferences are respected automatically, and reduced-transparency preferences are respected where supported
- dark, light, and high-contrast or forced-colors modes are all first-class and tested

### Toolbar and overlay rules
- toolbar follows the required ARIA interaction model
- modal dialog focus trap and focus return behavior must work
- overflow commands remain reachable by keyboard through labeled flyouts and non-context-menu paths

### Single-fold and reflow rule
- the single-fold principle must not break WCAG reflow, focus visibility, or keyboard usability
- when zoom, text-spacing, or assistive reflow requires it, controlled scrolling is allowed rather than clipping, overlap, or hidden focus

## Implementation scope

### 1. Accessibility audit and gap closure across current surfaces
Perform a real repo-wide accessibility hardening pass focused on the current shell and surfaces already built.

At minimum reconcile:
- authenticated shell
- nav rail
- header/user menu/project switcher
- page header actions
- dialogs
- drawers
- menus/flyouts
- toolbars
- current admin routes
- current project routes
- `/login`
- `/admin/design-system`

Do not just add comments or TODOs. Fix the real issues.

### 2. Focus management system
Implement or refine a shared focus-management baseline.

Requirements:
- strong visible focus ring across all interactive controls
- focus return on overlay close
- focus not obscured by sticky chrome or overlays
- reasonable initial focus in dialogs/drawers
- focus preservation or intentional reset on route transitions
- no disappearing focus on dark surfaces
- robust behavior in dark, light, and high-contrast modes

Where useful, centralize helpers instead of leaving every route to improvise.

### 3. Keyboard-first navigation and interaction
Harden keyboard interaction across the shell.

Requirements:
- nav rail reachable and usable by keyboard
- project switcher/menu path keyboard-safe
- toolbar roving-focus behavior correct
- overflow/menu behavior keyboard-safe
- dialogs and drawers keyboard-safe
- escape behavior predictable
- tab order logical
- optional skip-link or equivalent fast-path if it improves shell navigation
- no keyboard-only dead ends

Do not add gratuitous shortcuts.
Do make existing or necessary shortcuts stable and discoverable.

### 4. Reduced-motion and reduced-transparency behavior
Implement real support for user preference media features and explicit product behavior.

Requirements:
- reduced-motion disables non-essential transitions and motion
- where supported, reduced-transparency disables non-essential translucent effects
- overlays, drawers, menus, and route transitions respect these preferences
- the product remains visually consistent and usable when those preferences are active
- no “pretend support” where toggles or styles exist but behavior does not actually change

### 5. High-contrast and forced-colors safety
Harden the product for high-contrast scenarios.

Requirements:
- focus indicators remain visible
- borders, separators, and selected states remain discernible
- status chips/badges remain understandable
- shell chrome and overlays remain operable
- forced-colors behavior is not broken by over-aggressive resets or fancy CSS

If existing tokens or primitives are weak here, refine them rather than layering hacks on top.

### 6. Accessible names, roles, and live messaging
Ensure core interactive surfaces expose usable semantics.

Requirements:
- interactive controls have accessible names
- route and section headings are consistent
- dialogs/drawers/menus/toolbars expose appropriate semantics
- toast or transient messages use safe announcement behavior where appropriate
- loading and busy states use accessible affordances where needed
- no noisy live-region spam

### 7. Gallery diagnostics and hardening aids
Use `/admin/design-system` as an internal verification surface.

Add or refine diagnostic sections for:
- focus visibility
- forced-colors / high-contrast behavior
- reduced-motion
- reduced-transparency where supported
- keyboard traversal samples for shell/nav/dialog/toolbar/flyout behavior

This route must remain internal and engineering-grade, not a glossy showcase.

### 8. Accessibility regression tests
Implement a meaningful regression suite.

At minimum add or refine tests for:
- keyboard-only traversal through shell/nav/page-header
- dialog focus trap and return focus
- drawer open/close focus behavior
- toolbar arrow-key model
- menu/flyout keyboard behavior
- focus visible on dark and high-contrast themes
- reduced-motion path
- forced-colors or high-contrast-safe rendering on critical controls
- route-level safe error and loading states where already present

Use the least disruptive reliable tooling the repository already supports.

### 9. Documentation
Document:
- the shell accessibility contract
- keyboard interaction rules
- focus-management rules
- reduced-motion and reduced-transparency behavior where supported
- high-contrast / forced-colors expectations
- how later work must verify accessibility before landing new primitives or routes

## Required deliverables

### Web / shared UI
- focus-management improvements
- keyboard interaction hardening
- reduced-motion / reduced-transparency support where supported
- high-contrast-safe styles and behavior
- gallery diagnostics

### Tests
- accessibility and keyboard regression coverage for core shell and overlay flows

### Docs
- accessibility and keyboard contract doc
- motion/transparency/high-contrast behavior doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/packages/ui/**`
- `/packages/contracts/**` only if small shared accessibility-related enums/types help
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- major visual redesigns
- feature-specific workflows from later phases
- giant shortcut systems that increase cognitive load
- decorative animations
- accessibility theater with no real regression coverage
- a second accessibility utility layer hidden in feature folders

## Testing and validation
Before finishing:
1. Verify keyboard-only traversal works across shell, nav, header, and current core routes.
2. Verify there are no keyboard traps.
3. Verify focus is visible and not obscured.
4. Verify dialogs, drawers, menus, and toolbars behave correctly with keyboard input.
5. Verify reduced-motion changes real behavior.
6. Verify reduced-transparency changes real behavior where applicable.
7. Verify high-contrast / forced-colors behavior is not broken on critical controls.
8. Verify accessible names and semantics exist on core interactive surfaces.
9. Verify `/admin/design-system` includes real diagnostics for the above.
10. Verify docs match the implemented accessibility contract and testing approach.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the shell is genuinely keyboard-first
- focus management is reliable and visible
- reduced-motion and reduced-transparency behavior is real where supported
- high-contrast / forced-colors safety is real
- overlay and toolbar behavior is accessible
- regression tests exist for the core interaction paths
- accessibility changes do not regress existing keyboard, focus, contrast, or reduced-motion test coverage
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

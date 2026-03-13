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
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-01-ingest-document-viewer-v1.md` for the component-gallery route and route-layout baseline
   - `/phases/phase-11-hardening-scale-pentest-readiness.md` for future-friendly quality-gate posture only
3. Then review the current repository generally — code, packages, styles, CSS, theme plumbing, routes, tests, docs, screenshots, and any existing design-system work — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second visual system or leave ad hoc token islands scattered across the app.

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
- `/phases` wins for the visual and interaction contract, shell philosophy, adaptive-state model, keyboard/focus posture, and change-control rules.
- Official docs win only for browser theming, accessibility semantics, CSS/media-feature mechanics, and implementation details of the current frontend framework.
- Do not let expedient styling shortcuts weaken the shared design-system contract.

## Objective
Forge the Obsidian Web design system: dark tokens, typography, surfaces, spacing, motion, and focus language.

This prompt owns:
- the canonical token system in `/packages/ui`
- dark/light/high-contrast theming foundations
- typography scale and spacing rhythm
- surface language and elevation model
- focus visibility and interaction-state language
- motion preferences and reduced-transparency behavior where supported
- the in-app design-system gallery becoming a real internal working gallery
- migration of existing app surfaces onto the shared token language where feasible

This prompt does not own:
- the full shell-layout rebuild
- the full primitive/component library
- viewer-specific dense workspace tooling
- a public Storybook replacing the in-app gallery
- ad hoc one-off feature styling outside the shared system

## Phase alignment you must preserve
From the Obsidian Folio blueprint and Phase 0/1 posture:

### Core experience principles
- design for the app window, not device class
- use state-based adaptive layouts, not fixed breakpoint page forks
- keep work inside one fold by default on supported window sizes
- prefer bounded overflow and progressive disclosure over page-growth clutter
- make keyboard-first operation and explicit focus visibility non-negotiable
- keep premium visual treatment subordinate to legibility and task speed

### Theme strategy
- dark theme is default
- light theme remains supported
- browser high-contrast / forced-colors is first-class and tested

### Canonical design-system source
`/packages/ui` must become the canonical design-system source for:
- color
- typography
- spacing
- radius
- elevation
- motion
- browser-native theming through CSS custom properties or equivalent typed token export

No phase should define an ad hoc visual token system outside the shared UI package.

### Interaction rules that matter now
- strong visible focus indicators on all interactive controls
- no keyboard traps
- reduced-motion is respected automatically, and reduced-transparency is respected where supported
- focus styling must survive dark, light, and high-contrast modes
- new components or primitives must appear in the in-app gallery before broad adoption

## Implementation scope

### 1. Canonical token architecture
Implement or refine a token system in `/packages/ui` that is actually canonical.

At minimum cover:
- semantic colors
- surface/background layers
- typography families, sizes, weights, line-heights
- spacing scale
- radius / shape
- elevation / depth
- motion durations/easing
- focus-ring tokens
- border and separator language
- status/accent tokens for environment/access/status surfaces

Requirements:
- semantic token names, not random color names scattered in app code
- typed exports where useful
- CSS custom properties or equivalent browser-native theme plumbing
- the current web app can consume the tokens immediately

### 2. Theme engine and preference behavior
Implement a real theme foundation.

Requirements:
- dark default
- light support
- user preference persistence
- support for:
  - `prefers-color-scheme`
  - `prefers-contrast`
  - `forced-colors`
  - `prefers-reduced-motion`
  - `prefers-reduced-transparency` where supported
- high-contrast-safe defaults
- reduced-motion is functional, not decorative, and reduced-transparency behavior is real where supported

Do not build a gimmicky theme switcher.
Make it feel like a serious internal tool.

### 3. Typography and spacing language
Define a calm, premium, serious editorial/operational rhythm.

Requirements:
- strong hierarchy for shell title, page title, section title, body, metadata, and microcopy
- dense but readable table/list/detail surfaces
- consistent spacing rhythm
- predictable vertical rhythm across shell, forms, lists, and detail panels
- no oversized consumer-app typography
- no cramped “enterprise spreadsheet” ugliness

### 4. Surface and material system
Define the visual material language for:
- app frame / chrome surfaces
- content panels
- dense work surfaces
- transient overlays
- bordered tables/lists/details
- quiet vs emphasized surfaces

Requirements:
- dark-first premium look
- restrained translucency
- no stacked heavy blur/glass gimmicks
- strong separation without noisy outlines everywhere
- serious, calm, trustworthy tone
- environment and access-tier signals remain visible without becoming loud

### 5. Focus and interaction language
Implement the product-wide focus and interaction-state system.

Requirements:
- visible focus ring language
- hover/active/selected/disabled states
- consistent interactive affordances
- keyboard-first confidence
- focus never disappears into dark surfaces
- focus-not-obscured considerations for sticky chrome and bounded regions

### 6. Low-level shared primitives only where necessary
Build only the lowest-level shared primitives needed to make the token system real and reusable.

Good examples:
- theme provider / theme hook
- base text primitives
- layout primitives such as stack/inline/cluster/container where useful
- surface wrapper
- badge or status-pill foundation
- scroll-region primitive
- focus-ring helper

Do not try to fully build:
- menus
- dialogs
- drawers
- data tables
- command bars
- heavy form systems

Those deeper primitives belong to later work unless a small foundational version is necessary to keep the system consistent.

### 7. In-app design-system gallery
Upgrade `/admin/design-system` into a real internal working gallery.

It must demonstrate and validate:
- tokens
- themes
- focus states
- typography scale
- spacing scale
- surface layers
- environment badge
- access-tier badge
- motion / reduced-motion diagnostics
- reduced-transparency diagnostics where supported
- high-contrast / forced-colors-safe patterns
- the adaptive-state visual language at least at a diagnostic level

This route is internal and non-marketing.
It should feel like an engineering-grade gallery, not a glossy design showcase.

### 8. Migration and anti-pattern cleanup
Refine existing web surfaces so they consume the shared design language.

Requirements:
- reduce hardcoded colors, spacing, and shadows in app routes
- route styles through `/packages/ui` where practical
- keep the migration least disruptive and explicit about remaining gaps
- do not rewrite every page just for aesthetic purity
- do eliminate obvious token drift in shell-level and frequently used surfaces

### 9. Documentation and guardrails
Document:
- token structure
- theming model
- how to add or change tokens safely
- what belongs in `/packages/ui`
- what must not be styled ad hoc in feature routes
- how the in-app gallery is used as the canonical preview and QA surface

If appropriate, add a lightweight lint/guardrail against raw hardcoded token values in core app-shell paths.

## Required deliverables

### Shared UI package
- token modules
- theme variables
- theme provider / preference plumbing
- foundational style primitives
- docs

### Web
- `/admin/design-system`
- existing shell/admin/auth/project surfaces updated to consume the shared token language where practical

### Docs
- design-system / token architecture doc
- theming / preference-behavior doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/packages/ui/**`
- `/web/**`
- `/packages/contracts/**` only if small shared enums/contracts help badge/status consistency
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- the complete component library
- shell layout overhaul beyond what is minimally needed to apply the system
- full viewer/workspace compositions
- marketing-site polish
- decorative animation systems
- noisy gradients, flashy glassmorphism, or AI-assistant aesthetics
- a second parallel styling system outside `/packages/ui`

## Testing and validation
Before finishing:
1. Verify dark theme is default and functional.
2. Verify light theme is functional.
3. Verify preference persistence works.
4. Verify reduced-motion behavior works.
5. Verify forced-colors/high-contrast behavior is not broken.
6. Verify focus indicators are clearly visible across core surfaces.
7. Verify `/admin/design-system` reflects the real shared token system, not fake examples disconnected from app usage.
8. Verify key existing routes now consume the shared design language more consistently.
9. Run visual/accessibility checks where practical on gallery and key shell routes.
10. Verify docs match the actual token architecture and usage.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- `/packages/ui` is the canonical design-system source
- the token system is real and reusable
- dark/light/preference behavior is robust
- focus language is strong and visible
- the in-app gallery renders token, typography, color, and primitive examples sourced from `/packages/ui` exports
- existing shell-level surfaces are materially more consistent
- shared `/packages/ui` tokens/primitives are applied across shell and gallery surfaces without ad hoc theme constant forks
- no ad hoc token system is left as the default path
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

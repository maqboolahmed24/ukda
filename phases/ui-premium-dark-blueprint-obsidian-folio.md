# Obsidian Folio: Premium Dark Experience Blueprint

> Status: CANONICAL EXPERIENCE LAYER
> Applies To: Phase 0 through Phase 11
> Platform: Secure web application delivered through the browser
> Translation Rule: Older WinUI or desktop-specific references are intent-level only and must be implemented with equivalent web patterns

## Purpose
Define one product-wide experience contract so every operational surface shares the same interaction model, visual system, and accessibility behavior from login through administration.

This blueprint is intentionally independent of phase-specific data models and APIs. It defines how users experience those capabilities and should be implemented through browser-native mechanics under the web-first execution patch.

## Core Experience Principles
1. Design for the app window, not device class.
2. Use state-based adaptive layouts, not fixed breakpoint page forks.
3. Keep work inside one fold by default on supported window sizes.
4. Prefer bounded overflow and progressive disclosure over page-growth clutter.
5. Make keyboard-first operation and explicit focus visibility non-negotiable.
6. Keep premium visual treatment subordinate to legibility and task speed.

## Canonical Spatial Contract
All high-density workspaces inherit the same adaptive state model:

- `Expanded`: left rail + center work surface + right inspector visible.
- `Balanced`: rail narrows, inspector compresses to summary.
- `Compact`: inspector becomes drawer/flyout; rail becomes compact strip.
- `Focus`: active work surface dominates; secondary panes become on-demand overlays.

State transitions are driven by current app-window client area and task context. They are never keyed only to device labels.

### Single-Fold Rule
- Default behavior for supported window sizes keeps shell header + page header + workspace body within one client-area fold.
- Vertical page-level scrolling is avoided in default state; dense content scrolls within bounded regions (tables, lists, filmstrips, transcript panes, findings panes).
- Accessibility fallback permits controlled scrolling during zoom, text-spacing, or reflow scenarios to avoid clipping, overlap, or obscured focus.

## Visual Foundation (Dark-First Premium Web UI)
### Theme Strategy
- Dark theme is the default product theme.
- Light theme remains supported for role or environment preference.
- Browser high-contrast or forced-colors rendering is first-class and tested.

### Materials
- Use subtle layered backdrops for long-lived frame/background surfaces.
- Use lighter translucent treatment on transient contextual surfaces only (flyouts, transient drawers, lightweight overlays).
- Do not stack heavy transparency across multiple layers.

### Tokens and Resources
Use `/packages/ui` as the canonical design-system source:

- shared theme tokens for color, typography, spacing, radius, elevation, and motion
- browser-native theming via CSS custom properties or equivalent typed token export
- support for user preferences including color scheme, contrast, reduced motion, and reduced transparency

No phase should define an ad hoc visual token system outside the shared UI package.

## Interaction Contract
### Command Hierarchy
`Shell navigation -> page header primary action -> contextual command bar -> overflow/flyout -> item context menu`

Each contextual command must also be reachable without relying on right-click context menus.

### Toolbar Behavior
- Toolbar is a single tab stop with roving focus and arrow-key navigation.
- Low-frequency actions move to explicit overflow surfaces with labels.
- Escape behavior is predictable and returns focus safely.

### Focus and Keyboard Safety
- Strong visible focus indicators on all interactive controls.
- No keyboard traps.
- Sticky headers, drawers, and flyouts cannot obscure active focus targets.
- Shortcuts are stable and discoverable per workspace.

## Motion and Depth
- Motion is functional only: causality, orientation, hierarchy.
- Prefer short transitions and subtle opacity/scale/elevation changes.
- Respect reduced-motion and reduced-transparency settings automatically.

## Canonical Shell
### Global Frame
- Title bar with app identity, project context, deployment-environment signal, and project access-tier signal.
- Primary navigation rail.
- Main content host with page header + body regions.
- Optional contextual right region depending on workspace state.

### Page Header
- One clear page title.
- One primary action per surface.
- Secondary/destructive actions move to labeled overflow.

## Surface Families
### Standard Work Surfaces
- Overview dashboards
- Tables with details drawers
- Wizard flows
- Run history and status surfaces

### High-Density Operational Workspaces
- Viewer
- Preprocessing compare
- Layout segmentation
- Transcription workspace
- Privacy review workspace
- Governance review surfaces requiring multi-pane inspection

All high-density surfaces must implement the canonical state model and single-fold rule.

## Component System
Maintain a web component gallery in-app (non-public production route) that demonstrates and tests:

- shell frame primitives
- command bars and overflow patterns
- table + drawer composition
- dialogs and flyouts
- toolbar roving focus
- state-transition behavior (`Expanded`, `Balanced`, `Compact`, `Focus`)
- focus indicators across dark, light, and high-contrast themes

## Accessibility Contract
Target WCAG 2.2 AA across core workflows with browser-native validation:

- keyboard-only path verification
- focus visibility and focus-not-obscured checks
- reflow behavior at increased zoom/text spacing
- semantic roles, names, and states for assistive technology and browser accessibility trees

## Test and Quality Gates
### Required Gates Across Phases
- visual regression for shell, key pages, and workspace states
- keyboard interaction gate for toolbars, dialogs, drawers, and flyouts
- accessibility scans on primary routes and high-density workspaces
- reflow/zoom gate verifying controlled scrolling fallback behavior

### Preferred Tooling
- browser automation for keyboard and route-transition testing
- browser accessibility auditing
- snapshot-based visual regression for dark/light/high-contrast variants

## Phase Inheritance Matrix
- Phase 0: establishes shell, tokens, theme/motion plumbing, and component gallery scaffolding.
- Phase 1: establishes canonical workspace contract and viewer baseline.
- Phases 2-5: inherit workspace state model for operational review surfaces.
- Phases 6-8: apply same contract to governance, review, and release decision surfaces.
- Phases 9-11: maintain the same shell, focus, and adaptive-state behavior for proof, discovery, and hardening workflows.

## Governance and Change Control
- Any deviation from this blueprint requires explicit rationale in phase documentation.
- New components must be added to the web component gallery before broad adoption.
- Visual style updates cannot weaken keyboard, focus, or reflow guarantees.

## References
- MDN: [Responsive design](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/CSS_layout/Responsive_Design)
- W3C WAI APG: [Toolbar Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/)
- W3C WCAG 2.2 baseline principles: [WCAG 2.2](https://www.w3.org/TR/WCAG22/)

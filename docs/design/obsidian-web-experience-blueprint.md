# Obsidian Web Experience Blueprint

> Status: Repository design contract
> Scope: Browser-native translation of the Obsidian Folio experience

## Visual Tone

The product should feel dark-first, premium, minimal, quiet, exact, and high-trust. It is a research and review tool, not a marketing site and not an AI chat product.

Required tone markers:

- restrained surfaces
- strong typography hierarchy
- deliberate spacing
- crisp focus indication
- visible confidence, provenance, and object state
- subdued motion only when it clarifies causality

## Shell Principles

- Design for the app window, not a fake desktop frame.
- Keep a stable navigation rail, page header, main work region, and optional context region.
- Optimize for laptop and desktop research work first, then adapt downward without losing task clarity.
- Prefer persistent object focus and calm layout shifts over flashy transitions.

## Browser Equivalents For Adaptive States

| State      | Browser-shell meaning                                                                       |
| ---------- | ------------------------------------------------------------------------------------------- |
| `Expanded` | Rail, central workspace, and persistent right inspector all visible                         |
| `Balanced` | Rail narrows, workspace remains primary, inspector compresses to summary or tabs            |
| `Compact`  | Rail becomes compact, inspector becomes drawer or flyout, commands move to overflow         |
| `Focus`    | Active work surface dominates; supporting regions open on demand without breaking the route |

State changes are driven by available app-window space and task context, not by simplistic device labels alone.

## Bounded-Region Scrolling Philosophy

- The shell should fit within one fold on supported window sizes whenever practical.
- Page-level scroll should stay restrained.
- Long content scrolls inside bounded regions such as tables, viewers, filmstrips, transcript panes, findings panes, and inspectors.
- Sticky headers and toolbars must not obscure active focus.
- Reflow, browser zoom, increased text spacing, and accessibility overrides may relax the single-fold goal when necessary to preserve legibility and focus visibility.

## Focus Management And Keyboard Behavior

- Every route needs clear landmarks and heading structure.
- Route changes move focus predictably to the page heading or the primary workspace anchor.
- Toolbars should behave as a single tab stop with arrow-key movement between controls.
- Escape closes the topmost transient surface and returns focus to the invoking control.
- There must be no keyboard traps, hidden focus, or focus loss after async updates.
- Keyboard shortcuts may accelerate expert workflows, but core actions must remain discoverable without memorizing shortcuts.

## Interaction Expectations For Common Surface Types

| Surface   | Browser-native contract                                                                                               |
| --------- | --------------------------------------------------------------------------------------------------------------------- |
| Dialog    | Use for blocking confirmation or short focused tasks; trap focus only while open; destructive intent must be explicit |
| Drawer    | Use for contextual secondary work in compact states; preserve main route and restore focus on close                   |
| Menu      | Use for short action lists or mode switches; never hide critical actions behind icon-only ambiguity                   |
| Toolbar   | Use roving focus, stable grouping, labeled overflow, and keyboard-safe shortcuts                                      |
| Table     | Support sorting, filtering, selection, and row-to-detail transitions without collapsing the surrounding shell         |
| Viewer    | Keep image/page focus primary, preserve zoom/page state in the URL, and avoid uncontrolled page growth                |
| Inspector | Show object metadata, confidence, provenance, and actions without stealing primary reading space                      |

## Theme, Contrast, And User Preference Behavior

- Dark theme is the default product presentation.
- Light theme remains supported for user or environment needs.
- Forced-colors and high-contrast rendering are first-class supported modes.
- Respect browser and OS preferences for:
  - `prefers-color-scheme`
  - `prefers-contrast`
  - `prefers-reduced-motion`
  - `prefers-reduced-transparency`
- Visual polish must degrade safely when those preferences demand it.

## Anti-Patterns To Avoid

- fake desktop title bars, window chrome, or file-explorer cosplay
- toy dashboards and oversized KPI cards without operational value
- AI-assistant tropes such as chat bubbles, sparkle iconography, or anthropomorphic system voice
- ornamental clutter, heavy glass layers, and decorative gradients that weaken legibility
- unbounded full-page scroll surfaces for dense review work
- icon-only command clusters without labels or discoverable focus order
- motion used as decoration instead of orientation
- hiding provenance, confidence, review state, or governance context behind secondary clicks

## Implementation Notes

- Shared tokens and bootstrap primitives now live in `/packages/ui` and should remain the canonical browser design-system entry point.
- High-density surfaces should inherit this blueprint before phase-specific embellishment.
- When the phase materials describe desktop-like panes or states, implement the behavior through web-native layouts, drawers, inspectors, and URL-addressable workspaces instead.

## Related Documents

- [`/phases/ui-premium-dark-blueprint-obsidian-folio.md`](../../phases/ui-premium-dark-blueprint-obsidian-folio.md)
- [`/docs/design/design-system-token-architecture.md`](./design-system-token-architecture.md)
- [`/docs/design/theming-preference-behavior.md`](./theming-preference-behavior.md)
- [`/docs/architecture/web-first-execution-contract.md`](../architecture/web-first-execution-contract.md)
- [`/docs/architecture/route-map-and-user-journeys.md`](../architecture/route-map-and-user-journeys.md)

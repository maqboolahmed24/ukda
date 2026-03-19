# Playwire QA Audit (2026-03-18)

## Benchmark Basis
- Primary benchmark intent: Figma design specifications via MCP.
- Current limitation: a concrete Figma file/node reference was not available in this workspace context (no file key/node id provided), so node-level visual parity could not be executed.
- Fallback benchmark used:
  - UKDE canonical design-system contract and token architecture:
    - `/Users/test/Code/UKDA/docs/design/design-system-token-architecture.md`
    - `/Users/test/Code/UKDA/docs/design/obsidian-web-experience-blueprint.md`
  - Existing browser visual baselines in `/Users/test/Code/UKDA/web/tests/browser/*-snapshots`.

## Resolution Coverage
- 1366x900 (Playwright baseline config)
- 1440x900
- 1920x1080

## Test Coverage Executed
- Full Chromium regression: `pnpm playwright test --project=chromium`
  - 15 failed, 28 passed, 2 not run.
- Visual-only sweep: `pnpm playwright test --project=chromium --grep @visual`
  - 12 failed, 0 passed.
- Keyboard/A11y/Reflow sweep: `pnpm playwright test --project=chromium --grep "@keyboard|@a11y|@reflow" --grep-invert "@visual|@perf"`
  - 2 failed, 24 passed.
- Multi-resolution route probe artifacts:
  - `/Users/test/Code/UKDA/output/playwright/qa-refresh-20260318/multires`

## Prioritized Findings

### P0 (Critical)

1. Cross-surface visual/layout regression against baseline design language
- Category: Layout regression + design-system drift
- Impact: Brand consistency and user trust degraded across core routes; major geometry and typographic shifts.
- Evidence:
  - 12/12 visual tests failing.
  - Privacy workspace card mismatch: expected 850x90, got 792x67.
    - `/Users/test/Code/UKDA/output/playwright/qa-refresh-20260318/test-results/privacy-workspace-regressi-0fbfb-trolled-mode-privacy-visual-chromium/privacy-workspace-default-diff.png`
  - Privacy run detail mismatch: expected 850x556, got 792x446.
    - `/Users/test/Code/UKDA/output/playwright/qa-refresh-20260318/test-results/privacy-workspace-regressi-d2854-visual-a11y-keyboard-reflow-chromium/privacy-run-review-blockers-diff.png`
  - Dialog mismatch in reduced motion: expected 576x158, got 640x174.
    - `/Users/test/Code/UKDA/output/playwright/qa-refresh-20260318/test-results/shell-regression-reduced-m-43f93-sual-baseline-visual-motion-chromium/dialog-overlay-reduced-motion-diff.png`
- Likely contributing code paths:
  - Hard width/height caps introduced on key layouts and viewer workspace:
    - `/Users/test/Code/UKDA/web/app/globals.css:89`
    - `/Users/test/Code/UKDA/web/app/globals.css:97`
    - `/Users/test/Code/UKDA/web/app/globals.css:103`
    - `/Users/test/Code/UKDA/web/app/globals.css:2148`

### P1 (High)

2. Command bar route execution is unreliable under suite load
- Category: Functional failure (keyboard-first navigation)
- Impact: High-friction expert workflow; command palette Enter action can no-op.
- Evidence:
  - Failure in keyboard sweep: query "jobs" + Enter remained on overview instead of navigating to jobs.
  - Trace context:
    - `/Users/test/Code/UKDA/test-results/primitives-interaction-com-6f677-her-keyboard-flows-keyboard-chromium/error-context.md`
  - Test reference:
    - `/Users/test/Code/UKDA/web/tests/browser/primitives-interaction.spec.ts:190`
- Notes:
  - Passes in isolated run, indicating an intermittent race/timing dependency rather than deterministic route break.

3. Preprocessing compare-route navigation intermittently aborts
- Category: Functional failure (route transition reliability)
- Impact: Compare workflow can fail to open under load.
- Evidence:
  - `page.goto(...)` `net::ERR_ABORTED` on preprocessing compare route during keyboard sweep.
  - Trace context:
    - `/Users/test/Code/UKDA/test-results/preprocessing-regression-p-14f04-closure-keyboard-preprocess-chromium/error-context.md`
  - Test reference:
    - `/Users/test/Code/UKDA/web/tests/browser/preprocessing-regression.spec.ts:169`
- Notes:
  - Passes in isolated run; likely transient route load/hydration race.

### P2 (Medium)

4. Performance budget breach in high-concurrency regression execution
- Category: Performance regression risk
- Impact: Slower perceived readiness on document library path under stress.
- Evidence:
  - Full-suite fail: document library initial render measured 6168ms (budget 4000ms).
  - Test reference:
    - `/Users/test/Code/UKDA/web/tests/browser/ingest-viewer-performance.spec.ts:16`
- Notes:
  - Passes in isolated run; indicates low performance headroom under parallel browser load.

## Verified Closed (No Longer Failing)

1. Project context nav clipping
- Multi-resolution hidden/clipped links: 0 across 1366x900, 1440x900, 1920x1080.
- Evidence:
  - `/Users/test/Code/UKDA/output/playwright/qa-refresh-20260318/multires/nav-visibility-summary.json`

2. Viewer thumbnail decode failure
- Filmstrip thumbs load with non-zero natural dimensions across all tested resolutions.
- Evidence:
  - `/Users/test/Code/UKDA/output/playwright/qa-refresh-20260318/multires/viewer-thumbnail-health.json`

3. Admin design-system duplicate React key error
- Prior duplicate-key (`motion-standard`) regression no longer reproduced in current targeted checks.

4. Keyboard accessibility of scrollable privacy comparison table and privacy workspace canvas
- Scroll region focusability fixes validated in targeted keyboard/a11y runs.

## Recommendations (Immediate)
1. Treat the broad visual regression as a single release-blocking workstream and reconcile intended geometry with baseline (or deliberately re-baseline after design signoff).
2. Stabilize command-bar and preprocessing compare transitions by removing timing-sensitive assumptions in keyboard flows.
3. Run final signoff in production-like build mode (not just dev-server) before accepting performance and interaction reliability.
4. Provide the exact Figma file URL/node IDs so this audit can be upgraded from baseline-proxy validation to strict node-level parity.

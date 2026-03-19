# Playwire QA Audit - 2026-03-18

## Benchmark and Scope
- Requested benchmark: Figma design specifications as primary source.
- Figma status in this session: authenticated but no project-specific Figma file URL/node IDs were available, so strict node-level parity validation could not be executed.
- Proxy benchmark used: existing Playwright visual baselines and design-system snapshots in `web/tests/browser/*-snapshots`.

## Resolutions Tested
- 1366x900
- 1440x900
- 1920x1080

## Fresh Test Runs
- Full Chromium regression: `pnpm test:browser --project=chromium`
  - Result: 45 total, 36 passed, 7 failed, 2 did not run.
- Focused rerun of failing domains (perf + visual specs):
  - Result: 31 total, 22 passed, 7 failed, 2 did not run.
- Fresh multi-resolution route probe:
  - Spec: temporary one-off probe (removed after run).
  - Artifacts: `/Users/test/Code/UKDA/output/playwright/qa-comprehensive-20260318-2026-03-18T22-34-24-032Z/multires-fresh`

## Prioritized Findings

### P0 - Release blocking

1) Project context tab strip is clipped on all tested desktop resolutions
- Category: Functional failure + layout regression.
- Impact: High task-blocking risk and IA discoverability failure; users cannot reliably access project surfaces from primary nav strip.
- Evidence:
  - `/Users/test/Code/UKDA/output/playwright/qa-comprehensive-20260318-2026-03-18T22-34-24-032Z/multires-fresh/nav-visibility-summary.json`
  - `1366x900`: `hiddenOrClippedCount=7` (includes Jobs, Export candidates, Export requests, Export review, Activity, Settings).
  - `1440x900`: `hiddenOrClippedCount=6`.
  - `1920x1080`: `hiddenOrClippedCount=2` (Activity, Settings).
  - Screenshot evidence: `/Users/test/Code/UKDA/output/playwright/qa-comprehensive-20260318-2026-03-18T22-34-24-032Z/multires-fresh/screens/project_search-1366x900.png`, `/Users/test/Code/UKDA/output/playwright/qa-comprehensive-20260318-2026-03-18T22-34-24-032Z/multires-fresh/screens/project_search-1920x1080.png`

2) Core visual contract drift across workspace surfaces
- Category: Design-system departure + layout regression.
- Impact: Brand inconsistency across primary workflows (layout, preprocessing, privacy, viewer), increased QA churn, and higher regression risk.
- Evidence from fresh rerun:
  - Layout workspace overlay: 10% pixel delta (`45534` px).
    - `/Users/test/Code/UKDA/test-results/layout-workspace-regressio-52e2e-and-inspector-states-visual-chromium/layout-workspace-overlay-on-diff.png`
  - Viewer loading state: 6% pixel delta (`26080` px).
    - `/Users/test/Code/UKDA/test-results/viewer-regression-viewer-v-caf79-ady-and-error-states-visual-chromium/viewer-state-loading-diff.png`
  - Viewer preprocessed mode: 7% pixel delta (`28968` px).
    - `/Users/test/Code/UKDA/test-results/viewer-regression-viewer-v-a1f72-pector-drawer-states-visual-chromium/viewer-mode-preprocessed-diff.png`
  - Privacy compare route: dimension mismatch expected `889x556`, actual `850x556`, 5% pixel delta (`23208` px).
    - `/Users/test/Code/UKDA/test-results/privacy-workspace-regressi-d2854-visual-a11y-keyboard-reflow-chromium/privacy-compare-route-states-diff.png`
  - Preprocessing overview: 3% pixel delta (`10728` px).
    - `/Users/test/Code/UKDA/test-results/preprocessing-regression-p-d670f--variants-visual-preprocess-chromium/preprocessing-overview-pages-diff.png`

### P1 - High

3) Performance budget breach on document library initial render
- Category: Performance regression.
- Impact: Slow first meaningful interaction on a core route; raises abandonment and operator delay risk.
- Evidence:
  - Test failure: `/Users/test/Code/UKDA/web/tests/browser/ingest-viewer-performance.spec.ts:16`
  - Latest measured breach: `10238ms` vs budget `4000ms`.
  - Error context: `/Users/test/Code/UKDA/test-results/ingest-viewer-performance--df3db-d-upload-wizard-phase1-perf-chromium/error-context.md`

### P2 - Medium

4) Minor shell visual mismatch in design-system route
- Category: Design-system consistency drift.
- Impact: Lower direct UX harm, but signals unstable visual contract.
- Evidence:
  - 1% pixel delta (`3062` px) on `design-system-shell-dark`.
  - Diff artifact: `/Users/test/Code/UKDA/test-results/shell-regression-design-sy-fef60-her-visual-baselines-visual-chromium/design-system-shell-dark-diff.png`
  - Expected snapshot includes a bottom-left issue toast not present in actual render (possible intentional behavior change, needs design/product confirmation).

## Functional Reliability Notes
- No deterministic keyboard/a11y failures reproduced in fresh full and focused runs beyond visual/perf failures.
- Two tests were skipped only because preprocessing visual baseline failed earlier in the chain.

## Figma Constraint (Important)
- Figma MCP authentication is healthy (`whoami` succeeded), but this workspace has no provided Playwire Figma URL/node IDs.
- To complete strict Figma benchmark parity (rather than baseline-proxy parity), provide one or more exact Figma links with `fileKey` and `node-id` for audited surfaces.

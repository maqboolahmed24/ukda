# Browser Regression Testing

This repository uses one canonical browser regression stack:

- Playwright (`@playwright/test`) for route automation, screenshots, keyboard flows, and focus behavior
- Axe (`@axe-core/playwright`) for browser accessibility scans
- A deterministic fixture mode (`UKDE_BROWSER_TEST_MODE=1`) that serves stable auth/project/admin payloads from the web app without requiring a live API

The suite lives in [`/web/tests/browser`](../../web/tests/browser).

## Phase 1 Ingest/Viewer Gate Matrix

Prompt 30 extends the browser gate with explicit Phase 1 ingest/viewer coverage:

- `chromium`: full `@phase1` slice, including `@perf` budgets
- `firefox-phase1`: `@phase1` stability slice, excludes `@perf` and `@visual`
- `webkit-phase1`: `@phase1` stability slice, excludes `@perf` and `@visual`

The dedicated specs are:

- `web/tests/browser/ingest-viewer-phase1.spec.ts`
- `web/tests/browser/ingest-viewer-performance.spec.ts`

They cover:

- upload/import route basics
- resumable upload session progression and completion UX
- document library reachability
- ingest-status retry surface
- viewer open/navigation path
- auth denial path after session removal

## Phase 2 Preprocessing Visual + A11y Coverage

Prompt 38 extends the same Playwright/Axe stack with canonical preprocessing route coverage:

- `web/tests/browser/preprocessing-regression.spec.ts`

It includes:

- visual baselines for preprocessing overview/pages, runs table, run detail summary, quality route, compare route, advanced profile disclosure, and not-ready/error states
- accessibility checks for preprocessing overview, quality table surface, run detail, and compare diagnostics surfaces
- keyboard/focus flows across preprocessing tabs, triage table controls, details drawer open/close, compare links, and advanced-disclosure controls

No second browser regression framework is introduced.

## Scope Covered by This Gate

Canonical route coverage:

- `/login`
- `/projects`
- `/projects/:projectId/overview`
- `/projects/:projectId/documents/:documentId/viewer?page={page}`
- `/projects/:projectId/documents/:documentId/preprocessing`
- `/projects/:projectId/documents/:documentId/preprocessing/quality`
- `/projects/:projectId/documents/:documentId/preprocessing/runs/:runId`
- `/projects/:projectId/documents/:documentId/preprocessing/compare`
- `/admin/design-system`

Canonical shell and primitive coverage:

- authenticated shell (rail, header, context bar, work region)
- command bar and project switcher overlays
- page-header primary and overflow actions
- dialog, drawer, menu/flyout, toolbar roving focus, and table states via the design-system route

Preference/reflow variants covered where stable:

- dark and light visual baselines
- forced-colors/high-contrast-safe baseline
- reduced-motion overlay baseline
- single-fold desktop check and compact/focus reflow fallback check
- viewer loading/ready/error visual baselines and bounded-filmstrip workspace checks

## Commands

Install browser runtime:

```bash
pnpm test:browser:install
```

Run the browser gate:

```bash
pnpm test:browser
```

Run only the Phase 1 ingest/viewer matrix:

```bash
pnpm test:browser --project=chromium --project=firefox-phase1 --project=webkit-phase1 --grep @phase1 --workers=1
```

Run preprocessing-only browser regression checks:

```bash
pnpm test:browser --project=chromium --grep @preprocess --workers=1
```

Update visual baselines intentionally:

```bash
pnpm test:browser:update
```

The JS CI gate (`make ci-js`) runs this suite and fails on visual, accessibility, keyboard, or focus regressions.

## Performance Budgets (Prompt 30)

Phase 1 numeric budgets are enforced by `web/tests/browser/ingest-viewer-performance.spec.ts`:

- document library initial render: `<= 4000ms`
- document library filter apply: `<= 1500ms`
- viewer first-page render: `<= 3500ms`
- viewer thumbnail strip readiness: `<= 3000ms`
- upload wizard file-selection responsiveness: `<= 1000ms`

Budget constants live in [`web/tests/browser/performance-budgets.ts`](../../web/tests/browser/performance-budgets.ts).

Each run attaches `phase1-performance-metrics.json` to Playwright test artifacts for CI diagnosis.

## Visual Baseline Workflow

1. Make the intended UI change.
2. Run `pnpm test:browser`.
3. If screenshot diffs are intentional, run `pnpm test:browser:update`.
4. Review changed baseline images under `web/tests/browser/**` before commit.
5. Reject baseline churn that does not map to user-visible shell or primitive changes.

## Accessibility and Interaction Failure Policy

- Do not suppress Axe violations just to pass the gate.
- Fix semantic, labeling, focus order, or contrast issues in component/route code.
- Keyboard tests must preserve escape behavior, focus return, and no-trap guarantees.
- Focus-visible and focus-not-obscured checks are blocking for shell and overlay surfaces.

## Fixture Mode Notes

`UKDE_BROWSER_TEST_MODE=1` enables deterministic fixture responses for:

- `/auth/providers`
- `/auth/session`
- `/projects`, `/projects/:projectId`, `/projects/:projectId/workspace`
- `/projects/:projectId/jobs/summary`
- `/projects/:projectId/documents`, `/projects/:projectId/documents/:documentId`
- `/projects/:projectId/documents/:documentId/pages`
- `/projects/:projectId/documents/:documentId/pages/:pageId` (`GET` and `PATCH` for viewer rotation)
- `/admin/audit-integrity`
- `/admin/security/status`
- `/admin/operations/overview`
- `/me/activity`

This keeps route coverage stable while preserving real App Router rendering behavior.

## Current Automation Boundary

The suite approximates reflow/zoom safety with viewport-driven checks and shell-state assertions. It does not fully emulate all browser zoom/text-spacing assistive configurations yet; those remain part of manual release hardening.

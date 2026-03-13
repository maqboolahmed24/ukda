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
   - `/phases/phase-01-ingest-document-viewer-v1.md` for visual regression, accessibility, keyboard-interaction, and single-fold workspace quality gates
   - `/phases/phase-11-hardening-scale-pentest-readiness.md` for future-facing regression and hardening expectations
3. Then review the current repository generally — browser test setup, visual baselines, accessibility tooling, CI workflows, shared UI primitives, shell routes, gallery routes, fixtures, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second browser-test stack or duplicate screenshot harnesses.

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
- `/phases` wins for required quality gates, shell/workspace behavior, accessibility and keyboard expectations, reflow/single-fold rules, and UX variants that must be covered.
- Official docs win only for implementation mechanics.
- Prefer stable, low noise, deterministic regression coverage over flashy or flaky test breadth.

## Objective
Ship visual regression, accessibility, and interaction tests for the shell and core web primitives.

This prompt owns:
- the canonical browser regression harness
- screenshot-based visual regression for core shell states and primitives
- accessibility scans on key routes and overlays
- keyboard-interaction and focus-behavior tests
- reduced-motion, high-contrast, and reflow-safe regression checks where practical
- stable fixtures and deterministic test data for core UI coverage
- CI integration for these gates

This prompt does not own:
- exhaustive feature E2E coverage for later phases
- flaky pixel-hunting for unfinished feature areas
- a second testing stack parallel to the current one
- noisy tests that break continuously for non-user-visible reasons

## Phase alignment you must preserve
From the UI blueprint and Phase 1 quality gates:

### Required gates across phases
- visual regression for shell, key pages, and workspace states
- keyboard interaction gate for toolbars, dialogs, drawers, and flyouts
- accessibility scans on primary routes and high-density workspaces
- reflow/zoom gate verifying controlled scrolling fallback behavior

### Phase 1 test architecture guidance
- browser screenshot diff with `toHaveScreenshot()` is acceptable
- optional internal gallery snapshot harness using mock/stub data only
- browser accessibility auditing plus browser automation on key routes
- keyboard-flow tests for shell, nav, dialogs, and toolbar components
- focus-visibility and focus-not-obscured checks on dark and high-contrast themes
- use reusable fixtures and Page Object Models as the suite scales

### Product tone
The tests must reinforce the calm, serious, browser-native shell and primitive system, not push the repo into brittle demo theatrics.

## Implementation scope

### 1. Canonical browser regression harness
Implement or refine one canonical browser test harness.

Requirements:
- one consistent browser test stack
- stable local and CI execution
- deterministic fonts/assets where practical
- deterministic seed data or stub/mocked data where needed
- sensible test project structure and naming
- clear separation between:
  - shell/primitive regression coverage
  - later feature coverage that is not part of this prompt

If the repo lacks a browser suite, add one clear canonical stack and wire it cleanly into CI.

### 2. Visual regression coverage
Implement screenshot-based visual regression for the core shell and primitives.

At minimum cover:
- authenticated shell
- nav rail and page-header states
- `/login`
- `/projects`
- at least one project-scoped route such as overview or jobs
- `/admin/design-system`
- command bar / project switcher if those surfaces already exist in the repo
- dialog, drawer, toolbar, menu/overflow, toast, and table states using the real gallery or real routes
- dark theme baseline
- light theme baseline where supported
- high-contrast or forced-colors-safe baseline where practical and stable

Requirements:
- use deterministic fixtures or mocks where needed
- avoid unstable external data dependencies
- keep baselines intentional and reviewable
- do not generate meaningless screenshot noise

### 3. Accessibility scans
Implement browser accessibility scans on the core routes and key overlays.

At minimum cover:
- shell routes
- `/login`
- `/projects`
- one project route
- `/admin/design-system`
- dialog
- drawer
- toolbar/menu states where applicable

Requirements:
- accessibility auditing is automated
- failures are actionable
- high-density surfaces and overlays are included
- do not suppress issues just to get green runs

### 4. Keyboard interaction regression
Implement meaningful keyboard-flow tests.

At minimum cover:
- shell/nav traversal
- current-route highlighting and activation by keyboard
- page-header primary/overflow action behavior
- dialog focus trap and focus return
- drawer open/close focus behavior
- toolbar roving-focus arrow-key behavior
- menu/flyout keyboard behavior
- command bar and project switcher if implemented
- no keyboard traps on the covered surfaces

### 5. Focus visibility and focus-not-obscured checks
Add explicit regression checks for:
- visible focus on dark theme
- visible focus on high-contrast or forced-colors-safe paths where practical
- focus not obscured by sticky shell chrome, drawers, or overlays
- route transitions preserving or intentionally resetting focus safely

### 6. Reflow / single-fold-safe checks
Add practical regression checks for the shell's bounded-work-region behavior.

Requirements:
- supported shell sizes maintain the intended one-fold composition where applicable
- controlled fallback exists under constrained width or reflow conditions
- tests exercise at least a few window sizes/states
- no routine full-page vertical sprawl appears by accident on the covered routes
- zoom/reflow-safe behavior is approximated as practically as the current test stack allows

Be explicit about any hard boundary that cannot be fully automated yet.

### 7. Reduced-motion and preference variants
Where the current stack supports it cleanly, add regression coverage for:
- reduced-motion behavior on overlays and route transitions
- high-contrast or forced-colors-safe rendering
- reduced-transparency-safe rendering where supported and where the product uses translucency

Do not overcomplicate the suite just to tick boxes.
Cover what can be made stable and useful now.

### 8. Stable fixtures and test ergonomics
Implement or refine the data/test harness so the core UI tests remain deterministic.

Requirements:
- seeded or mocked data for gallery and shell coverage
- stable auth/project fixtures where needed
- no dependency on live mutable production-like data
- Page Object Models or equivalent reuse for shell, overlays, and high-frequency flows if that clearly simplifies the suite

### 9. CI integration and artifacts
Wire the regression suite into the existing quality-gate path.

Requirements:
- browser tests can run in CI
- visual diff artifacts are available when failures happen
- accessibility and keyboard failures fail the appropriate quality gate
- commands are documented and match the repo
- keep the suite practical; do not introduce an hours-long browser matrix

### 10. Documentation
Document:
- what the regression suite covers
- what routes and primitives are canonical coverage targets
- how visual baselines are reviewed and updated
- how accessibility scans are interpreted
- what later work must add when it introduces new primitives or major routes

## Required deliverables

### Tests / tooling
- canonical browser regression suite
- screenshot regression coverage
- accessibility scan coverage
- keyboard/focus regression coverage
- stable fixtures or mocks
- CI wiring and artifacts

### Web / gallery
- any small deterministic harness adjustments needed to make the covered routes and gallery stable under test

### Docs
- browser regression testing doc
- visual baseline update process doc
- accessibility/interaction gate doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/packages/ui/**` only where small deterministic-test or accessibility improvements are needed
- test directories and config files
- CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- broad later-phase feature E2E coverage
- flaky visual tests for highly volatile unfinished screens
- a second browser-testing framework
- giant cross-browser matrices if they are unstable or low-value right now
- decorative test output with little engineering value

## Testing and validation
Before finishing:
1. Verify the browser regression suite runs locally.
2. Verify screenshot regression exists for the covered shell and primitive states.
3. Verify accessibility scans run on the covered routes and overlays.
4. Verify keyboard-interaction tests cover the shell and core primitives.
5. Verify focus visibility and focus-not-obscured behavior are meaningfully checked.
6. Verify any reduced-motion/high-contrast variants you add are stable and useful.
7. Verify CI wiring matches the actual commands and produces useful artifacts.
8. Verify docs match the implemented regression process.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- one canonical browser regression harness exists
- visual regression is enabled for shell and core primitives
- accessibility scans are automated on key routes
- keyboard and focus interaction tests are real
- CI uploads screenshots, diffs, and traces for failing visual or interaction tests
- CI test outputs are deterministic and new route/component specs can be added without replacing the harness
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

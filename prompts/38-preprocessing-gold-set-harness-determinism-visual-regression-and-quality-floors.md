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
   - `/phases/phase-02-preprocessing-pipeline-v1.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — preprocessing engine code, profile registry, regression tests, browser visual baselines, CI workflows, deterministic fixtures, compare routes, quality routes, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second regression harness, a second gold-set folder shape, or a second visual-baseline system for the same preprocessing tranche.

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
- `/phases` wins for preprocessing determinism, approved drift handling, visual gates, accessibility expectations, and quality-floor intent.
- Official docs win only for implementation mechanics.
- Preserve the rule that silent preprocessing drift must be caught before it reaches later phases.

## Objective
Ship the preprocessing gold-set harness for determinism, visual regression, and quality floors.

This prompt owns:
- the canonical preprocessing gold-set harness
- deterministic fixture packaging for preprocessing profiles
- approved baseline manifests for output hashes and perceptual similarity where allowed
- quality-floor assertions for preprocessing drift
- visual regression coverage for preprocessing UI surfaces
- CI wiring for deterministic and visual preprocessing gates
- drift-review workflow and documentation

This prompt does not own:
- new preprocessing algorithm features
- new compare UX features
- layout/transcription/privacy feature work
- a second browser-test stack
- noisy or flaky test coverage that creates more noise than signal

## Phase alignment you must preserve
From Phase 2:

### Determinism and regression rules
- canonical parameter serialization (`same params => same hash`)
- same input + same params + same version should produce stable outputs in the same container/runtime
- golden dataset (10–20 pages):
  - hash checks or approved SSIM threshold
  - CI fails on unapproved drift
- regression or golden test pack prevents silent preprocessing quality drift

### Advanced profile gate coverage
- regression suite includes:
  - pages where binarization helps
  - pages where binarization harms
- advanced options remain behind progressive disclosure and clear labels

### Web-surface gates already required in Phase 2
- visual snapshots for runs table states and run detail summary
- compare-mode snapshots
- quality and triage route states
- accessibility gates for tabs, tables, drawers, and viewer/compare routes

### Phase 11 posture
- quality gates should be deterministic, reviewable, and CI-friendly
- operator trust depends on stable and explainable regression output
- failure artefacts must be useful, not theatrical

## Implementation scope

### 1. Canonical preprocessing gold set
Create or refine one canonical gold-set fixture pack for preprocessing.

Requirements:
- 10–20 representative pages or the strongest consistent fixture subset the repo can sustain deterministically
- include cases such as:
  - low DPI
  - skew
  - blur
  - low contrast
  - pages where binarization helps
  - pages where binarization harms
  - pages with bleed-through concerns if the repo already supports that path
- fixture metadata is explicit and durable
- fixtures do not require public network access
- fixtures fit the repo's controlled test posture

Keep the fixture pack small enough to run in CI but rich enough to catch real drift.

### 2. Baseline manifest and approval model
Implement a canonical baseline manifest or equivalent approval artifact.

Requirements:
- baseline records tie to:
  - input fixture identity
  - selected profile
  - expanded params
  - params hash
  - pipeline version
  - output hashes and/or approved SSIM thresholds
  - expected warnings where useful
- a change in baseline requires an explicit reviewed update path
- CI distinguishes:
  - approved baseline updates
  - unapproved drift
- no ad hoc baseline files scattered across tests

### 3. Determinism gate
Implement or refine a deterministic regression runner.

Requirements:
- same fixture + same expanded params + same pipeline version => same hash, unless the approved baseline explicitly uses a perceptual threshold instead
- canonical parameter serialization is exercised in the harness
- output keys remain inside the canonical preprocess-derived prefix
- the harness is deterministic and stable under CI
- failures point to the exact fixture/profile/page that drifted

Where strict hash equality is too brittle for a known acceptable case, use an explicitly approved SSIM or equivalent threshold and document why.

### 4. Quality-floor assertions
Add preprocessing quality floors that are small, exact, and justified.

Requirements:
- quality floors are tied to real fixture expectations, not hand-wavy global scores
- examples may include:
  - expected warning presence or absence
  - expected metric direction or threshold floors on curated fixtures
  - expected output availability for grayscale and binary variants where enabled
- do not invent one giant “quality score”
- quality floors must be explainable to an engineer reviewing a failing run

### 5. UI visual regression for preprocessing surfaces
Expand the canonical browser visual regression suite for preprocessing.

At minimum cover:
- preprocessing overview
- runs table states
- run detail summary
- quality tab states
- compare route states
- advanced option disclosure states if the repo already implements them
- empty/loading/error/not-ready states where applicable

Requirements:
- use stable fixtures or stubbed data
- preserve the calm dark operational tone in snapshots
- no meaningless screenshot diffs
- visual baselines are reviewable and updated through the canonical process

### 6. Accessibility and interaction gates
Make preprocessing UI gates concrete.

Requirements:
- Axe or equivalent accessibility checks on preprocessing routes
- keyboard and focus checks on:
  - tabs
  - tables
  - drawers
  - compare surfaces
  - advanced-option disclosure controls
- no keyboard traps
- focus-visible behavior remains strong in dark/high-contrast paths

### 7. Drift artefacts and CI ergonomics
Make failures easy to review.

Requirements:
- deterministic regression failures produce useful diff artefacts or summaries
- visual regression failures produce useful screenshot artefacts
- docs explain how to review and approve legitimate baseline changes
- CI commands are obvious and reproducible locally
- no second CI workflow is created if the existing one can be extended cleanly

### 8. Performance-aware guardrails
Where stable and practical, add light performance-aware checks.

Requirements:
- do not create noisy hardware-sensitive gates
- if you add runtime checks, keep them broad and explainable
- prioritize deterministic correctness and drift detection over brittle micro-benchmarks

### 9. Documentation
Document:
- fixture-pack ownership
- baseline manifest format
- determinism rules
- SSIM or other perceptual-threshold exception handling
- visual baseline update process
- what later work must add when new preprocessing profiles or compare variants appear

## Required deliverables

### Tests / fixtures / CI
- canonical preprocessing gold-set fixture pack
- baseline manifest or approved-drift artifact
- deterministic preprocessing regression harness
- visual regression coverage for preprocessing surfaces
- accessibility/interaction coverage for preprocessing surfaces
- CI wiring and artefacts

### Docs
- preprocessing gold-set and drift-approval doc
- preprocessing visual baseline update doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**` only if a small test-support contract alignment is required
- `/web/**` only where small deterministic test hooks are needed
- `/packages/contracts/**` only if small test-fixture or variant enums help
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- new preprocessing algorithms
- a second visual regression stack
- sprawling unstable browser matrices
- noisy flake-prone “quality” tests
- layout/transcription/privacy feature work

## Testing and validation
Before finishing:
1. Verify the gold-set harness runs locally.
2. Verify deterministic fixture + params + version runs either match hash baselines or approved perceptual thresholds.
3. Verify unapproved drift fails CI meaningfully.
4. Verify approved-baseline update flow is documented and testable.
5. Verify preprocessing visual baselines exist for the covered routes and states.
6. Verify accessibility and keyboard gates run on preprocessing surfaces.
7. Verify advanced-profile regression includes both helpful and harmful binarization cases where supported.
8. Verify failure artefacts are useful and reviewable.
9. Verify docs match the implemented fixture, baseline, and approval process.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- one canonical preprocessing gold-set harness exists
- determinism drift is caught automatically
- approved baseline changes have a clear review path
- preprocessing UI visual regression is real
- accessibility and interaction gates cover preprocessing surfaces
- the suite runs deterministically in CI and supports additive fixtures/specs without replacing the harness
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

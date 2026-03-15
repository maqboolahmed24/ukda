# CI/CD Quality Gates

UKDE now has a deterministic delivery skeleton for Phase 0 Iteration 0.1. The pipeline is designed to stay readable, fail fast, and preserve the internal-only posture described in [`/phases/phase-00-foundation-release.md`](../../phases/phase-00-foundation-release.md).

## Workflows

- [`/.github/workflows/ci.yml`](../../.github/workflows/ci.yml): merge-blocking code quality, tests, and build verification for JS and Python.
- [`/.github/workflows/dependency-review.yml`](../../.github/workflows/dependency-review.yml): dependency review for PRs plus runtime vulnerability audits for JS and Python.
- [`/.github/workflows/images.yml`](../../.github/workflows/images.yml): PR verification builds for `web`, `api`, and `workers`, plus internal-registry publishing on trusted branches.
- [`/.github/workflows/deploy-preview.yml`](../../.github/workflows/deploy-preview.yml): internal preview deployment and cleanup for labeled pull requests.
- [`/.github/workflows/deploy-environments.yml`](../../.github/workflows/deploy-environments.yml): manual gated deployment to `dev`, `staging`, or `prod`.

## What Blocks Merges

- `CI / javascript`
- `CI / python`
- `Dependency Review / dependency-review`
- `Dependency Review / vulnerability-audit`
- `Images / verify`

These checks are the intended required-status set. Repository settings still need to mark them as required in branch protection.

## Local Parity Commands

Run the closest local equivalent to PR CI after activating a Python environment:

```bash
make install-python
make ci
```

Additional local delivery checks:

```bash
make verify-images
make render-manifests
```

Browser regression gate (visual + accessibility + keyboard/focus):

```bash
pnpm test:browser:install
pnpm test:browser
```

Phase 1 ingest/viewer matrix (Prompt 30):

```bash
pnpm test:browser --project=chromium --project=firefox-phase1 --project=webkit-phase1 --grep @phase1 --workers=1
```

Phase 2 preprocessing browser tranche (Prompt 38):

```bash
pnpm test:browser --project=chromium --grep @preprocess --workers=1
```

Canonical preprocessing determinism gate:

```bash
make test-preprocess-gold
```

Canonical privacy regression gate (disclosure safety + reviewer lifecycle):

```bash
make test-privacy-regression
```

Canonical governance-integrity gate (manifest/ledger reconciliation, tamper evidence, and handoff lineage):

```bash
make test-governance-integrity
```

Canonical export-hardening gate (release-pack validation, audit completeness, and egress denial regressions):

```bash
make test-export-hardening
```

## Toolchain Pins

- Node.js: [`.node-version`](../../.node-version)
- Python: [`.python-version`](../../.python-version)
- JS dependency lock: [`pnpm-lock.yaml`](../../pnpm-lock.yaml)
- Python CI lock: [`requirements/python-ci.lock`](../../requirements/python-ci.lock)

## Secrets And Variables

The image-publish and deploy workflows expect these repository or environment settings:

- `vars.INTERNAL_REGISTRY`
- `vars.INTERNAL_IMAGE_NAMESPACE`
- `secrets.INTERNAL_REGISTRY_USERNAME`
- `secrets.INTERNAL_REGISTRY_PASSWORD`

Preview and environment deployment jobs must run on internal self-hosted runners labeled `self-hosted`, `linux`, and `internal`.

## Security Gates And Waivers

- PR dependency changes are checked by [`/.github/dependency-review-config.yml`](../../.github/dependency-review-config.yml).
- High-severity JS vulnerabilities fail via `pnpm audit --audit-level high --prod`.
- Python vulnerabilities fail via `pip-audit --strict`.

Tracked waiver mechanism:

- JavaScript and transitive dependency waivers must be committed as reviewed changes to [`/.github/dependency-review-config.yml`](../../.github/dependency-review-config.yml).
- Python audit waivers are intentionally not pre-created. If one becomes necessary, add the ignore explicitly in a reviewed workflow change and document the rationale in the PR. Silent local bypasses are not acceptable.

## Internal-Only Posture

- Preview deployments are internal dev-class environments, not public demos.
- Publish and deploy jobs assume internal runners because public runners may not reach the internal registry or cluster.
- The Helm skeleton does not introduce any new egress path. It deploys `web`, `api`, and `workers` with deny-by-default egress policy templates enabled in preview/staging/prod overlays.

## Browser Regression Artifacts

When browser regression fails in CI, the JavaScript job uploads:

- `playwright-report`
- `test-results` (includes screenshots, diffs, and traces)

These artifacts are the canonical review path for visual and interaction regressions.

When preprocessing, privacy, governance, or export-hardening regression gates fail in CI, the Python job uploads:

- `api/tests/.artifacts/preprocessing-gold-set`
- `api/tests/.artifacts/privacy-regression`
- `api/tests/.artifacts/governance-integrity`
- `api/tests/.artifacts/export-hardening`

These artifacts contain deterministic drift/failure details for triage, including request-level release-pack and audit-completeness failures plus no-bypass egress denial checks.

## Prompt 30 Phase 1 Quality Gates

Prompt 30 adds merge-blocking ingest/viewer gate coverage:

- Access-control regression coverage for ingest and viewer protected paths.
- Cross-browser stability for the Phase 1 tranche on Chromium, Firefox, and WebKit.
- Numeric performance budgets enforced from:
  - [`web/tests/browser/performance-budgets.ts`](../../web/tests/browser/performance-budgets.ts)

Budget failures and performance measurements are attached as Playwright artifacts (`phase1-performance-metrics.json`) under `test-results`.

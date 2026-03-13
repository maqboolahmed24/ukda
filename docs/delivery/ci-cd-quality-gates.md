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

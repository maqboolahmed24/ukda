You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed source files before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first on each run.

## Mandatory first actions
1. Inspect the relevant repository areas and any existing implementation this prompt may extend.
2. Read these local files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-00-foundation-release.md`
3. If present, also read and honor any earlier implementation docs and repo artifacts, including:
   - `README.md`
   - `docs/architecture/**`
   - `docs/design/**`
   - `.github/workflows/**`
   - `infra/**`
   - root package/toolchain config files
   - Docker / Compose / Helm / Terraform files already in the repo
4. Before adding new pipeline files, inspect any existing CI/CD or deployment setup and reconcile with it instead of duplicating it.

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
- Local phase contracts win for product behavior, workflow ownership, governance, audit, security boundaries, data semantics, and acceptance logic.
- Official external docs win only for CI/CD mechanics, workflow syntax, containerization mechanics, deployment environment wiring, browser/app framework conventions, and test tooling setup.
- If a local document uses language that assumes earlier desktop delivery, preserve the intent and translate it into the current web-first/browser-first execution model instead of copying desktop mechanics literally.

## External official reference pack for platform mechanics only
Use these only for mechanics. Do not let them override UKDE product rules.

### GitHub Actions
- https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions
- https://docs.github.com/actions/using-workflows/about-workflows
- https://docs.github.com/actions/deployment/about-deployments/deploying-with-github-actions
- https://docs.github.com/actions/deployment/targeting-different-environments/using-environments-for-deployment
- https://docs.github.com/code-security/supply-chain-security/understanding-your-software-supply-chain/about-dependency-review
- https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/configuring-the-dependency-review-action

### Next.js
- https://nextjs.org/docs/app/getting-started/deploying
- https://nextjs.org/docs/app/guides/self-hosting
- https://nextjs.org/docs/app/guides/testing
- https://nextjs.org/docs/pages/guides/testing/playwright

### FastAPI
- https://fastapi.tiangolo.com/deployment/docker/
- https://fastapi.tiangolo.com/deployment/concepts/
- https://fastapi.tiangolo.com/tutorial/testing/
- https://fastapi.tiangolo.com/advanced/settings/

### Docker Compose
- https://docs.docker.com/compose/
- https://docs.docker.com/compose/gettingstarted/

## Objective
Implement the deterministic delivery automation required for Phase 0 Iteration 0.1 without drifting into later workflow phases.

This prompt owns:
- deterministic CI
- merge-blocking quality gates
- dependency and supply-chain review gates
- container image builds for the web/api/workers stack
- internal preview-environment scaffolding
- gated promotion skeleton for `dev`, `staging`, and `prod`
- clear operator/developer documentation for the above

This prompt does not own Phase 0.2 identity, real RBAC behavior, audit ledger implementation, jobs, export flows, ingest, preprocessing, transcription, privacy review, or discovery.

## Phase alignment you must preserve
From Phase 0 Iteration 0.1, this work must support:
- secure web application as the active delivery target
- `/web`, `/api`, `/workers`, `/packages/ui`, `/packages/contracts`, `/infra`
- environment profiles `dev`, `staging`, `prod`
- no shared secrets
- internal container registry only
- CI pipeline with unit tests, lint/format, container image builds, and dependency scan
- security gate that fails on high-severity dependency vulnerabilities unless explicitly waived with tracking
- browser-first product posture and future internal component gallery / shell quality gates

## Key implementation rule for previews
Preview environments are allowed only as internal dev-class deployments.
They are not public demos, not public SaaS previews, and not a new governance tier.
Treat preview deployments as ephemeral internal environments derived from the `dev` posture.

## Delivery-platform rule
Default to GitHub Actions and GitHub workflow files if the repo has no CI yet.
If the repo already uses a consistent non-GitHub CI/CD system, do not replace it blindly. Extend or reconcile with the least disruptive path while keeping the repo easy for future developers and coding agents to understand and keeping the gates merge-blocking.

Actual deploy and registry-push jobs must be designed so they can run on self-hosted runners when internal network access is required. Do not assume public runners can reach private cluster endpoints or internal registries.

## Implementation scope
Implement all of the following unless the repo already has an equivalent:

### 1. Deterministic toolchain and local CI parity
Create or tighten:
- pinned Node and Python runtime expectations
- deterministic install behavior using lockfiles
- clear root-level scripts/commands for:
  - lint
  - format-check
  - typecheck
  - unit test
  - build
  - e2e smoke, if an e2e harness already exists or can be added cleanly
- one local command that approximates CI execution for developers

Do not over-engineer this. The next coding agent should understand the pipeline quickly.

### 2. Pull-request CI
Create a PR CI workflow that, at minimum:
- installs workspace dependencies deterministically
- runs JS/TS lint + typecheck + tests + build for the web/shared packages
- runs Python lint/format/test/import checks for the API and workers
- fails fast on obvious misconfiguration
- publishes artifacts only when genuinely useful
- is small, readable, and debuggable

The pipeline must use the actual repo structure, not hypothetical paths.

### 3. Supply-chain and dependency review
Implement a dependency-review gate for pull requests and a practical dependency-vulnerability gate for the repo's JS and Python ecosystems.

Requirements:
- block merge on high-severity dependency issues unless a tracked waiver mechanism exists and is documented
- keep the workflow internal-repo friendly
- do not introduce noisy or flaky checks that constantly fail for non-actionable reasons
- if the platform supports GitHub dependency review cleanly, use it
- if a repository/platform limitation prevents that from being reliable, add the strongest stable fallback and document why

### 4. Container builds
Create or reconcile container build flows for:
- web
- api
- workers

Requirements:
- build images deterministically
- support internal-registry tagging conventions
- support PR verification builds without pushing to production tags
- support push/build behavior on main or release branches
- keep runtime images lean and production-appropriate
- do not assume public base-image pulls at runtime after deployment

If Dockerfiles are missing, add them. If they already exist, improve them instead of duplicating them.

### 5. Preview + environment deployment skeleton
Create the minimum viable internal deployment skeleton that later work can extend.

Implement:
- environment-aware deployment workflow structure for `dev`, `staging`, `prod`
- ephemeral preview deployment mechanics for pull requests or branches
- internal namespace or deployment naming convention for previews
- renderable manifests/values/config for previews and named environments
- clear separation of per-environment config
- no public preview exposure assumptions

If the repo already has an `infra` direction, use it.
If not, create a minimal, legible structure under `/infra` that can evolve later.
Helm, Kustomize, or a similarly practical renderable approach is acceptable.
Choose the path that is the simplest long-term fit for this repo.

### 6. Quality-gate documentation
Document:
- what each workflow does
- what blocks merges
- how preview deployments work
- what secrets/variables are expected
- which jobs require self-hosted/internal runners
- how a developer can run the equivalent checks locally
- how `dev`, `staging`, `prod`, and preview differ
- how the setup preserves internal-only posture

## Required deliverables
Create or update the repo so it provides the following CI/CD behaviors:
- pull-request CI
- dependency or supply-chain review
- container-image build verification
- preview deployment scaffolding
- named-environment deployment scaffolding

If GitHub Actions is the chosen path, equivalent workflow files already present in the repo are acceptable:
- `.github/workflows/ci.yml`
- `.github/workflows/dependency-review.yml`
- `.github/workflows/images.yml`
- `.github/workflows/deploy-preview.yml`
- `.github/workflows/deploy-environments.yml`

You may collapse or rename workflows if the resulting structure is clearer, as long as the behaviors above still exist.

### Optional but recommended
- `.github/dependabot.yml`
- root-level `Makefile`, `justfile`, or equivalent developer task entrypoint
- version pin files if helpful and not redundant

### Infrastructure / deployment skeleton
Use existing repo conventions if they exist. Otherwise create the minimum equivalent of:
- `/infra/helm/ukde/**` or `/infra/k8s/**`
- environment values/config for:
  - preview
  - dev
  - staging
  - prod
- image-reference and tag wiring
- internal-registry placeholders
- preview namespace naming strategy
- preview cleanup strategy notes

### Docs
- `README.md`
- `docs/delivery/ci-cd-quality-gates.md`
- `docs/delivery/preview-environments.md`

Reuse existing docs directories if the repo already has a better naming convention.

## Security and governance constraints
You must preserve all of these:
- no uncontrolled public preview environments
- no bypass around the future single export door
- no weakening of the internal-only model execution posture
- no secret sharing across environments
- no hidden environment coupling
- no change to `/phases/**`
- no introduction of external AI API dependencies

## Allowed touch points
You may modify:
- root config files
- `README.md`
- `.github/**`
- `docs/**`
- `infra/**`
- Docker / Compose / container files
- existing app/package scripts when needed to make CI real

You may update `/web`, `/api`, `/workers`, `/packages/ui`, and `/packages/contracts` only if it is strictly necessary to make deterministic builds, tests, or containers real. Do not turn this into a feature-implementation prompt.

Do not modify `/phases/**`.

## Non-goals
Do not do any of the following here:
- real auth or OIDC
- RBAC feature implementation
- audit-event data model implementation
- jobs framework implementation
- export gateway behavior
- ingest, viewer, preprocessing, layout, transcription, or privacy features
- full observability stack
- production cluster provisioning that depends on unavailable secrets
- public cloud preview assumptions
- giant enterprise DevOps scaffolding that adds more weight than leverage

## Quality bar
The result should feel like a serious, secure product repo:
- deterministic
- understandable
- merge-blocking where it should be
- internal-preview aware
- low noise
- durable enough for later work
- not over-engineered

## Validation
Before finishing:
1. Run the local equivalents of the CI jobs you created.
2. Validate workflow YAML syntax as far as practical.
3. Build the web, api, and worker containers locally if the repo/tooling permits.
4. Render or validate the deployment manifests/config for preview/dev/staging/prod.
5. Confirm every workflow references commands and files that actually exist.
6. Confirm docs match the implemented commands and paths.
7. Confirm `/phases/**` is untouched.

If full deployment cannot be executed because secrets or internal infrastructure are unavailable, still validate everything that can be validated locally and make the failure boundary explicit.

## Acceptance criteria
This prompt is complete only if all are true:
- the repo has deterministic CI
- merge-blocking quality gates exist
- dependency/security review gates exist
- web/api/workers container builds exist
- preview deployment scaffolding exists and is internal-only
- `dev`, `staging`, and `prod` deployment structure is explicit
- developers can run local CI-equivalent checks from the repo
- documentation clearly explains the delivery model
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

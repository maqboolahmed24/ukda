# UKDataExtraction (UKDE)

UKDE is a secure, audit-first product for turning difficult archival scans into reviewable transcripts, conservative privacy-safe derivatives, and governed release candidates inside a controlled research environment.

The active build posture is web-first. Product behavior, governance rules, and later-phase intent still live in [`/phases`](./phases), but implementation now proceeds through a browser application, API, workers, shared packages, and infrastructure boundaries defined in this repository.

## What Is Canonical

- Product behavior and phase contracts: [`/phases`](./phases)
- Web-first execution posture: [`/docs/architecture/web-first-execution-contract.md`](./docs/architecture/web-first-execution-contract.md)
- Source-of-truth and prompt execution rules: [`/docs/architecture/source-of-truth-and-conflict-resolution.md`](./docs/architecture/source-of-truth-and-conflict-resolution.md)
- Browser experience contract: [`/docs/design/obsidian-web-experience-blueprint.md`](./docs/design/obsidian-web-experience-blueprint.md)
- Design-system token architecture: [`/docs/design/design-system-token-architecture.md`](./docs/design/design-system-token-architecture.md)
- Theming and preference behavior: [`/docs/design/theming-preference-behavior.md`](./docs/design/theming-preference-behavior.md)
- Auth and session boundary design: [`/docs/architecture/auth-session-boundaries.md`](./docs/architecture/auth-session-boundaries.md)
- Audit event model and integrity baseline: [`/docs/architecture/audit-logging-and-integrity.md`](./docs/architecture/audit-logging-and-integrity.md)
- Observability baseline and operations surfaces: [`/docs/architecture/observability-and-operations.md`](./docs/architecture/observability-and-operations.md)
- Secure-setting enforcement baseline: [`/docs/architecture/secure-setting-enforcement-baseline.md`](./docs/architecture/secure-setting-enforcement-baseline.md)
- Export gateway stub and no-egress posture: [`/docs/architecture/export-gateway-stub-and-no-egress-posture.md`](./docs/architecture/export-gateway-stub-and-no-egress-posture.md)
- Telemetry privacy rules: [`/docs/architecture/telemetry-privacy-rules.md`](./docs/architecture/telemetry-privacy-rules.md)
- Jobs lifecycle and worker runtime: [`/docs/architecture/jobs-framework-and-worker-runtime.md`](./docs/architecture/jobs-framework-and-worker-runtime.md)
- Project workspaces and RBAC boundaries: [`/docs/architecture/project-workspaces-and-rbac.md`](./docs/architecture/project-workspaces-and-rbac.md)
- Authenticated shell layout and adaptive-state contract: [`/docs/architecture/shell-layout-and-adaptive-state.md`](./docs/architecture/shell-layout-and-adaptive-state.md)
- Web primitives and interaction contract: [`/docs/architecture/web-primitives-and-interaction-contract.md`](./docs/architecture/web-primitives-and-interaction-contract.md)
- Overlay and focus-management contract: [`/docs/architecture/overlay-focus-management.md`](./docs/architecture/overlay-focus-management.md)
- Directory ownership and boundaries: [`/docs/architecture/repo-topology-and-boundaries.md`](./docs/architecture/repo-topology-and-boundaries.md)
- Future route and IA contract: [`/docs/architecture/route-map-and-user-journeys.md`](./docs/architecture/route-map-and-user-journeys.md)
- Delivery automation and merge gates: [`/docs/delivery/ci-cd-quality-gates.md`](./docs/delivery/ci-cd-quality-gates.md)
- Internal preview posture: [`/docs/delivery/preview-environments.md`](./docs/delivery/preview-environments.md)
- Local secure development workflow: [`/docs/development/local-secure-dev.md`](./docs/development/local-secure-dev.md)
- Deployment and operations runbooks: [`/docs/runbooks/deployment-runbook.md`](./docs/runbooks/deployment-runbook.md), [`/docs/runbooks/key-rotation-runbook.md`](./docs/runbooks/key-rotation-runbook.md), [`/docs/runbooks/backup-restore-runbook.md`](./docs/runbooks/backup-restore-runbook.md)
- Model service-map foundation: [`/MODEL_STACK.md`](./MODEL_STACK.md)

## Current Topology

- [`/web`](./web): Next.js App Router frontend
- [`/api`](./api): FastAPI service skeleton
- [`/workers`](./workers): queue worker runtime for Phase 0 NOOP jobs
- [`/packages/ui`](./packages/ui): shared tokens and browser primitives bootstrap
- [`/packages/contracts`](./packages/contracts): shared TypeScript contract bootstrap
- [`/infra`](./infra): infrastructure placeholders for containerization and environment separation

The governance posture is unchanged: deny by default, internal-only model execution, append-only audit/evidence intent, and a single export gateway as the only egress path.

## Read Order Before Changing Code

1. [`/phases/README.md`](./phases/README.md)
2. [`/docs/architecture/web-first-execution-contract.md`](./docs/architecture/web-first-execution-contract.md)
3. [`/docs/architecture/source-of-truth-and-conflict-resolution.md`](./docs/architecture/source-of-truth-and-conflict-resolution.md)
4. [`/phases/blueprint-ukdataextraction.md`](./phases/blueprint-ukdataextraction.md)
5. [`/docs/design/obsidian-web-experience-blueprint.md`](./docs/design/obsidian-web-experience-blueprint.md)
6. [`/docs/architecture/repo-topology-and-boundaries.md`](./docs/architecture/repo-topology-and-boundaries.md)
7. [`/docs/architecture/route-map-and-user-journeys.md`](./docs/architecture/route-map-and-user-journeys.md)
8. The phase file or checked prompt you are implementing
9. [`/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`](./phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md) when work touches recall-first behavior, rescue flow, token anchors, search anchoring, conservative masking, or downstream activation

## Prerequisites

- Node.js `24.10.0` or newer
- `pnpm 10.23.0` or newer
- Python `3.12+`

## Install

Install the JS workspace dependencies:

```bash
pnpm install
```

Create and activate a Python virtual environment, then install the editable Python packages:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
make install-python
```

## Run Locally

Start the frontend:

```bash
set -a && source .env && set +a
pnpm dev:web
```

Start local Postgres:

```bash
make dev-db-up
```

Start the API in a second terminal:

```bash
source .venv/bin/activate
set -a && source .env && set +a
cd api
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Inspect worker status:

```bash
source .venv/bin/activate
ukde-worker status
```

Run one worker pass:

```bash
source .venv/bin/activate
ukde-worker run-once
```

The entry resolver route `/` is auth-aware: unauthenticated users go to `/login`, authenticated users go to `/projects`.
The operational diagnostic route is `/health` and reads live status from the API.
Project workspace routes include `/projects/:projectId/overview`, `/projects/:projectId/jobs`, `/projects/:projectId/jobs/:jobId`, `/projects/:projectId/activity`, and permission-scoped `/projects/:projectId/settings`.
Phase 0 export-gateway stubs are visible at `/projects/:projectId/export-candidates`, `/projects/:projectId/export-requests`, and `/projects/:projectId/export-review` and remain intentionally disabled.
Audit routes include `/admin/audit`, `/admin/audit/:eventId`, and current-user `/activity`.
Operations routes include `/admin/operations`, `/admin/operations/slos`, `/admin/operations/alerts`, and `/admin/operations/timelines`.
Security route includes `/admin/security`.
The web app expects the API at `http://127.0.0.1:8000` by default.
Use `NEXT_PUBLIC_UKDE_API_ORIGIN` for browser-visible API URLs and `UKDE_API_ORIGIN_INTERNAL` for server-side fetches (for example `http://api:8000` in containerized smoke mode).

Containerized smoke path:

```bash
make dev-stack-up
```

## Validate

Run the local CI-equivalent quality gates:

```bash
make ci
```

Validate images and deployment manifests:

```bash
make verify-images
make render-manifests
```

Direct JS and Python commands remain available when you want narrower feedback loops.

Validate the shared packages and the web app:

```bash
pnpm typecheck:packages
pnpm typecheck:web
pnpm build:web
pnpm smoke:health
```

Validate the Python services:

```bash
source .venv/bin/activate
python -m pytest api/tests
python -m pytest workers/tests
```

## Auth Development Notes

- Local dev can use explicit seeded identities by setting `AUTH_DEV_MODE_ENABLED=true`.
- Dev seed identities are inserted into `users` automatically in dev mode to make member-management flows testable without a prior login for every fixture user.
- Dev auth is intentionally blocked outside `dev/test`.
- Real OIDC is enabled when `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, and `OIDC_REDIRECT_URI` are all set.
- Session cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` outside local dev.

## Delivery Assets

- GitHub workflows: [`/.github/workflows`](./.github/workflows)
- Helm deployment skeleton: [`/infra/helm/ukde`](./infra/helm/ukde)
- Local runtime stack: [`/docker-compose.yml`](./docker-compose.yml)
- Local CI entrypoint: [`/Makefile`](./Makefile)
- Python CI lock: [`/requirements/python-ci.lock`](./requirements/python-ci.lock)

## Working Rules

- Re-read the repository and relevant source files every turn. Do not rely on chat memory.
- Extend the current repository state instead of recreating parallel scaffolds.
- Keep `/phases` immutable. Translate legacy desktop wording into web-native implementation instead of editing the source canon to fit convenience.
- Use official external docs only for framework, browser, accessibility, and responsive mechanics. They do not override local product rules.

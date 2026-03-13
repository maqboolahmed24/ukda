You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed sources before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first. Treat any other repo docs as implementation context only unless `/phases` explicitly promotes them.

## Mandatory first actions
1. Inspect the relevant repository areas and any existing implementation this prompt may extend.
2. Read these local files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-00-foundation-release.md`
3. If present, also read and reconcile as current repo context only:
   - `README.md`
   - `docs/architecture/web-first-execution-contract.md`
   - `docs/architecture/source-of-truth-and-conflict-resolution.md`
   - `docs/architecture/repo-topology-and-boundaries.md`
   - `docs/architecture/route-map-and-user-journeys.md`
   - `docs/design/obsidian-web-experience-blueprint.md`
4. Only after reading the repo and sources, implement the bootstrap.

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
- Local phase and blueprint documents win for product behavior, workflow semantics, governance, audit constraints, security boundaries, and acceptance logic.
- Official external docs win only for browser mechanics, framework conventions, accessibility semantics, and responsive implementation details.
- If a local document uses desktop-only language, preserve the intent and translate it to a web-native equivalent instead of copying desktop mechanics literally.

## External official reference pack for platform mechanics only
- Next.js App Router:
  - https://nextjs.org/docs/app/getting-started/project-structure
  - https://nextjs.org/docs/app/getting-started/layouts-and-pages
  - https://nextjs.org/docs/app/api-reference/file-conventions/route-groups
  - https://nextjs.org/docs/app/api-reference/file-conventions/loading
  - https://nextjs.org/docs/app/getting-started/error-handling
  - https://nextjs.org/docs/app/getting-started/linking-and-navigating
- FastAPI official docs:
  - https://fastapi.tiangolo.com/
  - https://fastapi.tiangolo.com/tutorial/bigger-applications/
  - https://fastapi.tiangolo.com/advanced/settings/
  - https://fastapi.tiangolo.com/tutorial/testing/
  - https://fastapi.tiangolo.com/deployment/docker/
- Accessibility and responsive behavior:
  - https://www.w3.org/TR/WCAG22/
  - https://www.w3.org/WAI/ARIA/apg/
  - https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Media_queries/Using
  - https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-color-scheme
  - https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-contrast
  - https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-motion
  - https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-transparency

## Objective
Bootstrap the real web-first monorepo and target directory topology for UKDE so the repository is ready for iterative end-to-end implementation.

Create the actual top-level structure and starter applications/services for:
- `/web` — Next.js App Router + React + TypeScript browser frontend
- `/api` — FastAPI backend
- `/workers` — background worker/runtime package
- `/packages/ui` — shared web design primitives/tokens bootstrap
- `/packages/contracts` — shared typed contracts/bootstrap package
- `/infra` — infrastructure skeleton and operational placeholders

This prompt should create a clean, runnable foundation. It should not yet implement Phase 1 ingest features or later workflow features. Keep the scaffold sharp, calm, secure-minded, and extensible.

## Architectural intent you must preserve
- audit-first product posture
- deny-by-default mindset
- internal-only model execution posture
- single future export gateway as the only egress door
- browser-first product surface with FastAPI backend
- premium dark, minimal, serious UI direction
- adaptive, deep-linkable app architecture prepared for future review workspaces

## Stack decisions for this bootstrap
Unless the repo already pins something compatible, use:
- `pnpm` workspaces for JS/TS package management
- Next.js App Router + React + TypeScript under `/web`
- FastAPI under `/api`
- Python package under `/workers`
- lightweight root-level workspace configuration that is easy to understand and not over-engineered

Keep the bootstrap simple. Do not introduce complexity that is not buying immediate leverage.

## Implementation scope
Implement a repository bootstrap that includes:
1. Root workspace/package management setup.
2. Basic repo hygiene/config files.
3. Real directory skeletons for web, api, workers, shared packages, and infra.
4. Minimal but consistent starter code in each area.
5. A dark, restrained, browser placeholder experience in `/web` that already reflects the intended product tone without pretending the product is finished.
6. A minimal FastAPI app structure in `/api` using an app-factory style or similarly clean modular entrypoint.
7. A worker package structure in `/workers` prepared for later job execution work.
8. Shared-package scaffolds for UI and contracts that later work can build on.
9. Clear local developer instructions in the README and/or a dedicated bootstrap doc.

## Required deliverables
Create or update the repository so it contains at least the following, unless the repo already has a compatible existing structure:

### Root
- `package.json`
- `pnpm-workspace.yaml`
- `tsconfig.base.json`
- `.gitignore`
- `.editorconfig`
- optional minimal formatting/lint config only if needed to support the scaffold cleanly
- updated `README.md`

### `/web`
Create a real Next.js App Router app with TypeScript, including at minimum:
- `package.json`
- `app/layout.tsx`
- `app/page.tsx`
- `app/loading.tsx`
- `app/error.tsx`
- `app/globals.css`
- any supporting config files needed for a normal modern Next.js app

The frontend starter must:
- be dark-first by default
- feel calm, elegant, minimal, and professional
- avoid marketing-site fluff and avoid “AI assistant” styling
- use semantic HTML landmarks
- include an obvious shell placeholder that can later become the real product shell
- be prepared for future deep-linkable workspaces
- keep copy terse and product-grade

### `/api`
Create a real FastAPI starter with a modular structure, including at minimum:
- `pyproject.toml`
- `app/main.py`
- `app/core/config.py` or equivalent settings module
- `app/api/` router structure
- a minimal importable app entrypoint
- a small starter route or metadata endpoint so the service can boot meaningfully

Do not implement auth, RBAC, DB persistence, or job execution yet unless a small placeholder is strictly needed to make the scaffold consistent.

### `/workers`
Create a worker/runtime bootstrap with at minimum:
- `pyproject.toml`
- package/module structure for future queue/job execution
- a minimal CLI or entrypoint stub
- clear placeholder boundaries for future worker responsibilities

### `/packages/ui`
Create a shared UI bootstrap package with at minimum:
- package config
- minimal token/bootstrap exports or shared styling primitives that the web app can consume today
- structure that can later grow into the real design system without being rebuilt

Keep it intentionally small in this prompt. Do not build the full component system yet.

### `/packages/contracts`
Create a shared contracts/bootstrap package with at minimum:
- package config
- placeholder shared type exports and structure for future contracts
- clear note that richer API contracts and schemas can be added later

### `/infra`
Create infrastructure skeleton directories and README-level placeholders only. Do not fully implement deployment yet.
The structure should clearly anticipate:
- containerization
- environment separation (`dev`, `staging`, `prod`)
- future secure deployment manifests/config

## Allowed touch points
You may modify:
- root workspace/config files
- `README.md`
- `docs/**`
- `/web/**`
- `/api/**`
- `/workers/**`
- `/packages/ui/**`
- `/packages/contracts/**`
- `/infra/**`

Do not modify `/phases/**`.
Do not implement real auth, project RBAC, audit ledger, jobs, storage, model routing, or export flows yet. Later prompts own those.

## Non-goals
Do not do any of the following in this prompt:
- full CI/CD pipelines
- full local secure-environment orchestration
- OIDC/SSO integration
- DB migrations and real persistence layers
- job queue implementation
- real observability stack
- ingest/document viewer/product workflows
- full component library
- fake polished product screens that hide the fact this is still a bootstrap

## UI/UX direction for the frontend scaffold
Even at bootstrap stage, the frontend must signal the final product taste:
- sleek dark tone
- minimal surfaces
- sharp spacing and strong hierarchy
- accessible focus treatment
- subdued motion or no motion at all
- serious research-tool mood, not startup landing page mood
- straight, uncluttered user journey
- visible room for future shell, page header, workspace body, and inspector patterns

A plain ugly scaffold is not acceptable. A flashy gimmick is also not acceptable. Aim for composed, restrained, premium utility.

## Developer-experience expectations
The repo should be understandable by the next coding agent at a glance.
Set up scripts or commands so a developer can clearly see how to:
- install JS/TS dependencies
- run the frontend
- run the API
- run the worker stub
- run the available validations/tests

Prefer obvious commands and obvious folder boundaries over cleverness.

## Validation
Run the strongest validations that are reasonable for this bootstrap. At minimum:
1. Verify the Next.js app installs and builds or typechecks successfully.
2. Verify the FastAPI app imports and the starter tests pass.
3. Verify the worker stub imports and its starter tests pass.
4. Verify internal imports/aliases across shared packages resolve.
5. Verify the README instructions match the actual created commands.

If you introduce tests, keep them lightweight and meaningful. Smoke-level confidence is enough for this prompt.

## Acceptance criteria
This prompt is complete only if all are true:
- the target top-level repo topology now exists
- `/web` is a real Next.js App Router app
- `/api` is a real FastAPI app skeleton
- `/workers` contains a runnable worker scaffold with an entrypoint, dependency manifest, and documented start command
- `/packages/ui` and `/packages/contracts` exist and are consumable
- the frontend consumes shared `/packages/ui` tokens/primitives in the rendered shell, with no separate default token path as primary
- root documentation defines ownership and extension points for `/web`, `/api`, `/workers`, and `/packages`
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions or follow-up risks

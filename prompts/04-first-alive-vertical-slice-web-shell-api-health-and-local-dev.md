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
3. If present, also review only the current repo materials that are relevant to this prompt as implementation context:
   - `README.md`
   - the most relevant docs under `docs/architecture/**`, `docs/design/**`, and `docs/delivery/**`
   - the current `/web`, `/api`, `/workers`, `/packages/ui`, `/packages/contracts`, and `/infra` entry points
   - any existing CI/CD and local-dev docs or scripts already present in the repo
4. Reconcile with the current repo state. Do not duplicate scaffolds or create parallel architecture.

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
- Local phase contracts win for product behavior, workflow semantics, governance, audit posture, security boundaries, and acceptance logic.
- Official external docs win only for web-platform mechanics, Next.js file conventions, FastAPI structuring/settings/testing, Docker Compose mechanics, and browser accessibility semantics.
- If a local document uses older desktop-oriented language, preserve the intent and translate it into browser-native patterns instead of copying desktop mechanics literally.

## External official reference pack for platform mechanics only
Use these only for platform mechanics. Do not let them override UKDE product rules.

### Next.js
- https://nextjs.org/docs/app/getting-started/project-structure
- https://nextjs.org/docs/app/getting-started/layouts-and-pages
- https://nextjs.org/docs/app/api-reference/file-conventions/loading
- https://nextjs.org/docs/app/getting-started/error-handling
- https://nextjs.org/docs/app/getting-started/linking-and-navigating
- https://nextjs.org/docs/app/guides/environment-variables
- https://nextjs.org/docs/app/getting-started/deploying
- https://nextjs.org/docs/app/guides/self-hosting

### FastAPI
- https://fastapi.tiangolo.com/tutorial/bigger-applications/
- https://fastapi.tiangolo.com/advanced/settings/
- https://fastapi.tiangolo.com/tutorial/testing/
- https://fastapi.tiangolo.com/advanced/testing-events/
- https://fastapi.tiangolo.com/deployment/docker/

### Docker Compose
- https://docs.docker.com/compose/
- https://docs.docker.com/compose/gettingstarted/

### Accessibility and web interaction
- https://www.w3.org/TR/WCAG22/
- https://www.w3.org/WAI/ARIA/apg/
- https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/
- https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Media_queries/Using
- https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-color-scheme
- https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-contrast
- https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-motion
- https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-transparency
- https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/forced-colors

## Objective
Complete the first working Phase 0 Iteration 0.1 vertical slice for the web-first system.

This prompt must make the product feel genuinely alive from browser to API while staying within the Phase 0.1 boundary:
- a real FastAPI health surface
- a real readiness check that depends on the database
- a real browser shell that uses the shared dark design language
- a real safe diagnostic route that renders live service status from the API, not hardcoded copy
- a lightweight root route that behaves as an entry resolver rather than a faux dashboard
- a real `/login` placeholder route
- a real internal component-gallery scaffold at `/admin/design-system`
- real local environment wiring for web, api, db, and model-service-map foundation
- a clean local developer workflow on macOS-friendly web-first tooling

Do not pretend later product workflows already exist.

## Phase alignment you must preserve
From Phase 0 Iteration 0.1, this work must support:
- app shell foundation with header, navigation-rail slot, content host, deployment-environment badge, and project access-tier badge placeholder
- shared `/packages/ui` token system for Colors, Typography, Spacing, Shape, Elevation, and Motion
- dark by default, light supported, browser preference aware
- adaptive layout states `Expanded | Balanced | Compact | Focus`
- `/login` placeholder
- `/` is a lightweight entry route that resolves to `/login` until auth-aware redirects are available, and later redirects unauthenticated users to `/login` and authenticated users to `/projects`
- `/health` displays live service status from `/healthz`
- internal component gallery scaffold at `/admin/design-system`
- `/healthz` liveness
- `/readyz` DB readiness
- local development profile validates the role-to-service map against a role-isolated model root outside the repository
- keyboard-only navigation works in shell and login placeholders
- theme switching is functional and persisted
- browser accessibility baseline scan passes on shell and login placeholders

## Web UX non-negotiables
The frontend must already show the intended product taste:
- dark-first
- minimal
- calm
- serious
- premium utility, not startup marketing
- no fake desktop chrome
- no “AI assistant” visual tropes
- strong hierarchy
- strong visible focus
- bounded, structured surfaces
- clear object focus
- straight-line user journey

The root route is not a dashboard gimmick. It is a lightweight entry resolver. The safe operational health UI lives at `/health`.

## Implementation scope

### 1. API health and readiness
Implement or refine the FastAPI service so it has:
- `GET /healthz`
  - returns `200`
  - returns a clean, typed payload useful to the browser diagnostic route
  - includes at least service identity and status
- `GET /readyz`
  - performs a real DB readiness check
  - returns non-success when the DB is unavailable
  - is tested
- clean modular app structure using a settings module
- startup/readiness logic that is easy for later work to extend

If the current repo uses SQLite or a fake DB stub, move toward a real Postgres-friendly readiness path aligned with future phases.

### 2. Environment and configuration wiring
Implement the Phase 0 configuration foundation cleanly.
Support and document at least:
- `APP_ENV` or equivalent environment selector
- `DATABASE_URL`
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `MODEL_DEPLOYMENT_ROOT`
- `MODEL_ARTIFACT_ROOT`
- `MODEL_CATALOG_PATH`
- `MODEL_ALLOWLIST`
- `MODEL_SERVICE_MAP_PATH`
- `MODEL_WARM_START`

Use practical settings management.
Do not make external model calls.
Do not require public network access.

### 3. Model service map foundation
Phase 0.1 requires an approved internal model-service-map posture even before later ML-heavy prompts.

Implement the minimum viable foundation:
- a starter model catalog/config path
- a starter model-service-map config path
- validation that the config is structurally sound
- validation that configured roots/paths are internal and outside the repo where required
- no runtime public model pulls
- no direct dependency on external AI APIs

For local macOS development, you may document
`~/Library/Application Support/UKDataExtraction/models`
as an example default when appropriate.

For staging/prod guidance, you may document
`/srv/ukdataextraction/models`
as a typical server-side example root.

Keep model roots configurable rather than treating these example paths as universal truth.

If `MODEL_STACK.md` does not yet exist and no existing doc already covers the same material, you may create it as an implementation reference that captures:
- approved starter model roles from Phase 0.1
- service-map concept
- replacement rules
- local vs cluster artefact roots
- internal-only execution posture
- no public runtime pulls

Treat `MODEL_STACK.md` as operational guidance, not as canonical product truth.
Do not invent later-phase ML orchestration here. This is a foundation note and validation layer only.

### 4. Local secure development workflow
Create a developer workflow that is obvious and reproducible on a MacBook-oriented web dev setup.

Implement:
- `.env.example` or equivalent example env files
- a one-command or one-obvious-entry local startup path
- a local DB service for readiness checks
- a fast host-native dev path where practical
- a containerized smoke path where practical
- docs that explain how to start, test, and stop the local stack

Using Docker Compose for the DB and optional supporting services is acceptable and encouraged if it keeps local startup obvious.

Do not overbuild local infrastructure.
DB is mandatory.
Object storage placeholder is optional only if appropriate and if it supports future phases without forcing new structure.

### 5. Browser shell, entry route, and diagnostic route
Implement or refine the `/web` app so that it has:
- a real browser-native root shell
- semantic landmarks
- header/title area
- navigation rail slot
- content host
- deployment-environment badge
- project access-tier badge placeholder
- page header region
- future-ready structure for deep-linkable workspaces

The root route `/` must:
- behave as an entry resolver, not a fake dashboard
- redirect safely toward `/login` in the pre-auth Phase 0 posture
- remain easy to evolve into the later auth-aware redirect contract

The diagnostic route `/health` must:
- fetch from the API, not hardcode
- visibly show the current service status when healthy
- feel like part of a serious operational system
- not look like a toy, splash page, or investor deck

### 6. Login placeholder
Create or refine `/login` so it:
- clearly signals the future secure-entry route
- is keyboard-safe
- matches the Obsidian visual language
- does not fake a full auth implementation yet

No OIDC implementation in this prompt.
That comes later.

### 7. Internal design-system gallery scaffold
Create or refine `/admin/design-system` so it demonstrates the Phase 0 shell/UI foundations:
- color/surface tokens
- typography and spacing
- environment badge and tier badge patterns
- focus states
- command bar / toolbar sample
- shell primitives
- adaptive state examples or diagnostics for `Expanded | Balanced | Compact | Focus`

This route is an internal product route, not a public marketing showcase.
It can be a scaffold, but it must be real and useful.

### 8. Shared UI package refinement
Strengthen `/packages/ui` so it is actually the canonical source for:
- color tokens
- spacing
- typography
- radius/shape
- elevation
- motion
- theme variables
- focus styling primitives

Use browser-native theming via CSS custom properties or an equally practical typed-token approach.
Do not build the entire future component library yet.
Do build enough shared foundation so the shell and gallery are clearly using the same system.

### 9. Theme, preference, and adaptive-state behavior
Implement real behavior for:
- default dark theme
- light theme support
- persisted theme preference
- sync with browser/user preferences where appropriate
- `prefers-color-scheme`
- `prefers-contrast`
- `forced-colors`
- `prefers-reduced-motion`
- `prefers-reduced-transparency`

Implement the adaptive shell-state model:
- `Expanded`
- `Balanced`
- `Compact`
- `Focus`

The implementation can be heuristic and lightweight at this stage, but it must be explicit, testable, and already shaping the shell.

### 10. Testing and gates
Implement the strongest realistic Phase 0.1 tests/gates for this slice.

At minimum:
- backend unit tests:
  - `/healthz` returns `200`
  - `/readyz` fails if DB is not reachable
- backend integration path:
  - API starts against a local integration DB or ephemeral test DB
  - model-service-map validation works in local profile
- web/e2e smoke:
  - open `/health` and verify that it renders live service status from the API
- web surface gates:
  - keyboard-only navigation works in shell and login placeholders
  - theme switching is functional and persisted
  - browser contrast / forced-colors safe behavior is not broken
  - adaptive state transitions do not collapse the layout
- accessibility baseline:
  - run a practical accessibility scan on the shell and login routes if the repo can support it cleanly

Keep tests stable. Avoid flaky novelty.

## Required deliverables

### API
- `/api/app/main.py`
- `/api/app/core/config.py` or equivalent
- `/api/app/api/**`
- DB readiness support
- health/readiness tests

### Web
- `/web/app/layout.tsx`
- `/web/app/page.tsx`
- `/web/app/login/page.tsx`
- `/web/app/admin/design-system/page.tsx`
- `/web/app/loading.tsx`
- `/web/app/error.tsx`
- `/web/app/globals.css`
- theme/adaptive-state plumbing
- browser-safe API wiring

### Shared packages
- `/packages/ui/**`
- `/packages/contracts/**` for any shared health/status contracts that help keep web/api aligned

### Local-dev / infra / docs
- `.env.example` or equivalent env example files
- local Compose / local-dev scripts if needed
- `MODEL_STACK.md` if absent
- `README.md`
- `docs/development/local-secure-dev.md`

Reuse existing naming and structure if the repo already has a better pattern. Do not create redundant parallel systems.

## Allowed touch points
You may modify:
- `README.md`
- `docs/**`
- `MODEL_STACK.md`
- root env/config/task files
- `/web/**`
- `/api/**`
- `/packages/ui/**`
- `/packages/contracts/**`
- `/infra/**` or local-dev config files
- `/workers/**` only if a small adjustment is required for local stack coherence

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following in this prompt:
- real OIDC / SSO
- session management
- RBAC feature flows
- projects and memberships
- audit-log product surfaces
- job framework
- export gateway behavior
- ingest, viewer, preprocessing, layout, transcription, privacy, provenance, or discovery features
- public release pages
- fake polished screens that hide the fact this is still the Phase 0.1 alive slice

## Quality bar
The result must feel composed and intentional.
A plain ugly scaffold is not acceptable.
A flashy or noisy scaffold is also not acceptable.

Aim for:
- sleek dark tone
- restrained surfaces
- strong spacing discipline
- calm typography
- crisp hierarchy
- serious research-tool mood
- obvious future shell evolution
- practical accessibility from day one

## Validation
Before finishing:
1. Run the local dev startup path and confirm the vertical slice actually comes alive.
2. Verify `/healthz` and `/readyz` behavior.
3. Verify the root route behaves as the lightweight entry resolver and the `/health` route shows live API health, not hardcoded text.
4. Run backend tests.
5. Run web build/typecheck/test as appropriate.
6. Run e2e smoke for the diagnostic route if the harness exists or is added.
7. Verify theme persistence and shell behavior manually or via tests.
8. Verify docs match actual commands and paths.
9. Confirm `/phases/**` is untouched.

If some full validation step cannot run because of missing local infrastructure, still validate everything possible and report the hard boundary clearly.

## Acceptance criteria
This prompt is complete only if all are true:
- `/healthz` is real
- `/readyz` performs a real DB readiness check
- local environment wiring is clear and documented
- model-service-map foundation exists and is validated without external calls
- `/` behaves as the lightweight entry resolver and `/health` shows live service status from the API
- `/login` exists and returns an authenticated-placeholder screen with deterministic copy and no TODO-only content
- `/admin/design-system` exists as a real internal scaffold
- `/packages/ui` is actually shaping the shell
- dark/light/preference behavior is real
- adaptive shell states implement deterministic empty/loading/error/success behavior with validation coverage
- local startup docs include exact macOS commands for web, api, and db, plus expected ready signals
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

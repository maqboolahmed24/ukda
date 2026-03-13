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
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-01-ingest-document-viewer-v1.md` for the authenticated route contract and shell ownership only
3. Then review the current repo implementation context generally — existing code, configs, docs, scripts, tests, and implementation notes already present in the repo — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create parallel auth systems, duplicate route guards, or conflicting session models.

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
- The `/phases` documents win for identity posture, RBAC intent, governance boundaries, route ownership, and acceptance logic.
- Official docs win only for implementation mechanics such as App Router auth patterns, OIDC protocol handling, FastAPI middleware/security behavior, and browser-safe session handling.
- If a local phase document uses older desktop-oriented language, preserve the intent and translate it into a browser-native implementation.

## External official reference pack for mechanics only
Use only official docs, and only for implementation mechanics.

### Next.js
- https://nextjs.org/docs/app/guides/authentication
- https://nextjs.org/docs/app/guides/backend-for-frontend
- https://nextjs.org/docs/app/api-reference/functions/redirect
- https://nextjs.org/docs/app/api-reference/file-conventions/proxy
- https://nextjs.org/docs/app/getting-started/layouts-and-pages

### FastAPI
- https://fastapi.tiangolo.com/tutorial/security/
- https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- https://fastapi.tiangolo.com/tutorial/middleware/
- https://fastapi.tiangolo.com/advanced/response-cookies/
- https://fastapi.tiangolo.com/tutorial/testing/

### OIDC
- https://openid.net/specs/openid-connect-core-1_0-final.html

### Accessibility
- https://www.w3.org/TR/WCAG22/
- https://www.w3.org/WAI/ARIA/apg/

## Objective
Implement Phase 0 Iteration 0.2 authentication, session boundaries, and role-aware route guards for the web-first system.

This prompt owns:
- real authentication integration surface
- secure browser-safe session boundaries
- identity persistence
- deny-by-default protection on all protected routes
- reusable authorization and route-guard primitives
- a real login/callback/logout flow
- dev-safe local authentication for implementation and testing
- protection of the browser app, API routes, and admin surfaces

This prompt does not own:
- full project creation and membership UX
- full project workspace implementation
- full append-only audit system
- full observability platform
- jobs, ingest, preprocessing, layout, transcription, privacy, governance, export, or discovery features

## Phase alignment you must preserve
From Phase 0 Iteration 0.2 and the authenticated route contract:
- OIDC integration is the intended real authentication model
- stable `sub` identity key is required
- session boundary must be secure and browser-safe
- unauthenticated users are redirected to `/login` or rejected with `401` as appropriate
- all protected routes are deny-by-default
- the browser route contract includes `/`, `/login`, `/auth/callback`, `/logout`, `/projects`, and `/admin`
- authenticated users landing on `/` should end up at `/projects`
- unauthenticated users landing on `/` should end up at `/login`
- `ADMIN` and `AUDITOR` are platform roles, not ordinary project memberships
- platform-role override is explicit, not implicit
- no tokens in local storage or casual client-side state

## Security non-negotiables
- Do not store bearer tokens in `localStorage`, `sessionStorage`, or client-visible browser state.
- Prefer a server-mediated session boundary using secure `HttpOnly` cookies or an equally safe current-repo pattern.
- If cookies are used for session state, implement CSRF protection for state-changing operations.
- Session settings must be hardened:
  - `HttpOnly`
  - `Secure` outside local dev
  - appropriate `SameSite`
  - clear expiration and renewal behavior
- Auth failures must fail closed.
- Dev auth must be impossible to enable accidentally in staging or production.
- Route protection must not rely on client-only checks.

## Implementation scope

### 1. Identity and session foundation
Implement or refine the identity foundation in the backend.

At minimum, support:
- `users` table with:
  - `id`
  - `oidc_sub`
  - `email`
  - `display_name`
  - `created_at`
  - `last_login_at`
- platform-role storage if absent, or reconcile with the current repo's equivalent:
  - `user_platform_roles`
    - `user_id`
    - `role` (`ADMIN` | `AUDITOR`)
- a secure session model consistent with the current repo and Phase 0 intent

Use the least disruptive secure model for the current repo, but preserve:
- short-lived browser-facing session boundary
- server-side verification
- explicit logout
- revocation or invalidation path
- no client-visible secret material

### 2. Real auth integration plus explicit dev mode
Implement the real auth entry surface around OIDC, plus a clearly separated dev-only auth mode for local implementation and tests.

Requirements:
- support real OIDC configuration when environment variables are present
- support a dev-only login path when running locally and explicitly enabled
- dev auth must use seeded identities and role fixtures
- dev auth must go through the same session issuance and route-guard path as real auth as much as practical
- staging/prod must hard-fail if dev auth is enabled

Add or document the minimal env/config required for a real OIDC path, such as:
- issuer URL
- client ID
- client secret
- redirect URI
- scopes
- post-login redirect path
- post-logout redirect path
- dev-auth enable flag and seeded identity config

Do not build a fake “OAuth-like” toy flow that diverges from the real session model.

### 3. API auth enforcement and authorization primitives
Implement or refine API-side security so that:
- all routes except health and the minimal auth handshake routes require authentication
- unauthenticated requests receive `401`
- invalid session or invalid token state is rejected
- current-user resolution is centralized
- authorization checks are reusable and composable
- platform-role guards exist now
- project-role guard primitives can already be declared even if full project membership logic is implemented later in dedicated workspace-scoped work

Guard requirements:
- deny-by-default
- explicit declaration per route
- platform-role override only where a route explicitly opts in
- no accidental admin bypass for ordinary member-scoped project routes

### 4. Web route guards and login/logout flows
Implement or refine the browser flow for:
- `/`
- `/login`
- `/auth/callback`
- `/logout`

Requirements:
- `/` redirects unauthenticated users to `/login`
- `/` redirects authenticated users to `/projects`
- protected route groups are enforced server-side, not only in the client
- `/admin/design-system` and any other existing internal admin routes are protected with the correct platform-role boundary
- if `/projects` is not yet real, keep a minimal protected placeholder that later workspace-scoped work can build on
- login and logout behavior must be predictable, minimal, and restrained in tone

Use the App Router protection pattern that best suits the repository:
- server-side layout guards
- request-bound auth helpers
- `proxy.ts` / equivalent only when it improves correctness and keeps the auth boundary simpler
Do not introduce a brittle dual-guard system.

### 5. Shared contracts and UI alignment
Use `/packages/contracts` and `/packages/ui` where appropriate so the auth layer is not hardcoded ad hoc inside one app.

At minimum:
- centralize session/current-user response types
- centralize role enums if not already present
- keep the login and protected-shell UI aligned with the existing Obsidian dark system
- preserve keyboard-first behavior and visible focus treatment
- avoid generic SaaS or “AI assistant” login styling

The login route should feel calm, premium, and secure:
- dark-first
- restrained
- minimal copy
- clear primary action
- explicit environment awareness if useful
- no fake marketing section
- no ornamental illustrations

### 6. Required browser and API surfaces

#### Web
- `/web/app/page.tsx` or equivalent root redirect behavior
- `/web/app/login/page.tsx`
- `/web/app/auth/callback/**`
- `/web/app/logout/**`
- protected authenticated layout or route-group guard
- minimal protected `/projects` placeholder only if needed for a valid post-login landing
- guard protection on existing admin/internal routes

#### API
- auth/session modules
- current-user dependency/helper
- route-guard helpers
- auth callback/session exchange support if the architecture places it in the API
- logout/session invalidation support
- session/current-user endpoint if helpful to keep web and API aligned

#### Docs / config
- `.env.example` or equivalent auth-related env examples
- auth/session design doc
- local dev auth instructions

## Allowed touch points
You may modify:
- `/web/**`
- `/api/**`
- `/packages/contracts/**`
- `/packages/ui/**`
- root env/config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

You may create a minimal `/projects` protected placeholder only if needed to complete the real auth flow.
Do not turn this into full project workspace implementation. That is outside this prompt's scope.

## Non-goals
Do not implement any of the following here:
- project creation and full membership management
- jobs and workers
- append-only audit storage beyond the thinnest hook abstraction needed for later audit-focused work
- full RBAC-backed settings pages
- ingest, viewer, preprocessing, layout, transcription, privacy, manifest, policy, export, provenance, search, or discovery features
- public registration or public self-service account creation
- a fake polished auth demo disconnected from real route protection

## Testing and validation
Before finishing:
1. Run backend tests for unauthenticated rejection and invalid-session rejection.
2. Test the protected route boundary for `/`, `/projects`, and at least one `/admin` route.
3. Verify login and logout flows in dev mode.
4. Verify secure session flags and expiration behavior.
5. Verify CSRF protection if cookie sessions are used.
6. Verify dev auth is gated to local/dev only.
7. Verify docs match the implemented commands and environment variables.
8. Confirm `/phases/**` is untouched.

At minimum, cover:
- unauthenticated protected request -> rejected
- invalid token/session -> rejected
- authenticated request -> current user resolved
- authenticated `/` -> `/projects`
- unauthenticated `/` -> `/login`
- unauthorized user cannot open protected admin surface

## Acceptance criteria
This prompt is complete only if all are true:
- real authentication integration surface exists
- secure session boundaries exist
- all protected routes fail closed
- browser route guards are real and server-side
- `/login`, `/auth/callback`, and `/logout` are consistent and working
- dev auth exists but is safely isolated
- admin/internal route protection respects platform roles
- `/projects` exists at least as a real protected landing route if the full workspace is not built yet
- server-side session checks and route-guard redirects behave consistently across all protected routes
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

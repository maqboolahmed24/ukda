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
   - `/phases/phase-01-ingest-document-viewer-v1.md` for the authenticated route map, shell structure, and project-scoped navigation contract
3. Then review the current repo implementation context generally — existing code, configs, docs, scripts, tests, and implementation notes already present in the repo — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not duplicate shells, project models, or route structures.

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
- `/phases` wins for project semantics, membership semantics, RBAC intent, route ownership, access-tier meaning, and acceptance logic.
- Official docs win only for App Router, FastAPI, form handling, layout, navigation, and accessibility mechanics.
- Preserve the intent of any older desktop wording, but implement it as a browser-native workspace.

## External official reference pack for mechanics only
Use only official docs, and only for implementation mechanics.

### Next.js
- https://nextjs.org/docs/app/getting-started/project-structure
- https://nextjs.org/docs/app/getting-started/layouts-and-pages
- https://nextjs.org/docs/app/getting-started/linking-and-navigating
- https://nextjs.org/docs/app/getting-started/fetching-data
- https://nextjs.org/docs/app/api-reference/file-conventions/route-groups
- https://nextjs.org/docs/app/getting-started/error-handling

### FastAPI
- https://fastapi.tiangolo.com/tutorial/bigger-applications/
- https://fastapi.tiangolo.com/advanced/settings/
- https://fastapi.tiangolo.com/tutorial/testing/

### Accessibility
- https://www.w3.org/TR/WCAG22/
- https://www.w3.org/WAI/ARIA/apg/

## Objective
Implement project workspaces, memberships, and navigation boundaries that respect RBAC end to end.

This prompt owns:
- project and membership persistence
- project creation
- project listing and switching
- project-scoped layouts and route boundaries
- membership management
- role-aware navigation visibility
- project access-tier badges and purpose-aware creation flow
- attachment of the current seeded baseline privacy policy snapshot when a project is created

This prompt does not own:
- full append-only audit logging
- full observability platform
- jobs framework
- ingest features
- privacy-policy authoring
- export flows

## Phase alignment you must preserve
From Phase 0 Iteration 0.2 and the Phase 1 route contract:
- a user can authenticate, create a project, and RBAC is enforced for every protected route
- `projects` must include:
  - `id`
  - `name`
  - required `purpose`
  - `status` (`ACTIVE | ARCHIVED`)
  - `created_by`
  - `created_at`
  - required `intended_access_tier` (`OPEN | SAFEGUARDED | CONTROLLED`)
  - required `baseline_policy_snapshot_id`
- `project_members` must support:
  - `project_id`
  - `user_id`
  - `role`
- project roles are:
  - `PROJECT_LEAD`
  - `RESEARCHER`
  - `REVIEWER`
- platform governance roles remain separate from project membership
- platform-role override is explicit, not implicit
- `/projects` is the authenticated landing area
- authenticated project route ownership includes:
  - `/projects`
  - `/projects/:projectId/overview`
  - `/projects/:projectId/jobs`
  - `/projects/:projectId/activity`
  - `/projects/:projectId/settings`
- side navigation is link-only, permission-aware, and shallow
- header shows product identity, project switcher, environment label, access-tier badge, help entry, and user menu
- no CTA stuffing in the global header
- settings visibility is permission-based

## RBAC rules you must enforce now
- ordinary project routes require project membership unless the route explicitly declares a platform-role override
- `RESEARCHER` cannot manage members
- `REVIEWER` cannot manage members
- `PROJECT_LEAD` can add, remove, and change member roles within the project
- `ADMIN` can access explicitly designated admin/governance surfaces and may access project settings where Phase 1 explicitly allows it
- `AUDITOR` is read-only and only on explicitly designated governance/compliance surfaces; do not grant it implicit access to ordinary project workspaces
- navigation must reflect authorization rather than teasing inaccessible sections

## Implementation scope

### 1. Data model and seeded baseline attachment
Implement or refine the backend data model for:
- projects
- memberships
- platform roles if still missing
- baseline privacy policy snapshot attachment required for project creation

You are not building the full Phase 7 policy engine here.
You are building the minimum viable seeded baseline snapshot foundation required by Phase 0 project creation.

Requirements:
- seed a current baseline policy snapshot in a stable, read-only way if it does not exist yet
- attach the current baseline snapshot ID to new projects
- do not build a full policy authoring UI
- keep the seed deterministic and documented

### 2. Project and membership APIs
Implement or refine consistent project APIs, using the current repo's naming conventions where reasonable.

At minimum support:
- list my projects or memberships
- create project
- read project summary
- list project members
- add member
- change member role
- remove member

Requirements:
- validate role changes
- validate access-tier input
- prevent duplicate memberships
- create the creator's initial membership as `PROJECT_LEAD`
- apply authorization checks centrally
- keep response contracts typed and consistent with `/packages/contracts` when useful

### 3. Project shell and route structure
Implement or refine the browser project workspace structure so it feels like the real system, not a placeholder.

- `/web/app/(authenticated)/projects/page.tsx`
- `/web/app/(authenticated)/projects/[projectId]/layout.tsx`
- `/web/app/(authenticated)/projects/[projectId]/overview/page.tsx`
- `/web/app/(authenticated)/projects/[projectId]/activity/page.tsx`
- `/web/app/(authenticated)/projects/[projectId]/settings/page.tsx`

You may add nested settings/member routes if they suit the repository better, but preserve the URL contract and ownership.

Requirements:
- the projects index must show only the current user's memberships
- the current project layout must have:
  - header context
  - left navigation
  - page header region
  - content host
- the shell must use the shared dark system
- project switcher must feel like a real internal tool, not a consumer-app menu
- empty state and first-project state must be clear and calm

### 4. Membership management UX
Build the member-management flow for `PROJECT_LEAD` and `ADMIN`.

Requirements:
- members list
- add-member flow
- role-change flow
- remove-member flow
- read-only or hidden controls for unauthorized roles
- strong visible role/status presentation
- clear guardrails around privileged actions
- no noisy modal carnival; use restrained dialogs or dedicated panels

Use the UX pattern that best suits the repository:
- dedicated settings members section
- list + details
- restrained dialogs for add/remove confirmation
- keyboard-safe focus handling

### 5. Navigation Boundaries That Respect RBAC
The navigation itself must understand authorization.

Implement:
- project left-nav items:
  - Overview
  - Documents
  - Jobs
  - Activity
  - Settings (permission-based)
- hidden or disabled settings entry for unauthorized users, with a preference for hidden over teasing inaccessible control unless the current UX pattern clearly benefits from explanation
- route-level and layout-level guards enforce the same authorization decision for the same route and role
- unauthorized state handling that is serious and clear, not dramatic

You do not need to implement full Documents or Jobs product features here.
Those routes can be present as structured placeholders if later work owns the real feature work.

### 6. Shared contracts, badges, and shell refinement
Strengthen shared packages where it simplifies the repo:
- project role enums
- access-tier enums
- project summary/member DTOs
- access-tier badge patterns
- environment badge patterns if not already stable
- project switcher primitives if they belong in shared UI

The UI must remain:
- dark-first
- minimal
- dense but calm
- high-trust
- serious research-tool tone
- non-marketing
- non-AI-ish

### 7. Seed data and local dev ergonomics
Support straightforward local development and testing.

At minimum:
- make seeded dev users and role fixtures easy to understand
- make project creation and membership flows easy to exercise locally
- document any required seed command or automatic bootstrap
- keep the local setup deterministic

## Required deliverables

### API
- project model / migration
- membership model / migration
- baseline policy snapshot seed/bootstrap
- project and membership API routes
- RBAC enforcement for those routes

### Web
- authenticated projects index
- project-scoped layout
- overview route
- activity route placeholder if needed
- settings route with member management
- project switcher
- access-tier badge usage
- permission-aware navigation

### Shared packages
- project/member/access-tier contracts as needed
- shared UI elements only where they simplify the repo

### Docs
- update `README.md` if local workflow changes
- add or refine a project-workspace and RBAC doc
- document the seeded baseline policy attachment behavior

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

## Non-goals
Do not implement any of the following here:
- full audit ledger and audit viewer
- full metrics/tracing/operations dashboards
- jobs engine
- ingest and viewer functionality
- preprocessing, layout, transcription, privacy, governance, export, provenance, or discovery workflows
- full policy authoring
- noisy admin-console aesthetics
- a toy “project dashboard” disconnected from real RBAC and route ownership

## Testing and validation
Before finishing:
1. Verify project creation creates the project and the creator membership.
2. Verify project creation attaches the current seeded baseline privacy policy snapshot.
3. Verify non-members cannot read ordinary member-scoped project routes.
4. Verify `PROJECT_LEAD` can add/remove/change members.
5. Verify `RESEARCHER` cannot manage members.
6. Verify explicit platform-role override behavior is limited to routes that declare it.
7. Run frontend tests or e2e flows for:
   - login -> `/projects`
   - create project
   - project appears in list
   - add member
   - member appears with correct role
8. Verify navigation visibility matches authorization.
9. Verify docs match actual commands and paths.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- project persistence exists
- membership persistence exists
- project creation works
- baseline policy snapshot attachment works
- `/projects` is a real authenticated workspace index
- project-scoped layouts and routes are real
- membership management works for authorized roles
- navigation reflects authorization cleanly
- shell layout, navigation rail, and project switcher use one shared token/primitive system across project routes
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

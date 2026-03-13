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
   - `/phases/phase-01-ingest-document-viewer-v1.md` for `/admin` route ownership and shell/navigation expectations
   - `/phases/phase-11-hardening-scale-pentest-readiness.md` for operations and audit-facing admin routes that must remain future-compatible
3. Then review the current repository generally — admin routes, audit pages, activity pages, operations pages, security pages, design-system pages, role guards, shell layouts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second admin shell, duplicate audit navigation, or blur project-scoped governance with platform-admin surfaces.

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
- `/phases` wins for RBAC intent, platform-role boundaries, admin/auditor separation, audit-first posture, shell philosophy, and UX tone.
- Official docs win only for implementation mechanics.
- Keep platform admin surfaces separate from project-scoped governance surfaces. Do not turn `/admin` into a grab bag.

## Objective
Create the admin and audit shell surfaces for platform admins and auditors, while aligning project-scoped governance affordances for project leads.

This prompt owns:
- the canonical admin/governance shell and navigation model
- role-aware admin landing surfaces
- consistent audit and operations surface integration
- consistent page headers, filters, list/detail patterns, and dense governance UI
- integration of existing audit, operations, security, and design-system pages into one consistent internal console
- consistent separation between:
  - platform admin/governance surfaces
  - project-scoped activity/governance surfaces

This prompt does not own:
- brand-new deep backend feature implementations for later governance phases
- policy authoring
- evidence-ledger feature completion
- export review implementation
- a second project shell
- a noisy “security center” or “SOC dashboard” aesthetic

## Phase alignment you must preserve
From Blueprint, Phase 0, Phase 1, and Phase 11:

### Role intent
- `ADMIN` manages infrastructure, identity, keys, models, audit controls, and operational hardening
- `AUDITOR` has read-only governance access to explicitly designated compliance surfaces
- `PROJECT_LEAD` governs project purpose, scope, and project-scoped choices, but is not implicitly a platform admin
- platform-role override is explicit, not implicit

### Route ownership
- `/admin` is the platform-admin area with read-only `AUDITOR` governance screens and per-screen restrictions
- project-scoped activity remains in project routes such as `/projects/:projectId/activity`
- operations routes later include:
  - `/admin/operations`
  - `/admin/operations/export-status`
  - `/admin/operations/slos`
  - `/admin/operations/alerts`
  - `/admin/operations/timelines`

### UX tone
- dark, dense, calm, serious
- no consumer-dashboard gimmicks
- no noisy metric walls
- list/detail, drawer, timeline, and bounded-region patterns are preferred over clutter

## Implementation scope

### 1. Canonical admin shell
Implement or refine one consistent admin shell/layout.

Requirements:
- `/admin` becomes the entry to the platform admin/governance area
- role-aware left navigation or sectional navigation
- consistent page-header contract
- dense, calm information hierarchy
- deep-linkable subsections
- safe integration with the existing authenticated shell without creating a competing shell

The admin shell must feel like part of the same product, not a separate internal tool.

### 2. Role-aware surface grouping
Organize admin and governance surfaces clearly.

Suggested structure:
- Overview
- Audit
- Operations
- Security
- Design System
- Future reserved governance slots only if the repo already needs placeholders

Requirements:
- `ADMIN` sees the full platform-admin navigation for implemented surfaces
- `AUDITOR` sees only explicitly allowed read-only governance surfaces
- `PROJECT_LEAD` does not inherit platform-admin access by default
- project leads continue using project-scoped governance/activity surfaces where appropriate

Do not tease inaccessible surfaces unnecessarily.

### 3. Admin landing page
Create or refine a useful `/admin` landing route.

Requirements:
- concise overview of the implemented admin/governance modules
- role-aware module cards or list entries
- small read-only summaries where data already exists
- clear navigation to audit, operations, security, and design-system surfaces
- calm empty/unavailable states for modules not yet implemented
- no fake “executive dashboard” fluff

### 4. Audit surface integration
Integrate or refine the audit shell surfaces so they feel like one consistent system.

At minimum reconcile:
- `/admin/audit`
- `/admin/audit/[eventId]`

Requirements:
- list/detail flow remains clear
- filters and cursor state are URL-driven where appropriate
- dense but readable event presentation
- request ID, actor, project, event type, and time context remain legible
- detail view fits list/detail or route/detail composition cleanly
- read-only auditor access is enforced correctly

### 5. Operations and security surface integration
Integrate or refine existing operations and security routes into the admin shell.

At minimum reconcile if they exist:
- `/admin/operations`
- `/admin/operations/export-status`
- `/admin/operations/slos`
- `/admin/operations/alerts`
- `/admin/operations/timelines`
- `/admin/security`

Requirements:
- one consistent navigation model
- current data shown accurately
- unavailable signals remain clearly not-yet-available rather than faked
- `AUDITOR` remains read-only only where phases explicitly allow it
- `RESEARCHER` and ordinary project roles cannot open these platform pages

### 6. Project-scoped governance distinction
Make the distinction between project-scoped and platform-scoped governance explicit.

Requirements:
- `/projects/:projectId/activity` remains project-scoped
- project leads can access project activity and project-governance surfaces explicitly allowed to them
- project activity does not masquerade as platform audit
- shared visual patterns may be reused, but route ownership and RBAC boundaries must remain explicit

If appropriate, refine project activity so it visually aligns with admin audit surfaces without collapsing the two concepts together.

### 7. Filters, timelines, drawers, and details
Use the existing primitive system to make governance surfaces professional and efficient.

Requirements:
- clear filter bars
- dense data tables or timelines
- drawers or detail routes for low-frequency details
- URL persistence for filters where it helps review workflows
- one primary action per surface where appropriate
- no cluttered button fields or giant control strips

### 8. Read-only governance affordances
Explicitly reflect read-only access where useful.

Examples:
- read-only labels or badges for `AUDITOR`
- unavailable decision controls hidden or safely disabled
- page copy remains calm and exact
- no patronizing warning copy

### 9. Documentation
Document:
- admin shell ownership
- role-to-surface matrix
- difference between project activity and platform audit/operations/security
- route and navigation structure
- how future governance/admin surfaces must plug into the shell

## Required deliverables

### Web
- `/admin` landing page
- canonical admin shell layout
- integrated admin navigation
- consistent integration of current audit, operations, security, and design-system routes
- refined project activity alignment where useful

### Docs
- admin/governance shell contract doc
- role-to-surface matrix doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/packages/ui/**` only where small shared shell/list/detail helpers improve coherence
- `/packages/contracts/**` only if small shared role/surface enums help consistency
- `/api/**` only if a very small summary/helper endpoint is required for the admin landing page
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- full future governance modules not yet built
- policy authoring
- evidence-ledger feature completion
- export review completion
- project-level feature work outside what is needed for shell coherence
- a flashy admin console aesthetic
- a second shell path for governance

## Testing and validation
Before finishing:
1. Verify `/admin` is a real role-aware landing route.
2. Verify `ADMIN` access works for implemented admin surfaces.
3. Verify `AUDITOR` access is read-only and only on explicitly allowed surfaces.
4. Verify `PROJECT_LEAD` does not gain implicit platform-admin access.
5. Verify project activity remains distinct from platform audit.
6. Verify filters and deep links behave predictably on audit/admin surfaces.
7. Verify current admin routes now feel like one consistent console.
8. Verify dark/light/high-contrast behavior is not broken.
9. Verify docs match actual route ownership and role behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- one consistent admin shell exists
- admin, audit, operations, security, and design-system surfaces fit together cleanly
- auditor access is explicit and read-only where allowed
- project leads remain project-scoped unless a route explicitly grants more
- admin and audit surfaces enforce consistent role-based visibility and read-only behavior for auditor-only routes
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

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
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-01-ingest-document-viewer-v1.md` for shared contracts, single API client, standard query-key conventions, and browser route/data expectations
3. Then review the current repository generally — API routes, shared contracts, DTOs, frontend fetch helpers, hooks, cache/query libraries, mutations, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second API client, a second cache layer, or duplicate hand-written DTOs that drift from backend reality.

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
- `/phases` wins for shared-contract intent, single-API-client expectations, route/data separation, audit/governance posture, and UX/loading-state expectations.
- Official docs win only for implementation mechanics.
- Keep one consistent data layer. Do not scatter `fetch()` calls, duplicate DTOs, or invent conflicting query-key patterns across routes.

## Objective
Establish frontend data contracts, typed API clients, cache policy, and optimistic-state rules for the web app.

This prompt owns:
- the canonical typed frontend data layer
- one shared typed API client
- frontend-facing contracts aligned with backend reality
- query-key conventions and cache policy
- mutation and invalidation rules
- conservative optimistic-state rules
- server/client data-fetch integration suitable for the current web architecture
- testing and documentation for the data layer

This prompt does not own:
- a full backend schema redesign
- a second state-management framework
- feature-specific workflow completion
- an overbuilt internal SDK disconnected from the current repo
- aggressive optimistic UI that weakens governance or correctness

## Phase alignment you must preserve
From Phase 0 and Phase 1:

### Shared contracts
- `/packages/contracts` exists for shared schemas, DTOs, and typed contracts
- browser implementation should not drift from backend contracts

### Data fetching rules
- single API client
- standard query-key conventions
- prefer skeleton loading over spinner-only patterns

### Product architecture
The secure web application is the product surface.
It must use backend and shared contracts through typed clients only, without ad hoc per-view data handling that bypasses contract governance.

## Implementation scope

### 1. Canonical contract ownership
Implement or refine the canonical ownership model for frontend-facing contracts.

Requirements:
- one clear source of truth for the web app's DTOs and request/response shapes
- prefer the least disruptive correct path already present in the repo:
  - shared `/packages/contracts`
  - generated types from authoritative backend schemas
  - or a carefully centralized typed contract layer that does not drift
- no uncontrolled manual duplication of API shapes across route files
- no `any`-driven API layer

At minimum cover the entities already present in the repo, such as:
- health/status
- current user / auth context
- project summaries and memberships
- jobs
- admin audit list/detail
- current-user activity
- project activity
- operations/security summaries where implemented

### 2. Single typed API client
Implement or refine one shared API client for the web app.

Requirements:
- typed request/response handling
- centralized base URL and auth/session handling
- consistent error normalization
- support for abort/cancellation where useful
- safe request correlation hooks if the current repo already supports them
- browser-safe and server-safe use where the current architecture needs both
- no route-local ad hoc fetch wrappers multiplying across the repo

### 3. Query-key conventions and cache ownership
Define and implement standard query-key conventions.

Requirements:
- one consistent key factory or equivalent pattern
- predictable key shapes for:
  - auth/current-user
  - project lists and project detail
  - jobs and job detail/status
  - admin audit lists and detail
  - current-user activity
  - project activity
  - operations/security summaries
  - any other currently implemented major route families
- query keys reflect route and filter state where appropriate
- query keys are documented and reusable
- no accidental collisions
- do not collapse admin audit, current-user activity, and project-scoped activity into one catch-all resource family unless the backend genuinely exposes one canonical contract

### 4. Cache policy
Implement an explicit cache policy for the web app.

Requirements:
- different data classes have intentional freshness rules
- document what is:
  - short-lived or pollable
  - medium-lived and invalidated on mutation
  - effectively immutable after read
- auth/session-sensitive data invalidates correctly on login/logout or access changes
- high-frequency operational data does not become stale by accident
- append-only or immutable detail reads may have longer retention where appropriate
- route state in the URL is not duplicated meaninglessly in a client store

The cache policy must be conservative and easy to reason about.

### 5. Mutation rules and invalidation
Implement or refine typed mutation helpers and invalidation rules.

Requirements:
- one mutation pattern for the app
- post-mutation invalidation is explicit and predictable
- mutation success/error states integrate with the shared UX state language
- no hidden stale-cache traps after project creation, membership changes, retry/cancel job actions, or similar existing flows
- destructive or governance-sensitive actions remain exact and traceable

### 6. Optimistic-state rules
Implement and document conservative optimistic-state rules.

Core rule:
- pessimistic by default
- optimistic only when the action is low-risk, reversible, and rollback-safe

Never use optimistic state for:
- auth/session truth
- RBAC truth
- audit records
- security status
- append-only governance events
- job terminal state truth
- export or release decisions
- destructive or compliance-sensitive mutations

If appropriate, allow carefully bounded optimistic UI only for low-risk interactions, such as:
- harmless UI preference updates
- non-governance local state mirrors
- clearly rollback-safe list affordances

Where server confirmation is required, show pending or in-flight state rather than pretending success.

### 7. Server/client integration
Fit the data layer into the current web architecture.

Requirements:
- compatible with the existing App Router/server-client split
- initial data and interactive client refresh paths are consistent
- no duplicated fetching in both server and client without reason
- route boundaries, loading boundaries, and cache boundaries remain understandable
- future routes can reuse this layer as-is

If the repo already uses a consistent query/cache library, extend it.
If no consistent client cache exists, add one clear layer and document it clearly.

### 8. Error model and retry behavior
Implement or refine a user-safe error model in the data layer.

Requirements:
- normalized error shapes
- safe mapping of backend errors to frontend state handling
- predictable retry rules
- no aggressive automatic retries on unsafe mutations
- unauthorized and forbidden paths remain exact and fail closed
- validation and conflict errors remain actionable

### 9. Testing
Add meaningful tests for the data layer.

At minimum cover:
- typed client behavior
- query-key stability
- invalidation on successful mutations
- conservative no-optimism behavior on governance-sensitive actions
- optimistic rollback behavior if any bounded optimistic path is introduced
- error normalization behavior
- auth/session invalidation behavior where applicable

Use the least disruptive deterministic test strategy the repository already supports.

### 10. Documentation
Document:
- the canonical contract source
- the API client ownership model
- query-key conventions
- cache policy
- mutation and invalidation rules
- optimistic-state rules
- how later work should add new endpoints and query families

## Required deliverables

### Shared contracts / client layer
- canonical frontend-facing contracts
- one typed API client
- query-key factory or equivalent
- cache policy implementation
- mutation helpers and invalidation utilities
- tests

### Web
- current major routes migrated to the canonical data layer where practical
- ad hoc fetch patterns reduced where they are clearly redundant

### Docs
- frontend data-layer contract doc
- cache and optimistic-state policy doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/packages/contracts/**`
- `/api/**` only if a small schema/export alignment change is required to remove obvious drift
- `/packages/ui/**` only if small shared loading/error helpers are needed to support the new data-layer integration
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- a second client-side store competing with the query/cache layer
- broad backend schema rewrites
- overly optimistic UI for governed records
- feature completion for later phases
- scattered route-local API wrappers
- magic data abstractions that hide too much of the real behavior

## Testing and validation
Before finishing:
1. Verify one canonical typed API client exists.
2. Verify shared contracts or generated types are the real source for frontend data shapes.
3. Verify query-key conventions are explicit and stable.
4. Verify cache invalidation works on the major existing mutation paths.
5. Verify optimistic-state rules are conservative and enforced.
6. Verify auth/session-sensitive data invalidates correctly.
7. Verify current routes are simpler and more consistent after the refactor, not more fragmented.
8. Verify docs match the actual contract, cache policy, and mutation rules.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the web app has one typed data layer
- one shared API client exists
- query-key and cache policy are explicit
- mutation invalidation is reliable
- optimistic-state rules are conservative and documented
- ad hoc data fetching is materially reduced
- the implementation is easier for later work to extend
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

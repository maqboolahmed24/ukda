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
   - `/phases/phase-01-ingest-document-viewer-v1.md` for `/admin`, root-route, and project-scoped activity ownership
3. Then review the current repo implementation context generally — existing code, configs, docs, scripts, tests, and implementation notes already present in the repo — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second logging or audit system beside whatever already exists.

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
- `/phases` wins for audit posture, append-only guarantees, event semantics, privacy rules, and governance boundaries.
- Official docs win only for API middleware mechanics, route handling, testing mechanics, and browser UI implementation details.
- Preserve the audit-first posture even if the repo contains weaker ad hoc logging patterns.

## External official reference pack for mechanics only
Use only official docs, and only for implementation mechanics.

### Next.js
- https://nextjs.org/docs/app/getting-started/layouts-and-pages
- https://nextjs.org/docs/app/getting-started/linking-and-navigating
- https://nextjs.org/docs/app/getting-started/fetching-data
- https://nextjs.org/docs/app/getting-started/error-handling

### FastAPI
- https://fastapi.tiangolo.com/tutorial/middleware/
- https://fastapi.tiangolo.com/advanced/middleware/
- https://fastapi.tiangolo.com/tutorial/testing/
- https://fastapi.tiangolo.com/tutorial/bigger-applications/

### Accessibility
- https://www.w3.org/TR/WCAG22/
- https://www.w3.org/WAI/ARIA/apg/

## Objective
Implement append-only audit logging with correlation IDs and integrity guarantees across UI, API, and background-execution boundaries.

This prompt owns:
- audit event persistence
- append-only audit behavior
- request correlation IDs
- safe metadata allowlists and audit payload hygiene
- integrity verification baseline
- admin audit viewer
- user-facing activity surface
- event emission for the flows already implemented in the repo
- future-ready worker/job compatibility for audit emission without inventing fake product flows

This prompt does not own:
- full telemetry, tracing, or metrics platform
- jobs framework implementation
- export review logic
- provenance bundles
- search/discovery features

## Phase alignment you must preserve
From Phase 0 Iteration 0.3:
- all meaningful actions are auditable
- logs are protected
- sensitive data is not leaked into logs
- `audit_events` includes:
  - `id`
  - `timestamp`
  - `actor_user_id`
  - `project_id` (nullable)
  - `event_type`
  - `object_type` (nullable)
  - `object_id` (nullable)
  - `ip`
  - `user_agent`
  - `request_id`
  - `metadata_json` with a strict key allowlist
- append-only behavior:
  - no update/delete endpoints
  - application paths do not mutate past audit rows
  - database protections are enforced where practical in the current stack
- log hygiene:
  - never log tokens
  - never log passwords
  - never log raw document content
  - validate and encode values to prevent log injection
- structured correlation with `request_id`
- admin and read-only auditor audit viewer surfaces exist
- optional current-user `/activity` surface exists and stays distinct from project-scoped `/projects/:projectId/activity`
- audit reads themselves are auditable

## Integrity posture you must implement
Implement a tamper-resistance baseline that is real, not rhetorical.

Required:
- append-only application behavior
- explicit prohibition of update/delete API paths
- protected DB access pattern
- audit-event serializer that normalizes event structure

Strongly preferred in this prompt:
- hash-chain integrity columns such as:
  - `prev_hash`
  - `row_hash`
- internal verification path for chain integrity
- test coverage for verification behavior

If the current stack makes true DB-role separation difficult locally, still:
- encode the intended protections in migrations or DDL where possible
- keep the app path append-only
- document the exact hardening gap rather than hiding it

## Event model requirements
Implement a stable audit event model that is easy to extend.

At minimum, emit or refine events for flows already present by the time this prompt runs, including as applicable:
- `USER_LOGIN`
- `USER_LOGOUT`
- `AUTH_FAILED`
- `PROJECT_CREATED`
- `PROJECT_MEMBER_ADDED`
- `PROJECT_MEMBER_REMOVED`
- `PROJECT_MEMBER_ROLE_CHANGED`
- `AUDIT_LOG_VIEWED`
- `AUDIT_EVENT_VIEWED`
- `MY_ACTIVITY_VIEWED`
- access-denied events when a protected route rejects a caller, if the current architecture supports that cleanly

Do not create fake events for product areas that do not exist yet.
Do create a stable event-registration path that later work can extend.

## Implementation scope

### 1. Audit event persistence and writer
Implement or refine:
- `audit_events` storage
- canonical event serialization
- strict metadata allowlist per event type or equivalent centralized validation
- a single audit-writer path used by the API and usable by future workers

Requirements:
- no ad hoc arbitrary JSON dumping
- metadata should be investigation-useful but bounded
- raw request bodies must not be mirrored into audit metadata
- free-text fields must be sanitized
- object references should prefer IDs and stable kinds over sensitive labels

### 2. Correlation IDs and request context
Implement request correlation end to end.

Requirements:
- every relevant request gets a `request_id`
- audit events emitted during the request carry that `request_id`
- request context includes actor, project when known, route template when useful, and safe client metadata
- correlation should be centralized, not manually copied per route

Keep it compatible with the current repo's middleware approach.

### 3. Integrity verification
Implement a real integrity baseline.

Preferred outcome:
- append-only audit table
- hash chain
- internal verification routine or endpoint
- admin-visible integrity status surface or detail

Acceptable if the repo architecture constrains full enforcement:
- still implement the verification logic over existing rows
- document the remaining hardening boundary explicitly
- do not falsely claim stronger guarantees than actually implemented

### 4. Audit viewer and activity UX
Implement or refine:

#### Admin/governance surfaces
- `/web/app/(authenticated)/admin/audit/page.tsx`
- `/web/app/(authenticated)/admin/audit/[eventId]/page.tsx`

#### User surface
- `/web/app/(authenticated)/activity/page.tsx`

Requirements:
- `ADMIN` can use the full audit viewer
- `AUDITOR` is read-only where explicitly allowed
- `/activity` shows the current user's recent relevant events only
- filters include project, actor, event type, and time range where appropriate
- detail view shows request ID, event metadata, and event lineage/integrity indicators when available
- UI is dense, calm, legible, and serious
- do not build a flashy SIEM wall
- do not leak sensitive metadata into the browser just because it exists internally

### 5. Audit-read self-auditing
Reading audit data is itself meaningful.

Implement audit events for:
- audit list view access
- audit detail view access
- my-activity view access

Keep these bounded so the viewer does not recursively explode into unusable noise.
Use a sensible approach such as event-type filtering or clear viewer behavior.

### 6. Worker and future-job compatibility
This prompt does not build the job framework.
It must, however, avoid painting later work into a corner.

Requirements:
- the audit writer can be called from non-HTTP execution paths
- correlation helpers can accept externally supplied request or job context
- do not invent fake job records
- do not block future worker integration

### 7. Documentation
Document:
- event model
- append-only and integrity guarantees
- metadata allowlist rules
- privacy rules for audit content
- how to verify chain integrity
- role access to audit surfaces
- any hardening gap that remains pending deeper environment work

## Required deliverables

### API / backend
- audit model / migration
- audit writer service
- request-correlation middleware
- audit read endpoints
- integrity verification support
- tests

### Web
- `/admin/audit`
- `/admin/audit/:eventId`
- `/activity`

### Docs
- audit event model doc
- audit integrity / verification doc
- any README updates required for local validation

## Allowed touch points
You may modify:
- `/web/**`
- `/api/**`
- `/workers/**` only if a very small compatibility shim is needed for future audit emission
- `/packages/contracts/**`
- `/packages/ui/**`
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- full metrics and tracing platform
- operations dashboards
- job queue/runtime implementation
- ingest, preprocessing, layout, transcription, privacy, governance, export, provenance, or discovery flows
- public log exports
- a noisy “security dashboard” that weakens focus and readability

## Testing and validation
Before finishing:
1. Verify append-only application behavior.
2. Verify there are no update/delete API paths for audit events.
3. Verify audit events are emitted for login, project creation, membership changes, and audit reads where those flows exist.
4. Verify sensitive fields are absent from audit metadata.
5. Verify `request_id` correlation is present.
6. Verify admin and auditor access boundaries.
7. Verify `/activity` only shows appropriate current-user activity.
8. Verify integrity-check tests if the hash-chain path is implemented.
9. Verify docs match actual commands and paths.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- audit persistence exists
- audit behavior is append-only
- correlation IDs are real
- sensitive data is excluded from audit content
- integrity verification baseline is real and tested or explicitly bounded
- admin audit viewer exists
- my-activity view exists
- already-implemented product flows emit audit events
- the UX preserves existing shell visual conventions while keeping audit actions discoverable and keyboard accessible
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

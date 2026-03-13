# Phase 0: Foundation Release - Origins

> Status: ACTIVE
> Web Root: /web
> Active Phase Ceiling: 11
> Execution Policy: Phase 0 through Phase 11 are ACTIVE for this prompt program.
> Web Translation Overlay (ACTIVE): preserve existing workflow intent and phase semantics while translating any legacy desktop or WinUI terms into equivalent browser-native routes, layouts, and interaction patterns under /web.

## Phase Objective
By the end of Phase 0, the system:

1. Runs end-to-end in the secure environment (cluster, DB, object storage, workers, UI).
2. Enforces identity and project RBAC.
3. Produces protected audit logs with an append-only mindset.
4. Includes a real job framework (table, worker, retries, status).
5. Starts SecureLab-style constraints:
   - no external AI API calls
   - no uncontrolled download path
   - export gateway stub as the future single door out

Phase 0 is intentionally test-heavy to avoid carrying security debt into later phases.

## Entry Criteria
Start Phase 0 only when all are true:
- a target secure environment is available for internal deployment and networking
- internal database, object storage, container registry, and model-artefact storage capacity are provisioned or reserved
- OIDC integration and CI/CD secret-management paths are agreed
- no-egress, auditability, and deny-by-default access are accepted as day-one requirements

## Scope Boundary
Phase 0 establishes platform and governance foundations only.

Out of scope for this phase:
- controlled ingest, document library, and viewer workflows (Phase 1)
- preprocessing, layout, transcription, and privacy-review features (Phases 2 through 5)
- manifest, export, provenance, discovery, and production-hardening deliverables beyond the foundation stubs defined here (Phases 6 through 11)

## Phase 0 Non-Negotiables
- Secure web application is the active delivery target: preserve phase behavior and governance contracts while implementing browser-native interaction, routing, and layout patterns from first principles (no desktop-mechanics carryover).
- The Obsidian Folio experience layer starts here: dark-first theme defaults, app-window adaptive states, single-fold workspace scaffolding, and keyboard-first accessibility rules are platform concerns, not phase-local embellishments; see `ui-premium-dark-blueprint-obsidian-folio.md`.
1. Authentication and authorization are deny-by-default from the first protected route onward.
2. Audit logging is append-only, integrity-aware, and present before later workflow phases begin.
3. No-egress controls are active before any downstream ML or export-facing features are introduced.
4. The export-gateway stub proves the single-door design without creating a live egress path.

## Iteration Model
Build Phase 0 across five iterations. Each iteration must end with a deployable, working system that is more capable than the previous one.

## Iteration 0.1: Repo + CI/CD + Hello Secure World

### Goal
Deploy an empty app in the secure cluster with health checks, UI shell, and CI gates.

### Backend Work
- Monorepo scaffolding:
  - `/api` (FastAPI)
  - `/web` (Next.js App Router application)
  - `/workers`
  - `/packages/ui` (shared design system and browser primitives)
  - `/packages/contracts` (shared schemas, DTOs, and typed contracts)
  - `/infra` (Helm/Terraform)
- Environment profiles:
  - `dev`, `staging`, `prod`
  - No shared secrets
  - Internal container registry only
- Model serving foundation:
  - `dev`: local workstation services run outside the repository with a role-isolated model root; on macOS the recommended root is `~/Library/Application Support/UKDataExtraction/models`
  - `staging` and `prod`: Helm/Terraform deploy internal model services inside the secure cluster on GPU-capable nodes with read-only mounted artefacts or pre-synced internal object storage rooted at `/srv/ukdataextraction/models`
  - initial approved starter stack:
    - `TRANSCRIPTION_PRIMARY`: `Qwen2.5-VL-3B-Instruct`
    - `ASSIST`: `Qwen3-4B`
    - `PRIVACY_NER`: `GLiNER-small-v2.1` or `GLiNER-medium-v2.1`
    - `PRIVACY_RULES`: `Presidio`
    - `TRANSCRIPTION_FALLBACK`: `Kraken`
    - `EMBEDDING_SEARCH` (optional): `Qwen3-Embedding-0.6B`
  - every model role is replaceable through the approved service map without changing workflow routes or persistence schemas
  - OpenAI-compatible services are used for chat, vision, and embedding roles:
    - `GET /health`
    - `GET /v1/models`
    - `POST /v1/chat/completions`
    - `POST /v1/embeddings` when the role exposes embeddings
  - engine-native and rules-native services remain valid for fallback HTR and privacy rules, but they must still be bound through the same approved internal service map
  - workflow workers call only approved internal model services resolved through the service map and validate structured model output before persisting any derived artefact
  - see `MODEL_STACK.md` for deployment isolation and replacement rules
- Configuration contract:
  - `OPENAI_BASE_URL`
  - `OPENAI_API_KEY`
  - `MODEL_DEPLOYMENT_ROOT`
  - `MODEL_ARTIFACT_ROOT`
  - `MODEL_CATALOG_PATH`
  - `MODEL_ALLOWLIST`
  - `MODEL_SERVICE_MAP_PATH`
  - `MODEL_WARM_START`
- API skeleton:
  - `GET /healthz` (liveness)
  - `GET /readyz` (DB readiness)
- CI pipeline (mandatory):
  - unit tests (backend and web client)
  - lint/format (`ruff`, `black`, `eslint`, `prettier`)
  - container image builds
  - dependency scan (`npm`, `pip`)

### Web Client Work
- App shell foundation (browser-native):
  - root App Router layout with header, navigation rail slot, content host, deployment-environment badge, and project access-tier badge placeholder
  - shared `/packages/ui` token system for `Colors`, `Typography`, `Spacing`, `Shape`, `Elevation`, and `Motion`
  - theme service defaults to `Dark`, supports `Light`, and honors browser contrast or forced-colors preferences through preference synchronization rather than a separate desktop-style mode
  - layered backdrop policy keeps persistent shell surfaces restrained and uses translucency only for transient overlays when user transparency preferences allow it
  - adaptive layout state root driven by available browser-window and app client area (`Expanded | Balanced | Compact | Focus`)
- Initial views:
  - `/login` placeholder
  - `/` lightweight entry route that resolves to `/login` in the pre-auth baseline and later becomes the auth-aware redirect to `/login` or `/projects`
  - `/health` displays `Service status: OK` from `/healthz`
  - internal web component gallery scaffold (`/admin/design-system`) for shell primitives, focus states, and toolbar behavior

### Tests and Gates (Iteration 0.1)
#### Unit
- `/healthz` returns `200`.
- `/readyz` fails if DB is not reachable.

#### Integration
- API starts with a local integration DB or ephemeral test DB.
- local development profile validates the role-to-service map against a role-isolated model root outside the repository.

#### E2E
- Open `/health` and verify service status is `OK`.

#### web-surface gate
- Keyboard-only navigation works in shell and login placeholders.
- Theme switching (`Dark`, `Light`) is functional and persisted, and browser contrast or forced-colors preferences render correctly.
- Browser accessibility baseline scan passes on shell and login placeholders.
- Layout-state transitions (`Expanded`, `Balanced`, `Compact`, `Focus`) are wired to supported browser viewport changes without layout breakage.

#### Security Gates
- CI fails on high-severity dependency vulnerabilities unless explicitly waived with tracking.
- Model services start from preloaded internal artefacts only; runtime public model pulls are not part of the supported bootstrap path.

### Exit Criteria (Iteration 0.1)
- One command deploys skeleton into secure environment.
- CI actively blocks merges.
- Obsidian Folio experience foundations are present in the running shell (theme, tokens, adaptive states, and component gallery scaffold).

## Iteration 0.2: Identity, RBAC, and Project Workspace Skeleton

### Goal
A user can authenticate, create a project, and RBAC is enforced for every protected route.

### Backend Work
#### 1) Authentication
- OIDC integration (SSO):
  - stable `sub` identity key
  - session cookie or JWT (short-lived access + refresh)
- `users` table:
  - `id`
  - `oidc_sub`
  - `email`
  - `display_name`
  - `created_at`
  - `last_login_at`
- Enforce authentication on all routes except health checks.

#### 2) Projects and memberships
- `projects` table:
  - `id`
  - `name`
  - `purpose` (required)
  - `status` (`ACTIVE | ARCHIVED`)
  - `created_by`
  - `created_at`
  - required `intended_access_tier`: `OPEN | SAFEGUARDED | CONTROLLED`
  - required `baseline_policy_snapshot_id` (attached from the seeded platform baseline and read-only until Phase 7 policy authoring exists)
- `project_members`:
  - `project_id`
  - `user_id`
  - `role`
- Project roles:
  - `PROJECT_LEAD`
  - `RESEARCHER`
  - `REVIEWER`
- Platform governance capability is separate from project membership:
  - `user_platform_roles`
    - `user_id`
    - `role` (`ADMIN` | `AUDITOR`)
- `ADMIN` and `AUDITOR` may access explicitly designated governance or admin surfaces without project membership when a route declares that platform-role override.
- `AUDITOR` is read-only governance access for explicitly designated compliance surfaces such as audit, policy, evidence-ledger, pseudonym-registry, proof-verification, release-review, and later index-quality or operations review pages.
- RBAC middleware:
  - deny by default
  - each route declares required role(s)
- Initial audit hooks:
  - `USER_LOGIN`
  - `PROJECT_CREATED`
  - `PROJECT_MEMBER_ADDED`
  - `PROJECT_MEMBER_REMOVED`

### Web Client Work
- Identity and project views inherit the Obsidian Folio shell contract (dark-first tokens, adaptive states, keyboard-first focus behavior).
- Real login flow:
  - redirect to IdP
  - callback handling
- Projects page:
  - list memberships
  - create project form with:
    - name
    - required purpose
    - tier intent dropdown (default Controlled)
- Project members page (`PROJECT_LEAD` and `ADMIN`):
  - add/remove members
  - change roles

### Tests and Gates (Iteration 0.2)
#### Unit (backend)
- RBAC matrix:
  - non-member cannot read ordinary member-scoped project routes
  - platform-role governance access works only on routes that explicitly declare the override
  - `RESEARCHER` cannot add members
  - `PROJECT_LEAD` can add members
- Auth:
  - unauthenticated requests rejected (`401`)
  - invalid token rejected

#### Integration
- Create project creates membership row.
- Add member creates membership row and audit event.
- Create project attaches the current seeded baseline privacy policy snapshot.

#### E2E
- Login -> create project -> appears in list.
- Add member (mock second user) -> appears in members list.

#### Security Gates
- Session hardening:
  - `HttpOnly`
  - `Secure`
  - `SameSite`
  - CSRF protection if cookie sessions are used

### Exit Criteria (Iteration 0.2)
- Identity and project RBAC are enforceable and tested.
- Project workspace exists as the core unit of work.

## Iteration 0.3: Audit Logging + Tamper-Resistance Baseline + Log Privacy Rules

### Goal
All meaningful actions are auditable, logs are protected, and sensitive data is not leaked into logs.

### Backend Work
#### 1) Audit event design
Create `audit_events`:

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
- `metadata_json` (strict key allowlist)

Rules:

- Append-only behavior:
  - no update/delete endpoints
  - app DB role cannot update/delete audit rows
- Log hygiene:
  - never log tokens, passwords, raw document content
  - validate/encode values to prevent log injection
  - include investigation-grade metadata

#### 2) Integrity protection baseline
Minimum baseline:

- append-only DB permissions + restricted role + frequent snapshots
- hash-chain columns:
  - `prev_hash`
  - `row_hash = H(prev_hash + canonical_json(event))`
- internal verify endpoint for chain integrity

Recommended enhancement in the same phase if feasible:

- periodic automated verification jobs and alerting on chain-integrity failures

#### 3) Observability
- Structured logs with `request_id` and safe `project_id`.
- Metrics:
  - request latency
  - error rate
  - queue size (to be used in Iteration 0.4)

### Web Client Work
- `ADMIN` and read-only `AUDITOR` audit viewer:
  - `/admin/audit`
  - `/admin/audit/:eventId`
  - filter by project, user, event type, time range
  - show request id and metadata
- Optional `My activity` view for users without `ADMIN` or `AUDITOR`:
  - `/activity`
  - last logins
  - recent project events
  - this route is current-user scoped and remains distinct from the later project-scoped `/projects/:projectId/activity` surface

APIs:
- `GET /admin/audit-events?projectId={projectId}&actorUserId={actorUserId}&eventType={eventType}&from={from}&to={to}&cursor={cursor}`
- `GET /admin/audit-events/{eventId}`
- `GET /me/activity`

### Tests and Gates (Iteration 0.3)
#### Unit
- Audit events emitted for:
  - login
  - project creation
  - membership changes
  - audit viewer reads
- Sensitive fields absent from logs/metadata:
  - token values
  - raw file bytes
- Hash-chain verification tests

#### Integration
- Request correlation:
  - API request creates `request_id`
  - audit event carries same `request_id`

#### E2E
- `ADMIN` or `AUDITOR` opens audit viewer and sees project creation event.

#### Security Gate
- Audit log is not modifiable via API.
- App DB role lacks `UPDATE/DELETE` on `audit_events`.

### Exit Criteria (Iteration 0.3)
- You can reconstruct who did what, when, and in which project.
- Logs are protected and treated as sensitive data.

## Iteration 0.4: Job Framework + Worker Service + Pipeline-Ready Backbone

### Goal
Background work can be enqueued, executed, retried safely, and monitored in UI.

### Backend Work
#### 1) Jobs table and state machine
`jobs` table:

- `id`
- `project_id`
- `attempt_number`
- `supersedes_job_id` (nullable when this is the first attempt)
- `superseded_by_job_id` (nullable)
- `type` (start with `NOOP`)
- `dedupe_key`
- `status`: `QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`
- `attempts` (worker-delivery attempts for this specific job row)
- `max_attempts`
- `payload_json`
- `created_by`
- `created_at`
- `started_at`
- `finished_at`
- `canceled_by` (nullable)
- `canceled_at` (nullable)
- `error_code`
- `error_message` (sanitized)

Add append-only `job_events`:

- `id`
- `job_id`
- `project_id`
- `event_type` (`JOB_CREATED | JOB_STARTED | JOB_SUCCEEDED | JOB_FAILED | JOB_CANCELED | JOB_RETRY_APPENDED`)
- `from_status` (nullable)
- `to_status`
- `actor_user_id` (nullable for worker-generated transitions)
- `details_json` (nullable)
- `created_at`

Idempotency rule:

- Deterministic `dedupe_key` per logical job.
- `dedupe_key` stays stable across retries for the same logical work item; retry lineage is represented by `attempt_number`, `supersedes_job_id`, and `superseded_by_job_id`, not by minting a different logical key.
- `attempt_number` counts append-only logical retries across job rows, while `attempts` counts worker delivery/execution attempts inside the current row only; a new retry row starts with a new `attempt_number` and resets `attempts` for that row.
- when an unsuperseded job with the same `dedupe_key` is already `QUEUED` or `RUNNING`, create/retry requests return that in-flight row instead of appending a duplicate logical job
- worker avoids re-running only when an unsuperseded job with the same `dedupe_key` has already reached `SUCCEEDED`
- `job_events` is the append-only lifecycle source of truth for a job row; job detail history and retry chronology must read from `job_events` rather than reconstructing transitions from the mutable `jobs.status` projection alone

#### 2) Worker
- Poll queue or consume broker.
- Apply valid state transitions.
- Every create, retry, start, finish, fail, and cancel transition appends a matching `job_events` row for the affected job attempt.
- Project-scoped job APIs:
  - `GET /projects/{projectId}/jobs`
  - `GET /projects/{projectId}/jobs/{jobId}`
  - `GET /projects/{projectId}/jobs/{jobId}/status`
  - `GET /projects/{projectId}/jobs/{jobId}/events`
  - `POST /projects/{projectId}/jobs/{jobId}/retry`
    - appends a new job row, increments `attempt_number`, carries forward the same logical `dedupe_key`, sets `supersedes_job_id`, and records the forward link on the replaced row through `superseded_by_job_id`
  - `POST /projects/{projectId}/jobs/{jobId}/cancel`
    - allowed only while the target row is `QUEUED` or `RUNNING`
    - queued jobs transition directly to `CANCELED`
    - running jobs transition to `CANCELED` only through worker-checked cooperative cancellation; cancel requests against already terminal rows are rejected instead of rewriting terminal history
- RBAC:
  - `PROJECT_LEAD`, `RESEARCHER`, and `REVIEWER` can read project job status
  - `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can retry or cancel eligible jobs
- Emit audit events:
  - `JOB_LIST_VIEWED`
  - `JOB_RUN_CREATED`
  - `JOB_RUN_STARTED`
  - `JOB_RUN_FINISHED`
  - `JOB_RUN_FAILED`
  - `JOB_RUN_CANCELED`
  - `JOB_RUN_VIEWED`
  - `JOB_RUN_STATUS_VIEWED`

#### 3) Storage skeleton
Create prefixes and IAM policies:

- `controlled/raw/`
- `controlled/derived/`
- `safeguarded/exports/` (empty until later phases)

Access policies:

- App can write `controlled/raw` and `controlled/derived`.
- Only future export gateway service account can write `safeguarded/exports`.

### Web Client Work
- Project Jobs page:
  - `/projects/:projectId/jobs`
  - `/projects/:projectId/jobs/:jobId`
  - job list
  - status badges
  - timestamps
  - safe error display
- Project overview:
  - `jobs running: N`
  - last job status

### Tests and Gates (Iteration 0.4)
#### Unit
- Valid job state transitions only.
- Dedupe key blocks duplicate execution.

#### Integration
- Enqueue -> worker picks up -> marks success.
- Job detail history is reproducible from append-only `job_events` even after the mutable job row reaches a later terminal state.
- Retry path:
  - first failure
  - retry
  - success
- Retry lineage increments `attempt_number` and preserves both `supersedes_job_id` and `superseded_by_job_id`.
- in-flight same-key duplicate create or retry requests return the existing unsuperseded `QUEUED` or `RUNNING` row instead of appending a second logical job
- Cancellation path:
  - cancel queued job
  - ensure it never runs
- cancel running job cooperates with the worker and never rewrites a job that already finished terminally
- Job detail pages poll `GET /projects/{projectId}/jobs/{jobId}/status` for live status changes instead of repeatedly fetching the full detail payload.

#### E2E
- Create project -> run test job -> status flow: queued -> running -> success.

#### Reliability Gate
- Worker restart mid-job recovers safely; no permanently stuck `RUNNING` jobs.

### Exit Criteria (Iteration 0.4)
Background processing is operational, observable, and safe to retry.

## Iteration 0.5: Secure-Setting Enforcement Baseline

### Goal
Technically enforce controlled-environment constraints from day one.

### Backend Work
#### 1) Network egress deny-by-default
- Kubernetes/Firewall policy:
  - deny all outbound by default
  - allow only required internal services:
    - DB
    - object storage
    - internal auth/IdP
    - internal package mirrors/registry
- CI egress test:
  - launch pod
  - attempt public endpoint call
  - call must fail

#### 2) External AI call prevention
- Central HTTP client wrapper with allowlist policy.
- Any non-allowlisted domain call:
  - hard fail
  - audit event emitted
- Unit tests enforce this behavior.
- Runtime model pulls from public registries are treated as blocked external calls.
- Only internal object storage, mounted artefact paths, or other allowlisted internal model sources may satisfy model loads.

#### 3) Export gateway stub (no exports yet)
- Stub endpoints:
  - `GET /projects/{projectId}/export-candidates` returns disabled/not-implemented and audits attempt
  - `GET /projects/{projectId}/export-candidates/{candidateId}` returns disabled/not-implemented and audits attempt
  - `POST /projects/{projectId}/export-requests` returns disabled/not-implemented and audits attempt
  - `GET /projects/{projectId}/export-requests?status={status}&requesterId={requesterId}&candidateKind={candidateKind}&cursor={cursor}` returns disabled/not-implemented and audits attempt
  - `GET /projects/{projectId}/export-requests/{exportRequestId}` returns disabled/not-implemented and audits attempt
  - `GET /projects/{projectId}/export-requests/{exportRequestId}/status` returns disabled/not-implemented and audits attempt
  - `GET /projects/{projectId}/export-requests/{exportRequestId}/release-pack` returns disabled/not-implemented and audits attempt
  - `GET /projects/{projectId}/export-requests/{exportRequestId}/events` returns disabled/not-implemented and audits attempt
  - `GET /projects/{projectId}/export-requests/{exportRequestId}/reviews` returns disabled/not-implemented and audits attempt
  - `GET /projects/{projectId}/export-requests/{exportRequestId}/reviews/events` returns disabled/not-implemented and audits attempt
  - `POST /projects/{projectId}/export-requests/{exportRequestId}/reviews/{reviewId}/claim` returns disabled/not-implemented and audits attempt
  - `POST /projects/{projectId}/export-requests/{exportRequestId}/reviews/{reviewId}/release` returns disabled/not-implemented and audits attempt
  - `POST /projects/{projectId}/export-requests/{exportRequestId}/start-review` returns disabled/not-implemented and audits attempt
  - `GET /projects/{projectId}/export-requests/{exportRequestId}/receipt` returns disabled/not-implemented and audits attempt
  - `POST /projects/{projectId}/export-requests/{exportRequestId}/resubmit` returns disabled/not-implemented and audits attempt
    - reserves the later Phase 8 behavior that a resubmission creates a new request revision, increments `request_revision`, and sets `supersedes_export_request_id`
  - `POST /projects/{projectId}/export-requests/{exportRequestId}/decision` returns disabled/not-implemented and audits attempt
    - reserves the later Phase 8 decision contract `decision = APPROVE | REJECT | RETURN`
  - `GET /projects/{projectId}/export-review?status={status}&agingBucket={agingBucket}&reviewerUserId={reviewerUserId}` returns disabled/not-implemented and audits attempt
- Reserve only minimal stub persistence in Phase 0 to support audit attempts and disabled-route hardening:
  - `export_stub_events`
    - `id`
    - `project_id` (nullable)
    - `route`
    - `method`
    - `actor_user_id` (nullable)
    - `request_id`
    - `created_at`
  - do not lock the final `export_candidate_snapshots`, `export_requests`, `export_request_events`, or `export_request_reviews` schemas in Phase 0; those contracts are owned by Phase 8
  - disabled export stubs may persist audit-safe placeholder rows only in `export_stub_events`
  - reserve the later Phase 8 rule that request-level final decision fields are projections from append-only review rows and events, and that high-risk requests may require a distinct secondary reviewer before approval
- Ensure architecture establishes a single future egress door.

#### 4) Baseline privacy policy snapshot bootstrap
- Seed a non-editable baseline privacy policy snapshot at deployment:
  - `baseline_policy_snapshots`
    - `id`
    - `snapshot_hash`
    - `rules_json`
    - `policy_family_origin_id`
    - `created_at`
    - `seeded_by`
- New projects attach the current baseline snapshot ID at creation time and keep that baseline read-only until Phase 7 introduces explicit project policy versions.
- Phase 7 policy creation must be able to seed a first explicit `redaction_policies` lineage from the attached `baseline_policy_snapshot_id`, and policy-compare surfaces must support baseline-snapshot-to-policy comparisons for that initial lineage.
- Audit events:
  - `BASELINE_POLICY_SNAPSHOT_SEEDED`
  - `PROJECT_BASELINE_POLICY_ATTACHED`
  - `ADMIN_SECURITY_STATUS_VIEWED`

#### 5) Web hardening baseline
- Security headers:
  - CSP baseline
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy`
  - minimal `Permissions-Policy`
- Rate limiting on auth and protected endpoints.
- `GET /admin/security/status` exposes the internal security-status summary used by the admin security page.

#### 6) Operational readiness
- Backup baseline:
  - DB snapshots
- Secret/config rotation mechanism:
  - documented
  - runnable
- Runbooks:
  - deployment
  - key rotation
  - backup restore

### Web Client Work
- Environment banner (`staging` vs `prod`).
- Export UI stub:
  - `/projects/:projectId/export-candidates`
  - `/projects/:projectId/export-requests`
  - `/projects/:projectId/export-review?status={status}&agingBucket={agingBucket}&reviewerUserId={reviewerUserId}`
  - disabled control
  - explanation that screening workflow is pending later phase
- Admin security status page:
  - `/admin/security`
  - last successful egress deny test
  - current CSP mode
  - last backup timestamp
  - current reduced-motion and reduced-transparency preference state (diagnostic only)

### Tests and Gates (Iteration 0.5)
#### Unit
- HTTP allowlist enforcement tests.
- Security header presence tests.
- Basic rate limit tests.
- Baseline policy snapshot hash is stable for the same seeded rules.

#### Integration
- In-cluster egress deny test fails public internet reachability.
- Worker external call attempt is blocked and audited.
- Model gateway startup fails when the configured model artefact is absent from mounted local or internal storage.
- Model gateway startup is validated against the configured `MODEL_ALLOWLIST`.
- New project records reference the current seeded baseline policy snapshot.
- Admin security status reads from `GET /admin/security/status`; the read surface is available to `ADMIN` and read-only `AUDITOR`, while any security-setting mutation remains `ADMIN`-only.
- Audit viewer reads emit `AUDIT_LOG_VIEWED`, audit-event detail reads emit `AUDIT_EVENT_VIEWED`, and `My activity` reads emit `MY_ACTIVITY_VIEWED`.

#### E2E
- `RESEARCHER` cannot access `/admin/security`; `AUDITOR` reads remain read-only and `ADMIN` retains all mutation rights.
- Export UI remains disabled; no uncontrolled export path.

#### Security Gates
- Access control decisions are logged.
- Sensitive values are excluded from logs.
- Logs remain protected against tampering and unauthorized access.

### Exit Criteria (Iteration 0.5)
- Secure-setting controls are technically enforced.
- No accidental controlled-data exfiltration path exists.

## Handoff to Later Phases
- Phase 1 builds controlled ingest and document viewing on top of Phase 0 identity, RBAC, jobs, audit, and no-egress controls.
- Phase 5 relies on the seeded baseline privacy policy snapshot attached here until explicit per-project policies arrive in Phase 7.
- No later phase may bypass the single export-gateway foundation or the audit guarantees established here.

## Phase 0 Definition of Done

### Functional
- SSO/OIDC authentication works.
- Projects and memberships are available.
- Jobs run and are observable.
- UI supports:
  - login
  - project creation
  - member management (`PROJECT_LEAD` and `ADMIN`)
  - job monitoring
  - `ADMIN` and read-only `AUDITOR` audit viewing

### Security and Governance Baseline
- Deny-by-default RBAC on all protected routes.
- Audit logging is append-only and integrity-aware.
- External egress is blocked except allowlisted internal services.
- Export path is architected as a single door out (stubbed in Phase 0).
- Baseline operational readiness is in place for security assessments and later hardening.

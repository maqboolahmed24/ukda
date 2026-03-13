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
   - `/phases/phase-07-policy-engine-v1.md` for future compatibility of baseline snapshot behavior only
   - `/phases/phase-08-safe-outputs-export-gateway.md` for the future export-gateway contract that Phase 0 must reserve without prematurely implementing it
3. Then review the current repository generally — code, configs, scripts, tests, docs, infra, model/runtime wiring, and security configuration already present in the repo — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second security-enforcement layer or parallel export contract.

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
- `/phases` wins for secure-environment posture, no-egress rules, export gateway ownership, baseline snapshot behavior, governance boundaries, and acceptance logic.
- Official docs win only for security-header mechanics, rate limiting mechanics, network-policy mechanics, and implementation details of runtime guards.
- If the repo already has weaker or ad hoc network/model/export behavior, strengthen or replace it to match the phase posture.

## Objective
Implement Phase 0 Iteration 0.5: secure-setting enforcement baseline.

This prompt owns:
- network egress deny-by-default baseline
- central allowlisted outbound-call enforcement
- external AI call prevention
- model artefact source enforcement
- export gateway stubs and disabled routes
- baseline privacy policy snapshot bootstrap if absent or weaker than required
- web hardening baseline
- admin security status surface
- operational-readiness docs and runbooks

This prompt does not own:
- real export workflow implementation
- Phase 7 full policy authoring
- external/public AI integrations
- full production cluster provisioning if unavailable
- later export review flows beyond the reserved contract

## Phase alignment you must preserve
From Phase 0 Iteration 0.5:

### Iteration Objective
Technically enforce controlled-environment constraints from day one.

### Required outbound-network posture
- deny all outbound by default
- allow only required internal services such as:
  - DB
  - object storage
  - internal auth / IdP
  - internal package mirrors / registry

### Required external-AI-call prevention
- central HTTP client wrapper with allowlist policy
- any non-allowlisted domain call:
  - hard fail
  - audit event emitted
- runtime model pulls from public registries are treated as blocked external calls
- only internal object storage, mounted artefact paths, or other allowlisted internal model sources may satisfy model loads

### Required export stub contract
Implement stub behavior for these exact routes:
- `GET /projects/{projectId}/export-candidates`
- `GET /projects/{projectId}/export-candidates/{candidateId}`
- `POST /projects/{projectId}/export-requests`
- `GET /projects/{projectId}/export-requests?status={status}&requesterId={requesterId}&candidateKind={candidateKind}&cursor={cursor}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/status`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/release-pack`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/events`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/reviews`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/start-review`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/receipt`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/resubmit`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/decision`
- `GET /projects/{projectId}/export-review?status={status}&agingBucket={agingBucket}&reviewerUserId={reviewerUserId}`

All of those must:
- return disabled/not-implemented
- audit the attempt
- preserve the future single-egress-door architecture
- avoid locking in full Phase 8 schemas too early

### Required minimal stub persistence
Reserve only minimal Phase 0 stub persistence:
- `export_stub_events`
  - `id`
  - `project_id` (nullable)
  - `route`
  - `method`
  - `actor_user_id` (nullable)
  - `request_id`
  - `created_at`

Do not prematurely lock the full Phase 8 export schemas.
Only stub-safe placeholder persistence is allowed here.

### Required baseline policy snapshot bootstrap
Seed a non-editable baseline privacy policy snapshot at deployment:
- `baseline_policy_snapshots`
  - `id`
  - `snapshot_hash`
  - `rules_json`
  - `created_at`
  - `seeded_by`

New projects attach the current baseline snapshot ID at creation and keep it read-only until Phase 7 introduces explicit project policy versions.

### Required audit events
Preserve or reconcile:
- `BASELINE_POLICY_SNAPSHOT_SEEDED`
- `PROJECT_BASELINE_POLICY_ATTACHED`
- `ADMIN_SECURITY_STATUS_VIEWED`

### Required web hardening baseline
- CSP baseline
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy`
- minimal `Permissions-Policy`
- rate limiting on auth and protected endpoints
- `GET /admin/security/status` exposes the internal security-status summary used by the admin security page

### Required web routes
- `/projects/:projectId/export-candidates`
- `/projects/:projectId/export-requests`
- `/projects/:projectId/export-review?status={status}&agingBucket={agingBucket}&reviewerUserId={reviewerUserId}`
- `/admin/security`

## Implementation scope

### 1. Egress deny-by-default baseline
Implement the strongest realistic deny-by-default network posture the repo can support at this stage.

Requirements:
- infrastructure/manifests/config express deny-by-default outbound rules
- only internal dependencies are allowlisted
- public-internet runtime calls are not assumed to be allowed
- docs are explicit about which jobs require internal runners or cluster support
- local dev may remain pragmatic, but production/staging posture must be deny-by-default

If full cluster enforcement cannot be executed locally, still create renderable policy/config and validate what can be validated.

### 2. Central outbound-call enforcement
Implement one central allowlisted network-call path for API/worker/model-related outbound HTTP behavior.

Requirements:
- all relevant outbound HTTP usage routes through the wrapper or policy layer
- non-allowlisted domains hard-fail
- blocked attempts are audited
- this applies to model download/pull behavior as well
- do not let one-off ad hoc HTTP clients slip around the policy

If the repo already has multiple client helpers, unify or wrap them rather than leaving bypasses.

### 3. Model source enforcement
Reconcile the model/runtime foundation with secure-setting enforcement.

Requirements:
- startup validation against the configured model allowlist
- startup validation that required model artefacts exist in mounted local or internal storage
- no runtime public model pulls
- no external AI API dependency introduced
- preserve internal-only execution posture

Use the current repo's model/runtime shape if present, but strengthen it to match the phase contract.

### 4. Export gateway stubs
Implement the exact disabled export stubs now, while preserving later Phase 8 ownership.

Requirements:
- one consistent disabled response contract
- machine-readable error/disabled code
- audit-safe response body
- no accidental export capability
- no download or release-pack bypass
- no placeholder that could be mistaken for a real release path

For `resubmit` and `decision`, reserve later Phase 8 semantics without fully implementing them:
- resubmission later creates a new request revision
- decision later supports `APPROVE | REJECT | RETURN`

### 5. Baseline snapshot bootstrap
If the baseline policy snapshot behavior is absent or weaker than required, implement or reconcile it now.

Requirements:
- deterministic seeded baseline
- stable snapshot hash for same rules
- non-editable baseline snapshot
- new projects attach the current baseline snapshot
- no full Phase 7 policy-authoring UI or workflow in this prompt

### 6. Web hardening and admin security page
Implement or refine:
- security headers
- rate limiting
- admin security status API and page
- environment banner
- disabled export UI surfaces

`/admin/security` must surface at least:
- last successful egress deny test
- current CSP mode
- last backup timestamp
- current reduced-motion preference state (diagnostic only)
- current reduced-transparency preference state (diagnostic only)

Authorization:
- `ADMIN` can access the security page
- `AUDITOR` may have read-only access where phase rules allow
- `RESEARCHER` cannot access the admin security page

The UI must stay restrained, dark, calm, and operational.
Do not turn it into a flashy security dashboard.

### 7. Operational readiness docs and runbooks
Document the baseline for:
- backup snapshots
- secret/config rotation mechanism
- deployment runbook
- key-rotation runbook
- backup-restore runbook

Keep it implementation-grade and specific.
Do not write vague compliance prose.

## Required deliverables

### Backend / infra / security
- egress policy/config/manifests
- central outbound-call allowlist enforcement
- model artefact/source validation
- export stub endpoints
- `export_stub_events` persistence
- security-status endpoint
- rate limiting / headers
- tests

### Web
- `/projects/:projectId/export-candidates`
- `/projects/:projectId/export-requests`
- `/projects/:projectId/export-review`
- `/admin/security`
- disabled export controls and explanation state
- environment banner refinement if needed

### Docs
- secure-setting enforcement doc
- export stub / no-egress posture doc
- runbooks / operational-readiness docs
- any README updates required for local validation

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**`
- `/web/**`
- `/infra/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if a small shared status/badge refinement is required
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- the real Phase 8 export workflow
- reviewer decision workflow
- release packs
- public egress paths
- external AI API integrations
- Phase 7 policy authoring
- giant enterprise security boilerplate that is not actually wired into the repo
- a fake “secure mode” badge with no technical enforcement

## Testing and validation
Before finishing:
1. Verify allowlist enforcement blocks non-allowlisted outbound calls.
2. Verify blocked outbound/model-pull attempts are audited.
3. Verify security headers are present.
4. Verify basic rate limits on auth and protected endpoints.
5. Verify baseline snapshot hash is stable for identical seeded rules.
6. Verify new project records reference the current seeded baseline snapshot.
7. Verify model startup/config validation fails when required artefacts are absent or disallowed.
8. Verify export stub routes are disabled and audited.
9. Verify `RESEARCHER` cannot access the admin security page.
10. Verify `/admin/security/status` reads correctly and respects admin/auditor boundaries.
11. Verify docs match actual commands, paths, and environment expectations.
12. Confirm `/phases/**` is untouched.

If full cluster egress testing cannot run locally, still validate everything possible and state the hard boundary clearly.

## Acceptance criteria
This prompt is complete only if all are true:
- deny-by-default secure-setting posture is encoded
- outbound-call allowlisting is real
- external/public model pulls are blocked
- export routes are present only as disabled audited stubs
- baseline policy snapshot bootstrap is real and deterministic
- web hardening baseline is active
- `/admin/security` exists and shows effective egress/export policy state from backend data
- no uncontrolled egress path exists
- policy and security tests cover allowlisted and denied outbound-call paths with typed error responses
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

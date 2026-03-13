# Phase 6: Redaction Manifest + Evidence Ledger v1 - The Ledger of Record

> Status: ACTIVE
> Web Root: /web
> Active Phase Ceiling: 11
> Execution Policy: Phase 0 through Phase 11 are ACTIVE for this prompt program.
> Web Translation Overlay (ACTIVE): preserve existing workflow intent and phase semantics while translating any legacy desktop or WinUI terms into equivalent browser-native routes, layouts, and interaction patterns under /web.

## Phase Objective
Turn approved Phase 5 privacy-review runs into defensible governance artefacts: a screening-safe redaction manifest and a Controlled-only evidence ledger.

## Entry Criteria
Start Phase 6 only when all are true:
- Phase 5 review is complete for the target run, including any required second review.
- The target Phase 5 run has `redaction_run_reviews.review_status = APPROVED`.
- The approved Phase 5 run has non-null `approved_snapshot_key`, `approved_snapshot_sha256`, and `locked_at`, proving the decision set is frozen and retrievable as immutable bytes.
- A deterministic safeguarded preview exists as `READY` page outputs plus a `READY` `redaction_run_outputs` manifest for the approved run.
- Audit logging, append-only storage patterns, and RBAC from earlier phases are active.

## Scope Boundary
Phase 6 produces internal governance artefacts only.

Out of scope for this phase:
- advanced policy authoring, pseudonym registries, and generalisation logic (Phase 7)
- disclosure review workflow and external release decisions (Phase 8)
- provenance proofs and deposit packaging (Phase 9)

## Phase 6 Non-Negotiables
- Secure web application is the active delivery target: preserve phase behavior and governance contracts while implementing browser-native interaction, routing, and layout patterns from first principles (no desktop-mechanics carryover).
- All workspace and page surfaces inherit the canonical `Obsidian Folio` experience contract (dark-first Fluent 2 tokens, app-window adaptive states, single-fold defaults, keyboard-first accessibility); see `ui-premium-dark-blueprint-obsidian-folio.md`.
1. Manifest generation must be reproducible from approved Phase 5 decisions and run metadata.
2. Evidence ledgers remain Controlled-only even when manifest data is screening-safe.
3. Governance artefacts must not create a new export or download bypass.
4. Artefact integrity must be checkable through stored hashes and append-only lineage.

## Iteration Model
Build Phase 6 in four iterations (`6.0` to `6.3`). Each iteration must tighten governance traceability without creating a new export path.

## Iteration 6.0: Artefact Model + Surfaces

### Goal
Create dedicated manifest and ledger surfaces so governance artefacts are first-class outputs, not side files.

### Web Client Work
#### Routes
- `/projects/:projectId/documents/:documentId/governance`
  - tabs:
    - `Overview`
    - `Runs`
    - `Manifest`
    - `Evidence ledger`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/overview`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/manifest`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/ledger`
- `/projects/:projectId/documents/:documentId/governance/runs/:runId/events`

Navigation contract:
- `/projects/:projectId/documents/:documentId/privacy` owns Phase 5 review, findings, and safeguarded preview work.
- `/projects/:projectId/documents/:documentId/governance` owns Phase 6 manifest and evidence-ledger access once a run is approved.

#### UX rules
- manifest and ledger tabs are visible only for approved Phase 5 runs
- `Manifest` and governance-overview surfaces are screening-safe internal governance outputs readable by `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, and read-only `AUDITOR`
- `Evidence ledger` remains `Controlled-only`, is access-gated separately, and is never shown on Safeguarded-facing surfaces
- manifest access uses authenticated internal streaming or staged retrieval and does not imply export approval
- ledger access uses authenticated internal streaming only and never broadens ordinary project-member access
- governance run detail views show the latest manifest or ledger attempt plus prior attempts when regenerate has been used

### Backend Work
#### Tables
Add `redaction_manifests`:
- `id`
- `run_id`
- `project_id`
- `document_id`
- `source_review_snapshot_key`
- `source_review_snapshot_sha256`
- `attempt_number`
- `supersedes_manifest_id` (nullable)
- `superseded_by_manifest_id` (nullable)
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `manifest_key` (nullable until generation succeeds)
- `manifest_sha256` (nullable until generation succeeds)
- `format_version`
- `started_at`
- `finished_at`
- `canceled_by` (nullable)
- `canceled_at` (nullable)
- `failure_reason` (nullable)
- `created_by`
- `created_at`

Add `redaction_evidence_ledgers`:
- `id`
- `run_id`
- `project_id`
- `document_id`
- `source_review_snapshot_key`
- `source_review_snapshot_sha256`
- `attempt_number`
- `supersedes_ledger_id` (nullable)
- `superseded_by_ledger_id` (nullable)
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `ledger_key` (nullable until generation succeeds)
- `ledger_sha256` (nullable until generation succeeds)
- `hash_chain_version`
- `started_at`
- `finished_at`
- `canceled_by` (nullable)
- `canceled_at` (nullable)
- `failure_reason` (nullable)
- `created_by`
- `created_at`

Add `governance_readiness_projections`:
- `run_id`
- `project_id`
- `document_id`
- `status` (`PENDING | READY | FAILED`)
- `generation_status` (`IDLE | RUNNING | FAILED | CANCELED`)
- `manifest_id` (nullable)
- `ledger_id` (nullable)
- `last_ledger_verification_run_id` (nullable)
- `last_manifest_sha256` (nullable)
- `last_ledger_sha256` (nullable)
- `ledger_verification_status` (`PENDING | VALID | INVALID`)
- `ledger_verified_at` (nullable)
- `ready_at` (nullable)
- `last_error_code` (nullable)
- `updated_at`

Add `governance_run_events`:
- `id`
- `run_id`
- `event_type` (`RUN_CREATED | MANIFEST_STARTED | MANIFEST_SUCCEEDED | MANIFEST_FAILED | MANIFEST_CANCELED | LEDGER_STARTED | LEDGER_SUCCEEDED | LEDGER_FAILED | LEDGER_CANCELED | LEDGER_VERIFY_STARTED | LEDGER_VERIFIED_VALID | LEDGER_VERIFIED_INVALID | LEDGER_VERIFY_CANCELED | REGENERATE_REQUESTED | RUN_CANCELED | READY_SET | READY_FAILED`)
- `actor_user_id` (nullable for system-generated job events)
- `from_status` (nullable)
- `to_status` (nullable)
- `reason` (nullable)
- `created_at`

Add `ledger_verification_runs`:
- `id`
- `run_id`
- `attempt_number`
- `supersedes_verification_run_id` (nullable)
- `superseded_by_verification_run_id` (nullable)
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `verification_result` (`VALID | INVALID`) (nullable until the attempt finishes successfully)
- `result_json` (nullable)
- `started_at`
- `finished_at`
- `canceled_by` (nullable)
- `canceled_at` (nullable)
- `failure_reason` (nullable)
- `created_by`
- `created_at`

Regeneration rules:
- manifest and ledger bytes are append-only artefacts; regenerate never mutates a previously completed row in place
- `status` reflects whether `manifest_id` points at a successful manifest row and `ledger_id` points at a successful ledger row whose latest verification status is `VALID`
- every regenerate request appends a new manifest attempt and ledger attempt, records the forward supersession link on the replaced rows through `superseded_by_manifest_id` and `superseded_by_ledger_id`, and preserves the current ready pointers until the replacement pair finishes successfully and the replacement ledger verifies as `VALID`
- every manifest or ledger attempt pins both `source_review_snapshot_key` and `source_review_snapshot_sha256` from the immutable Phase 5 approval lock; generation is rejected if that frozen snapshot artifact is missing or if its hash no longer matches the locked run-review row
- successful ledger generation automatically enqueues a `ledger_verification_runs` attempt; `POST /ledger/verify` appends an additional verification attempt instead of overwriting the earlier verification lineage, and is not the only route by which a run can become `READY`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/events` reads from append-only `governance_run_events`; timeline and status surfaces use that event stream as the history source of truth rather than reconstructing attempts from mutable projection rows

#### APIs
- `GET /projects/{projectId}/documents/{documentId}/governance/overview`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/overview`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/events`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest/status`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest/entries?category={category}&page={page}&reviewState={reviewState}&from={from}&to={to}&cursor={cursor}&limit={limit}`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest/hash`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger` (`ADMIN` and read-only `AUDITOR`)
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/status` (`ADMIN` and read-only `AUDITOR`)
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/entries?view={list|timeline}&cursor={cursor}&limit={limit}` (`ADMIN` and read-only `AUDITOR`)
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/summary` (`ADMIN` and read-only `AUDITOR`)
- `POST /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/verify` (`ADMIN` only)
  - triggers an additional verification attempt and appends verification state to the append-only governance event stream
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/verify/status` (`ADMIN` and read-only `AUDITOR`)
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/verify/runs` (`ADMIN` and read-only `AUDITOR`)
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/verify/{verificationRunId}` (`ADMIN` and read-only `AUDITOR`)
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/verify/{verificationRunId}/status` (`ADMIN` and read-only `AUDITOR`)
- `POST /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/verify/{verificationRunId}/cancel` (`ADMIN` only)
  - allowed only while the targeted verification attempt is `QUEUED` or `RUNNING`; queued attempts cancel immediately, while running attempts cancel only through cooperative verification-worker shutdown

All manifest and ledger retrieval endpoints stream through authenticated internal handlers. They do not return raw object-store URLs and do not create Phase 8-exportable downloads.

### Tests and Gates (Iteration 6.0)
#### Backend
- artefact rows are created only for approved and locked Phase 5 runs
- hashes are persisted alongside artefact keys
- readiness projection is initialized as `PENDING` with `generation_status = IDLE` before downstream consumers can poll it
- governance timeline and status surfaces read append-only `governance_run_events` so regenerate, verification, failure, and cancel transitions remain reproducible
- manifest and ledger attempts pin both `source_review_snapshot_key` and `source_review_snapshot_sha256`; generation is rejected if the referenced Phase 5 approval snapshot is missing or no longer matches the locked run review row
- successful manifest and ledger rows persist the exact `source_review_snapshot_key` they were built from so later governance and export surfaces can reload the frozen approved decision set rather than verifying by hash alone
- ledger re-verification attempts append `ledger_verification_runs` rows with independent status and result lineage; `ledger/verify/status` and readiness projections do not have to infer history from a single mutable status field
- queued or running verification attempts can be canceled through the explicit verification-cancel endpoint without mutating prior successful verification lineage
- Audit events emitted:
  - `GOVERNANCE_RUNS_VIEWED`
  - `GOVERNANCE_RUN_VIEWED`
  - `MANIFEST_RUN_CREATED`
  - `MANIFEST_RUN_STARTED`
  - `MANIFEST_RUN_FINISHED`
  - `MANIFEST_RUN_FAILED`
  - `MANIFEST_RUN_CANCELED`
  - `REDACTION_MANIFEST_VIEWED`
  - `REDACTION_MANIFEST_ENTRIES_VIEWED`
  - `REDACTION_MANIFEST_HASH_VIEWED`
  - `LEDGER_RUN_CREATED`
  - `LEDGER_RUN_STARTED`
  - `LEDGER_RUN_FINISHED`
  - `LEDGER_RUN_FAILED`
  - `LEDGER_RUN_CANCELED`
  - `GOVERNANCE_OVERVIEW_VIEWED`
  - `GOVERNANCE_EVENTS_VIEWED`
  - `REDACTION_LEDGER_VIEWED`
  - `REDACTION_LEDGER_ENTRIES_VIEWED`
  - `REDACTION_MANIFEST_ACCESSED`
  - `REDACTION_LEDGER_ACCESSED`
  - `REDACTION_LEDGER_VERIFIED`

#### web-surface
- manifest and ledger states render correctly for unavailable, queued or running, failed, and ready states
- `Manifest` and governance-overview tabs hide for users outside `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, and `AUDITOR`
- `Evidence ledger` tabs hide for users outside `ADMIN` and `AUDITOR`

### Exit Criteria (Iteration 6.0)
Manifest and evidence-ledger artefacts have stable storage, routes, and access rules.

## Iteration 6.1: Screening-Safe Manifest Generation

### Goal
Generate a stable manifest that explains what changed without leaking raw sensitive text or implying release approval.

### Backend Work
For every applied redaction include:
- applied action (`MASK`, later `PSEUDONYMIZE` or `GENERALIZE`)
- category
- page and line reference
- safe location reference or bbox token when needed
- `basis_primary` and confidence
- a screening-safe summary of any secondary detector evidence
- final Phase 5 decision state
- baseline policy snapshot hash or explicit Phase 7 policy version reference
- decision timestamp

Rules:
- do not include raw sensitive source text
- do not include reviewer-visible assist explanation text in the manifest; only include a compact secondary-basis summary when present
- manifest bytes must be stable for the same approved run
- manifest must be derivable entirely from the locked `approved_snapshot_key` plus `approved_snapshot_sha256` decision set and run metadata

### Web Client Work
- `Manifest` tab:
  - filterable table by category, page, review state, and timestamp
  - table rows and filters are backed by `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest/entries?category={category}&page={page}&reviewState={reviewState}&from={from}&to={to}&cursor={cursor}&limit={limit}`
  - raw JSON viewer for `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, and read-only `AUDITOR`
  - authenticated internal stream or staged retrieval action with clear `Internal-only` and `Not export-approved` status

### Tests and Gates (Iteration 6.1)
#### Unit
- manifest completeness for every applied redaction
- manifest excludes raw sensitive source text
- manifest serializer is deterministic

#### Integration
- every manifest entry maps back to an audited Phase 5 decision
- manifest hash matches streamed bytes

### Exit Criteria (Iteration 6.1)
The platform can produce a screening-safe manifest that is reproducible and decision-complete.

## Iteration 6.2: Controlled-Only Evidence Ledger

### Goal
Preserve full redaction evidence for `AUDITOR` and `ADMIN` without widening ordinary `PROJECT_LEAD`, `REVIEWER`, or `RESEARCHER` access.

### Backend Work
Store append-only evidence records with:
- before and after text references
- detector evidence summary including `basis_primary` and `basis_secondary_json`
- `assist_explanation_key` and hash when bounded reviewer-facing assist output exists
- actor and timestamp
- override reason when present
- previous hash and row hash for tamper evidence

RBAC:
- ledger access limited to `AUDITOR` and `ADMIN`
- `PROJECT_LEAD` and `REVIEWER` can see decision-history summaries but not raw ledger payloads
- `RESEARCHER` does not access Phase 6 ledger surfaces
- `GET /ledger/entries?view=timeline` is the paged event-history surface for the Evidence Ledger UI; `GET /ledger/summary` provides the diff/impact rollup without forcing clients to scan every raw row

### Web Client Work
- `Evidence ledger` view:
  - event timeline
  - diff summary
  - integrity badge from `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/verify/status`
  - `ADMIN` can trigger re-verification through `POST /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/verify`
  - explicit warning when raw evidence is restricted
  - list and timeline rows are backed by `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/entries?view={list|timeline}&cursor={cursor}&limit={limit}`
  - diff summary is backed by `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/summary`

### Tests and Gates (Iteration 6.2)
#### Unit
- ledger hash-chain verification succeeds for untampered data
- ledger rows are append-only

#### Integration
- permission checks block unauthorized ledger access
- ledger verification status reports `VALID` for untampered chains after the automatic post-generation verification run or an `ADMIN`-triggered re-verification run
- ledger verification history is readable from persisted `ledger_verification_runs` attempts rather than only from the latest projection

#### Governance Gate
- application APIs cannot edit or delete existing ledger rows

### Exit Criteria (Iteration 6.2)
The system retains full evidence for governance without turning that evidence into a broader access surface.

## Iteration 6.3: Operational Integrity + Downstream Handoff

### Goal
Make manifest and ledger generation operationally reliable and ready for downstream policy reruns and the export workflow that follows.

### Backend Work
- add `FINALIZE_MANIFEST` and `FINALIZE_LEDGER` jobs
- add `VERIFY_LEDGER` job
- require successful artefact generation before a run can be marked `governance-ready`
- set `governance_readiness_projections.status` to `READY` only when `manifest_id` points at a `SUCCEEDED` manifest row and `ledger_id` points at a `SUCCEEDED` ledger row whose latest verification status is `VALID`; use `FAILED` only when no such downstream-consumable pair exists
- `FINALIZE_LEDGER` automatically enqueues `VERIFY_LEDGER`; manual `POST /ledger/verify` requests enqueue an additional `VERIFY_LEDGER` attempt without invalidating the last known valid verification result
- when regenerate starts a new attempt for a previously ready run, set `generation_status = RUNNING` but keep `status = READY`, `manifest_id`, `ledger_id`, `ledger_verification_status`, and `ready_at` pinned to the last downstream-consumable pair until the replacement artefacts finish successfully
- when replacement artefacts finish successfully and the replacement ledger verifies as `VALID`, atomically advance `manifest_id`, `ledger_id`, hashes, `ledger_verification_status`, `ledger_verified_at`, and `ready_at`, then reset `generation_status = IDLE`
- when replacement generation fails after a prior ready pair exists, preserve the current ready pointers and surface the failed replacement through `generation_status = FAILED` and `last_error_code`; only runs with no ready pair fall back to `status = FAILED`
- when replacement generation is canceled after a prior ready pair exists, preserve the current ready pointers and surface the canceled replacement through `generation_status = CANCELED`; do not coerce a canceled attempt into `FAILED`
- persist `governance_readiness_projections.status` for Phase 7 and Phase 8 consumers
- APIs:
  - `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/status`
  - `POST /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/regenerate`
    - restricted to `PROJECT_LEAD`, `REVIEWER`, or `ADMIN`
  - `POST /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/cancel`
    - cancels any in-flight manifest and ledger generation attempts for that governance run
- Audit events emitted:
  - `GOVERNANCE_READY_SET`
  - `GOVERNANCE_READY_FAILED`
  - `GOVERNANCE_REGENERATE_REQUESTED`
  - `GOVERNANCE_RUN_CANCELED`
  - `GOVERNANCE_STATUS_VIEWED`

### Web Client Work
- governance-readiness badge on approved Phase 5 runs
- governance run detail surfaces poll `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/status` plus the manifest and ledger status endpoints for readiness, in-flight replacement progress, and active-pointer changes
- governance overview and attempt-history timeline read from `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/events`
- clear failure states with retry affordance for `PROJECT_LEAD`, `REVIEWER`, or `ADMIN`
- in-flight generation states expose `Cancel generation` only to `PROJECT_LEAD`, `REVIEWER`, or `ADMIN`

### Tests and Gates (Iteration 6.3)
#### Integration
- failed finalize jobs do not leave partial artefacts marked ready
- Phase 7 and Phase 8 consumers can detect governance-ready versus incomplete runs
- regenerate appends new manifest and ledger attempts, preserves prior artefacts, and repoints readiness only to the newest verified attempt
- readiness projection changes are visible through the status endpoint and match emitted audit events
- canceled or failed replacement generation leaves prior successful artefacts active for downstream consumers, while the status endpoint still exposes the replacement attempt through `generation_status` and per-attempt status records without collapsing canceled attempts into failures
- successful ledger generation automatically schedules verification so a newly approved Phase 5 run can become `READY` without waiting for a manual admin click
- manifest, ledger, and ledger-verification cancellation transitions are representable in `governance_run_events`, so consumers do not need to infer canceled attempts from projection drift alone

#### E2E
- approved Phase 5 run generates manifest and ledger, then surfaces as ready for export workflow

### Exit Criteria (Iteration 6.3)
Governance artefacts are generated reliably enough to become a hard prerequisite for downstream policy and export workflows.

## Handoff to Later Phases
- Phase 7 upgrades policy control, pseudonymisation, and generalisation while continuing to emit Phase 6 governance artefacts.
- Phase 8 consumes only governance-ready runs, including Phase 7 reruns that still emit Phase 6 artefacts.
- Phase 9 adds lineage proofs and deposit-ready packaging on top of Phase 8-approved outputs.

## Phase 6 Definition of Done
Move to Phase 7 only when all are true:
1. Approved Phase 5 runs generate stable manifests and Controlled-only evidence ledgers.
2. Manifest entries are complete, reproducible, and free of raw sensitive source text.
3. Ledger rows are append-only, hash-verifiable, and tightly access-gated.
4. Governance artefact generation is operationally reliable and statused for downstream phases.
5. No Phase 6 route, API, or download path bypasses later disclosure review in Phase 8.

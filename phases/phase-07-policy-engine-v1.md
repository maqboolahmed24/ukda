# Phase 7: Policy Engine v1 + Pseudonymisation + Generalisation - The Law of Names

> Status: ACTIVE
> Web Root: /web
> Active Phase Ceiling: 11
> Execution Policy: Phase 0 through Phase 11 are ACTIVE for this prompt program.
> Web Translation Overlay (ACTIVE): preserve existing workflow intent and phase semantics while translating any legacy desktop or WinUI terms into equivalent browser-native routes, layouts, and interaction patterns under /web.

## Phase Objective
Replace baseline redaction defaults with explicit per-project policy control, stable pseudonym registries, and auditable generalisation rules for indirect identifiers, while allowing local LLM assistance for explanation and risk grouping under rule-authoritative policy control.

## Entry Criteria
Start Phase 7 only when all are true:
- Phase 6 governance artefacts are generated reliably for approved runs.
- Project-level role separation is strong enough to gate policy editing and activation.
- Existing mask-first behavior is stable enough to compare against reruns.

## Scope Boundary
Phase 7 upgrades policy behavior and reuse of governance artefacts.

Project-scoped policy authoring remains separate from document-scoped privacy reruns so policy administration does not get buried inside a single-document workflow.

Out of scope for this phase:
- disclosure review queues and external release decisions (Phase 8)
- provenance proofs and deposit packaging (Phase 9)

## Phase 7 Non-Negotiables
- Secure web application is the active delivery target: preserve phase behavior and governance contracts while implementing browser-native interaction, routing, and layout patterns from first principles (no desktop-mechanics carryover).
- All workspace and page surfaces inherit the canonical `Obsidian Folio` experience contract (dark-first Fluent 2 tokens, app-window adaptive states, single-fold defaults, keyboard-first accessibility); see `ui-premium-dark-blueprint-obsidian-folio.md`.
1. Every rerendered output must be pinned to an explicit policy version.
2. Policy changes never mutate historical outputs; they create new runs and new artefacts.
3. Pseudonym maps and reversible evidence remain Controlled-only.
4. Indirect-identifier handling must be explainable, reviewable, and regression-tested.
5. Explicit `redaction_policies` begin in Phase 7 and do not retroactively redefine historical Phase 5 baseline-snapshot runs.
6. Local LLM assistance may explain or group risk signals, but policy rules remain the authoritative decision layer.

## Iteration Model
Build Phase 7 in four iterations (`7.0` to `7.3`). Each iteration must improve configurability without making redaction behavior harder to reason about.

## Iteration 7.0: Policy Model + Activation Workflow

### Goal
Introduce a first-class policy model instead of hard-coded thresholds and action rules.

### Backend Work
Add `redaction_policies`:
- `id`
- `project_id`
- `policy_family_id`
- `name`
- `version`
- `seeded_from_baseline_snapshot_id` (nullable)
- `supersedes_policy_id` (nullable)
- `superseded_by_policy_id` (nullable)
- `rules_json`
- `version_etag`
- `status` (`DRAFT | ACTIVE | RETIRED`)
- `created_by`
- `created_at`
- `activated_by` (nullable)
- `activated_at` (nullable)
- `retired_by` (nullable)
- `retired_at` (nullable)
- `validation_status` (`NOT_VALIDATED | VALID | INVALID`)
- `validated_rules_sha256` (nullable)
- `last_validated_by` (nullable)
- `last_validated_at` (nullable)

Add `project_policy_projections`:
- `project_id`
- `active_policy_id` (nullable)
- `active_policy_family_id` (nullable)
- `updated_at`

Rules:
- Phase 7 v1 supports one active policy lineage per project; `policy_family_id` stays stable across that sole lineage and is not used to permit parallel active families in v1
- activating a policy creates a new explicit version lineage starting in Phase 7
- the first explicit policy lineage for a project may be seeded from the attached Phase 0 `baseline_policy_snapshot_id`; that baseline snapshot becomes the lineage origin recorded in `seeded_from_baseline_snapshot_id`
- new draft revisions keep a shared `policy_family_id` and point `supersedes_policy_id` at the previous revision in that family
- activating a new revision retires any previous `ACTIVE` revision in the project, updates `project_policy_projections.active_policy_id` and `active_policy_family_id`, and never rebinds historical runs
- historical Phase 5 runs keep their pinned baseline snapshots and are never rewritten to point at later `redaction_policies`
- only `ACTIVE` revisions can be retired; `DRAFT` revisions remain editable or supersedable rather than moving through the retire path
- `GET /projects/{projectId}/policies/active` reads `project_policy_projections.active_policy_id` instead of scanning policy rows for `status = ACTIVE`
- any `PATCH` to a `DRAFT` policy clears `validation_status` back to `NOT_VALIDATED` and clears `validated_rules_sha256` until validation is rerun against the edited rules
- activation is rejected unless the target revision is still `DRAFT`, `validation_status = VALID`, and `validated_rules_sha256` matches the current `rules_json` hash for that exact revision

Rules support:
- category actions
- confidence thresholds
- reviewer requirements
- escalation flags
- pseudonymisation mode and aliasing rules
- generalisation transforms by category and specificity ceiling
- reviewer explanation mode for local LLM-assisted risk summaries

Add `policy_events`:
- `id`
- `policy_id`
- `event_type` (`POLICY_CREATED | POLICY_EDITED | POLICY_VALIDATED_VALID | POLICY_VALIDATED_INVALID | POLICY_ACTIVATED | POLICY_RETIRED`)
- `actor_user_id`
- `reason` (nullable)
- `rules_sha256`
- `rules_snapshot_key`
- `created_at`

APIs:
- `GET /projects/{projectId}/policies`
- `GET /projects/{projectId}/policies/active`
- `POST /projects/{projectId}/policies`
  - creates a new draft revision and never mutates an existing policy row in place
- `GET /projects/{projectId}/policies/{policyId}`
- `GET /projects/{projectId}/policies/{policyId}/events`
- `PATCH /projects/{projectId}/policies/{policyId}`
  - requires the caller's current `version_etag` and saves edits only while the targeted policy revision remains `DRAFT`; `ACTIVE` and `RETIRED` revisions are immutable
  - rejects stale `version_etag` values instead of silently overwriting a newer draft edit, and returns the newly projected `version_etag`
- `GET /projects/{projectId}/policies/{policyId}/compare?against={otherPolicyId}`
- `GET /projects/{projectId}/policies/{policyId}/compare?againstBaselineSnapshotId={baselineSnapshotId}`
  - requires exactly one comparison target: either `against` or `againstBaselineSnapshotId`, but never both in the same request
  - rejects cross-project or cross-family policy comparisons so diffs always compare a coherent policy lineage
  - allows a baseline-snapshot comparison only when the target policy lineage was seeded from that exact `baselineSnapshotId`
- `POST /projects/{projectId}/policies/{policyId}/validate`
  - evaluates the draft or target revision for contradictory rules, unsupported transforms, and reviewer-gate inconsistencies before activation, then persists `validation_status`, `validated_rules_sha256`, `last_validated_by`, and `last_validated_at`
- `POST /projects/{projectId}/policies/{policyId}/activate`
  - rejected unless the latest successful validation still matches the exact draft content being activated
- `POST /projects/{projectId}/policies/{policyId}/retire`

`GET /projects/{projectId}/policies/{policyId}/events` reads from append-only `policy_events`; policy history and timeline views must not infer revision history from mutable policy status fields alone.
Every event that creates, edits, validates, activates, or retires a policy revision persists the exact rule snapshot hash and immutable snapshot key for that point in time, so draft history remains reconstructable even though the current `rules_json` on a `DRAFT` row can still change before activation.

These policy routes split read and mutate access explicitly:
- `GET` policy list, detail, and compare surfaces are readable by `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, and read-only `AUDITOR`.
- `POST`/`PATCH` create, edit, validate, activate, and retire actions are restricted to `PROJECT_LEAD` and `ADMIN`.

### Web Client Work
- project-scoped routes:
- `/projects/:projectId/policies`
- `/projects/:projectId/policies/active`
- `/projects/:projectId/policies/:policyId`
- `/projects/:projectId/policies/:policyId/compare?against={otherPolicyId}`
- `/projects/:projectId/policies/:policyId/compare?againstBaselineSnapshotId={baselineSnapshotId}`
- compare navigation and generated links must include exactly one comparison target and must never emit both query parameters in the same URL
- policy list/detail/compare views are readable by `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, and read-only `AUDITOR`
- policy editor for `PROJECT_LEAD` and `ADMIN`
- version diff view between policy revisions
- activation flow with validation summary
- policy history timeline powered by `/projects/{projectId}/policies/{policyId}/events`
- retire action with explicit impact summary before a policy leaves active service

Phase 7 RBAC matrix:
- `PROJECT_LEAD`: create draft revisions, edit drafts, validate drafts, compare policy revisions, activate policies, request policy reruns, and view rerun compares.
- `REVIEWER`: view active policy summaries and rerun compare surfaces; cannot draft, edit, or activate policies.
- `ADMIN`: same write access as `PROJECT_LEAD`, including validation, plus governance oversight across projects.
- `AUDITOR`: read-only access to policy summaries, policy comparisons, rerun comparisons, and pseudonym registry views.
- `RESEARCHER`: no access to Phase 7 policy-authoring or pseudonym-registry surfaces.

### Tests and Gates (Iteration 7.0)
#### Unit
- policy evaluation returns deterministic actions for the same finding input
- malformed rules are rejected
- editing a draft invalidates any prior successful validation until `POST /validate` runs again

#### Integration
- only one active policy version is allowed per project, and the active row's `policy_family_id` matches `project_policy_projections.active_policy_family_id`
- run records capture policy ID and version
- activation is blocked when `validation_status != VALID` or when `validated_rules_sha256` no longer matches the current draft rules
- stale draft edits are rejected unless the caller supplies the current `version_etag`
- policy history timeline reconstructs create, edit, validate, activate, and retire actions from append-only `policy_events` instead of inferring chronology from mutable policy rows
- policy event history can reconstruct the exact rule snapshot for every create, edit, validate, activate, and retire step from `rules_sha256` plus `rules_snapshot_key`
- compare surfaces can diff the first explicit policy revision against its seeded Phase 0 baseline snapshot when `seeded_from_baseline_snapshot_id` matches the requested baseline
- compare requests reject ambiguous input when both `against` and `againstBaselineSnapshotId` are provided
- only `PROJECT_LEAD` or `ADMIN` can create, activate, or retire policies; `AUDITOR` stays read-only on policy surfaces
- Audit events emitted:
  - `POLICY_CREATED`
  - `POLICY_LIST_VIEWED`
  - `POLICY_ACTIVE_VIEWED`
  - `POLICY_DETAIL_VIEWED`
  - `POLICY_EVENTS_VIEWED`
  - `POLICY_UPDATED`
  - `POLICY_VALIDATION_REQUESTED`
  - `POLICY_ACTIVATED`
  - `POLICY_RETIRED`
  - `POLICY_COMPARE_VIEWED`

### Exit Criteria (Iteration 7.0)
Projects can define and activate explicit privacy policies with traceable versions.

## Iteration 7.1: Stable Pseudonym Registries

### Goal
Support project-scoped aliases that preserve linkage where policy allows it without exposing raw identity.

### Backend Work
- `pseudonym_registry_entries`:
- `id`
- `project_id`
- `source_run_id`
- `source_fingerprint_hmac_sha256`
- `alias_value`
- `policy_id`
- `salt_version_ref`
- `alias_strategy_version`
- `created_by`
- `created_at`
- `last_used_run_id` (nullable)
- `updated_at`
- `status` (`ACTIVE | RETIRED`)
- `retired_at` (nullable)
- `retired_by` (nullable)
- `supersedes_entry_id` (nullable)
- `superseded_by_entry_id` (nullable)

Registry rules:
- pseudonym generation uses the project-scoped salt identified by `salt_version_ref` plus the recorded `alias_strategy_version`; the persisted fingerprint is `HMAC-SHA256(canonical_normalized_source_value, project_secret_for_salt_version_ref)`, and plain source text or plain SHA-256 fingerprints must never be stored
- lookups are deterministic for the same `(project_id, source_fingerprint_hmac_sha256, policy_id, salt_version_ref, alias_strategy_version)` tuple
- only one `ACTIVE` registry row may exist for a given `(project_id, source_fingerprint_hmac_sha256, policy_id, salt_version_ref, alias_strategy_version)` tuple; repeated reuse appends `ENTRY_REUSED` instead of creating a duplicate row
- `alias_value` must be unique within the same active project/salt/strategy scope so two different fingerprints cannot silently collide onto the same live alias
- changing `salt_version_ref` or `alias_strategy_version` requires a new registry lineage through `supersedes_entry_id`; the system must not silently reuse aliases from an incompatible lineage
- Phase 7 pseudonymisation uses the existing Phase 6 manifest and ledger artefacts rather than creating a second reversible-evidence system

Add `pseudonym_registry_entry_events`:
- `id`
- `entry_id`
- `event_type` (`ENTRY_CREATED | ENTRY_REUSED | ENTRY_RETIRED`)
- `run_id`
- `actor_user_id` (nullable for system reuse events)
- `created_at`

APIs:
- `GET /projects/{projectId}/pseudonym-registry`
- `GET /projects/{projectId}/pseudonym-registry/{entryId}`
- `GET /projects/{projectId}/pseudonym-registry/{entryId}/events`

These pseudonym-registry routes are readable only by `PROJECT_LEAD`, `ADMIN`, and read-only `AUDITOR`.
Registry entries are system-generated only in v1. There are no manual create, edit, or delete endpoints.

### Web Client Work
- Controlled-only route:
  - `/projects/:projectId/pseudonym-registry`
  - `/projects/:projectId/pseudonym-registry/:entryId`
  - `/projects/:projectId/pseudonym-registry/:entryId/events`
- Controlled-only pseudonym registry view
- entry detail view includes an events timeline backed by `GET /projects/{projectId}/pseudonym-registry/{entryId}/events`
- output preview distinguishes masked values from pseudonymised values

### Tests and Gates (Iteration 7.1)
#### Unit
- same entity in same project maps to same alias
- same entity across projects maps differently
- two different fingerprints in the same active project/salt/strategy scope cannot produce the same live `alias_value`
- persisted fingerprints are keyed HMACs, so low-entropy raw identifiers cannot be recovered by dictionary attack against a plain hash column

#### Integration
- rerender with same policy version, `salt_version_ref`, and `alias_strategy_version` preserves aliases
- changing `salt_version_ref` requires an explicit new registry lineage rather than silently reusing an alias from an incompatible salt generation
- repeated reuse of the same fingerprint under the same active policy and salt lineage appends `ENTRY_REUSED` instead of inserting a duplicate active registry row
- users outside `PROJECT_LEAD`, `ADMIN`, and `AUDITOR` cannot access registry views
- `PSEUDONYM_REGISTRY_VIEWED`, `PSEUDONYM_REGISTRY_ENTRY_VIEWED`, and `PSEUDONYM_REGISTRY_EVENTS_VIEWED` are audited for registry reads

### Exit Criteria (Iteration 7.1)
Pseudonymisation is stable, project-isolated, and consistent with existing governance artefacts.

## Iteration 7.2: Generalisation + Indirect Identifier Handling

### Goal
Allow policies to lower disclosure risk through controlled reduction of specificity.

### Backend Work
Support generalisation actions:
- exact date -> month/year or year only
- town -> county or region
- exact age -> age band

Add indirect-risk heuristics for combinations such as:
- place + rare occupation + exact date
- uncommon kinship term + small locality
- use optional local LLM assistance to group or explain ambiguous indirect-risk combinations for reviewers
- keep policy rules authoritative for the final action applied to the output

Policy reruns remain document-scoped and emit new `redaction_runs`, `redaction_manifests`, and `redaction_evidence_ledgers` rather than mutating prior artefacts.

### Web Client Work
- policy controls for granularity by category
- reviewer-facing explanation of why a generalisation rule fired, including optional local LLM-assisted grouping notes
- run comparison view showing masked vs pseudonymised vs generalised output

### Tests and Gates (Iteration 7.2)
#### Unit
- date, place, and age banding rules are deterministic
- generalized output never exceeds the configured specificity ceiling
- local LLM-assisted explanations cannot request a more specific output than the active policy allows

#### Integration
- indirect-risk findings can be rerendered under new policy versions without mutating prior runs
- local LLM-assisted grouping remains reviewer-visible metadata and does not bypass deterministic policy evaluation

### Exit Criteria (Iteration 7.2)
Projects can reduce specificity deliberately instead of relying on masking alone.

## Iteration 7.3: Policy Reruns + Regression Gates

### Goal
Make policy evolution safe by showing exactly what changes and blocking contradictory behavior.

### Backend Work
- rerun orchestration from prior reviewed decisions plus new policy version
- diffs for safeguarded preview, manifest, and ledger summaries
- activation gates for contradictory or incomplete rules
- rerendered Phase 7 outputs extend `redaction_runs` with explicit `policy_id`, `policy_family_id`, and `policy_version` values so later provenance and export phases do not have to infer policy lineage from detached snapshots

APIs:
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/rerun?policyId={policyId}`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`

The rerun API is available to `PROJECT_LEAD` and `ADMIN`. `REVIEWER` remains read-only on rerun compare surfaces and cannot mint a new rerun candidate.
Rerun requests are rejected unless they reference an explicit target `policyId`.
Rerun requests are also rejected unless the source run has `redaction_run_reviews.review_status = APPROVED`.
Rerun requests are also rejected unless the source run is already governance-ready from Phase 6.
Rerun requests are also rejected unless the target `policyId` belongs to the same project, is either the current `ACTIVE` revision or a validated `DRAFT` revision in the same project lineage, has `validation_status = VALID`, and its `validated_rules_sha256` still matches the stored `rules_json` for that revision.
Reruns against a validated `DRAFT` revision remain comparison-only candidates; they do not activate that policy revision or alter `project_policy_projections.active_policy_id`.
The compare API is available to `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, and read-only `AUDITOR` when both runs are governance-ready.

### Web Client Work
- document-scoped compare route:
  - `/projects/:projectId/documents/:documentId/privacy/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}&page={pageNumber}&findingId={findingId}&lineId={lineId}&tokenId={tokenId}`
- compare surface is available to `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, and read-only `AUDITOR`
- project-scoped policy pages link into the document-scoped privacy compare route once a rerun candidate exists
- compare runs by policy version
- changed-pages summary
- pre-activation warnings for broad allow rules or inconsistent thresholds

### Tests and Gates (Iteration 7.3)
#### Integration
- reruns are reproducible from the same reviewed decisions
- diff summaries match underlying artefact changes
- rerun creation is blocked for `RESEARCHER`, `REVIEWER`, and `AUDITOR`
- validated `DRAFT` policy revisions can be rerun for comparison without activating them, while invalid or retired targets remain rejected
- Audit events emitted:
  - `POLICY_RERUN_REQUESTED`
  - `POLICY_RUN_COMPARE_VIEWED`

#### Security
- deny-by-default permission checks for all policy and registry routes

### Exit Criteria (Iteration 7.3)
Policy behavior is configurable per project without becoming opaque, brittle, or historically destructive.

## Handoff to Later Phases
- Phase 8 consumes policy-pinned, governance-ready artefacts and handles disclosure review plus egress control.
- Phase 9 layers provenance proofs and deposit-ready packaging on top of Phase 8-approved outputs.

## Phase 7 Definition of Done
Move to Phase 8 only when all are true:
1. Projects can activate explicit policy versions that drive rerendered outputs reproducibly.
2. Pseudonym registries are stable within a project and isolated across projects.
3. Generalisation and indirect-identifier handling are implemented with deterministic rules and reviewable explanations.
4. Policy reruns produce new outputs and readable diffs instead of mutating history.
5. Phase 6 manifest and ledger artefacts continue to work as the governance record for Phase 7 outputs.

You are the implementation agent for UKDE. Work directly in the repository. Do not ask clarifying questions. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: assume zero chat memory and reread the repo plus the listed phase files before changing anything.
- Sequenced: if the repo already contains partial implementation from earlier prompts, extend and reconcile it instead of restarting from scratch.

The actual product source of truth is the extracted `/phases` directory in repo root. Do not mention or expect a zip. Read `/phases` first on every run.

## Mandatory first actions
1. Inspect the full repository tree.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/phase-07-policy-engine-v1.md`
3. Then review the current repository generally — policy engine foundations, governance artefacts, masking outputs, storage adapters, typed contracts, current routes, audit code, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second pseudonym registry, a second aliasing strategy system, or conflicting access-control semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for pseudonym registry fields, HMAC fingerprint rules, alias uniqueness, project isolation, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that pseudonym maps and reversible evidence remain Controlled-only and that deterministic alias reuse is project-scoped, policy-aware, and salt-versioned.

## Objective
Implement stable pseudonym registries with deterministic mapping and governed access control.

This prompt owns:
- the canonical pseudonym registry schema
- deterministic HMAC-based source fingerprinting
- alias strategy and salt-version lineage rules
- append-only pseudonym entry events
- controlled-only registry routes and read surfaces
- pseudonym reuse behavior for policy-controlled rerenders
- output-preview differentiation between masked and pseudonymized values
- regression coverage for alias stability and isolation

This prompt does not own:
- policy editor UX
- indirect-identifier generalisation rules
- policy rerun orchestration
- public or external registry access
- a second reversible-evidence system

## Phase alignment you must preserve
From Phase 7 Iteration 7.1:

### Required tables
Implement or reconcile:
- `pseudonym_registry_entries`
- `pseudonym_registry_entry_events`

`pseudonym_registry_entries` fields to preserve:
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
- `last_used_run_id`
- `updated_at`
- `status` (`ACTIVE | RETIRED`)
- `retired_at`
- `retired_by`
- `supersedes_entry_id`
- `superseded_by_entry_id`

`pseudonym_registry_entry_events`:
- `id`
- `entry_id`
- `event_type` (`ENTRY_CREATED | ENTRY_REUSED | ENTRY_RETIRED`)
- `run_id`
- `actor_user_id`
- `created_at`

### Registry rules
- pseudonym generation uses the project-scoped salt identified by `salt_version_ref` plus `alias_strategy_version`
- persisted fingerprint is `HMAC-SHA256(canonical_normalized_source_value, project_secret_for_salt_version_ref)`
- plain source text and plain SHA-256 fingerprints must never be stored
- lookups are deterministic for the same `(project_id, source_fingerprint_hmac_sha256, policy_id, salt_version_ref, alias_strategy_version)` tuple
- only one `ACTIVE` row may exist for that tuple
- repeated reuse appends `ENTRY_REUSED` instead of creating a duplicate active row
- `alias_value` must be unique within the same active project/salt/strategy scope
- changing `salt_version_ref` or `alias_strategy_version` requires a new registry lineage through `supersedes_entry_id`
- Phase 7 pseudonymisation uses existing Phase 6 manifest and ledger artefacts rather than creating a second reversible-evidence system

### APIs and routes
- `GET /projects/{projectId}/pseudonym-registry`
- `GET /projects/{projectId}/pseudonym-registry/{entryId}`
- `GET /projects/{projectId}/pseudonym-registry/{entryId}/events`
- `/projects/:projectId/pseudonym-registry`
- `/projects/:projectId/pseudonym-registry/:entryId`
- `/projects/:projectId/pseudonym-registry/:entryId/events`

### RBAC
- registry routes readable only by `PROJECT_LEAD`, `ADMIN`, and read-only `AUDITOR`
- system-generated only in v1
- no manual create, edit, or delete endpoints

## Implementation scope

### 1. Canonical registry schema
Implement or refine the pseudonym registry schema.

Requirements:
- one authoritative registry store
- no second mapping cache
- append-only lifecycle with active and retired entries
- event history is append-only and queryable
- registry remains Controlled-only

### 2. HMAC fingerprinting and normalization
Implement the canonical fingerprint path.

Requirements:
- canonical normalization of source value before hashing
- HMAC-SHA256 using project-scoped secret identified by `salt_version_ref`
- no plain source storage
- no plain SHA-256 storage
- deterministic same-project/same-salt/same-strategy reuse
- cross-project isolation

### 3. Alias generation and uniqueness
Implement deterministic alias generation and uniqueness checks.

Requirements:
- alias generation strategy version is explicit
- alias uniqueness enforced within active project/salt/strategy scope
- collision handling remains deterministic and safe
- same source in the same scope resolves to same active alias
- different fingerprints cannot silently share the same active alias

### 4. Entry reuse and lineage
Implement or refine reuse behavior.

Requirements:
- repeated reuse appends `ENTRY_REUSED`
- `last_used_run_id` updates coherently on reuse
- salt or strategy changes force new lineage
- historical entries remain immutable and queryable
- no silent alias rebinding across incompatible lineage generations

### 5. Read surfaces and route shells
Implement minimal but coherent registry read surfaces.

Requirements:
- registry list
- entry detail
- entry events timeline
- Controlled-only access messaging
- calm empty/loading/error states
- event history backed by the canonical event table

### 6. Output differentiation
Refine current privacy/governance views where low churn and useful.

Requirements:
- output preview distinguishes masked from pseudonymized values
- no raw identity leakage
- no broad UI redesign
- no second registry UI outside the canonical project-scoped routes

### 7. Audit and tests
Use the canonical audit path and add regression coverage.

At minimum cover:
- same entity in same project maps to same alias
- same entity across projects maps differently
- two different fingerprints in same active scope cannot produce the same live alias
- persisted fingerprints are keyed HMACs
- changing salt version requires explicit new lineage
- users outside `PROJECT_LEAD`, `ADMIN`, and `AUDITOR` cannot access registry views
- registry read events are audited

### 8. Documentation
Document:
- pseudonym registry schema and event model
- HMAC fingerprint rules
- alias uniqueness and lineage rules
- access control
- what Prompt 74 and 76 will use from this registry later

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- pseudonym registry schema
- HMAC fingerprint and alias generation logic
- append-only entry events
- typed read APIs
- tests

### Web
- pseudonym registry list/detail/events routes
- controlled-only registry UI
- masked vs pseudonymized output distinction where low churn and useful

### Docs
- pseudonym registry and aliasing doc
- controlled-access and lineage doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**` if a tiny registry-use helper is required
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small registry/detail/timeline refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- policy rerun orchestration
- generalisation rules
- public registry access
- manual registry create/edit/delete flows
- a second pseudonym system

## Testing and validation
Before finishing:
1. Verify same entity in same project maps to same alias.
2. Verify same entity across projects maps differently.
3. Verify alias uniqueness within active project/salt/strategy scope.
4. Verify fingerprints are HMAC-based and do not expose raw identifiers.
5. Verify salt-version or strategy changes require new registry lineage.
6. Verify unauthorized users cannot access registry routes.
7. Verify registry read events are audited.
8. Verify docs match the implemented pseudonym registry behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the stable pseudonym registry is real
- deterministic mapping is real
- project isolation is real
- governed access control is real
- later policy reruns can reuse the registry without contract churn
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

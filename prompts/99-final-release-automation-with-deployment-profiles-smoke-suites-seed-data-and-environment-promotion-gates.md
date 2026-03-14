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
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-08-safe-outputs-export-gateway.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — CI/CD workflows, infra configs, environment profiles, seed data tooling, smoke suites, capacity/recovery/security readiness outputs, runbooks, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second promotion pipeline, a second seed-data path, or conflicting environment gate semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for secure environment separation, single egress door, and launch-readiness expectations.
- Official docs win only for implementation mechanics.
- Preserve the rule that production promotion is gated by evidence, not manual optimism, and that non-prod seed data never weakens the controlled environment model.

## Objective
Ship final release automation with deployment profiles, smoke suites, seed data, and environment-promotion gates.

This prompt owns:
- environment-specific deployment profiles
- final promotion workflows and gate conditions
- smoke suites for core end-to-end flows
- non-production seed-data packs and refresh tooling
- production-safe configuration and rollout sequencing
- rollback-aware promotion automation
- machine-readable release gate results

This prompt does not own:
- incident response itself
- public launch messaging
- a second deployment system
- ad hoc manual prod pushes outside the gated pipeline

## Phase alignment you must preserve
From Phase 0 secure environment separation, Phase 8 gateway-only egress, and Phase 11 go-live readiness:

### Environment separation
- `dev`, `staging`, and `prod` are explicit
- no shared secrets
- internal registry and internal services remain authoritative
- production egress still goes only through the approved gateway path

### Phase 11 go-live readiness intent
- release readiness checklist
- change management and rollback procedure
- on-call ownership and escalation paths
- named operational ownership for model service map, approved-model lifecycle, and rollback execution
- go-live rehearsal covering ingest through export review
- approved-model rollback rehearsal completed

### Smoke-suite expectations
Core product slices should be covered, such as:
- auth and project access
- ingest and document handling
- transcription/privacy/governance happy-path sanity
- export request and review flow sanity
- no-bypass controls sanity
- key admin operations/status sanity

These may be environment-specific and should stay stable, not overbroad.

## Implementation scope

### 1. Deployment profiles
Implement or refine environment deployment profiles.

Requirements:
- explicit `dev`, `staging`, `prod` profile behavior
- clear config isolation
- no shared secret material
- profile-aware routing to internal services
- safe defaults for non-prod
- no second parallel deployment-profile scheme

### 2. Promotion automation
Implement or refine gated promotion workflows.

Requirements:
- promotion from environment to environment is machine-gated
- gates incorporate readiness evidence from earlier prompts
- rollback path is explicit
- promotion history is reviewable through pipeline artifacts or equivalent canonical records
- no “push straight to prod” bypass

### 3. Smoke suites
Implement or refine stable smoke suites.

Requirements:
- cover the core end-to-end flow slices that matter for launch confidence
- run automatically in the right environments
- keep scope tight enough to stay reliable
- surface failures clearly
- no second smoke framework

### 4. Seed data and non-prod refresh
Implement or refine non-production seed-data packs.

Requirements:
- safe, synthetic or controlled non-prod data only
- deterministic refresh/reset path
- supports dev and staging workflows
- does not weaken governed data boundaries
- no production seeding shortcuts

### 5. Rollback-aware automation
Integrate rollback into the promotion flow.

Requirements:
- rollback procedure is encoded into deployment automation where feasible
- approval and evidence gates are rechecked on rollback-sensitive paths
- rollback does not bypass security or gateway constraints
- model rollback rehearsal results can be referenced

### 6. Documentation
Document:
- deployment profiles
- promotion gates
- smoke-suite scope
- seed-data lifecycle
- rollback-aware promotion behavior
- how Prompt 100 consumes these artifacts in final ship/no-ship review

## Required deliverables
Create or refine the closest coherent equivalent of:

### CI/CD / infra / automation
- deployment profiles
- gated promotion workflows
- smoke suites
- non-prod seed-data tooling
- rollback-aware automation
- tests or checks proving gate wiring

### Docs
- release automation and promotion-gate doc
- seed-data and smoke-suite doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- CI/workflow files
- `/infra/**`
- deployment/config helpers
- seed-data scripts/tools
- `/api/**` or `/web/**` only if tiny smoke-test hooks are strictly needed
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- incident workflow UI
- public launch messaging
- a second deployment system
- production data seeding shortcuts
- ungated manual prod release paths

## Testing and validation
Before finishing:
1. Verify deployment profiles are explicit and isolated.
2. Verify promotion workflows enforce readiness gates.
3. Verify smoke suites execute against the intended environments.
4. Verify non-prod seed-data refresh is deterministic and safe.
5. Verify rollback-aware automation exists and is documented.
6. Verify docs match the implemented release automation and promotion behavior.
7. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- deployment profiles are real
- promotion gates are real
- smoke suites are real
- non-prod seed data is real and safe
- the repo has a credible release automation story
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

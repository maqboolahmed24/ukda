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
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/phase-06-redaction-manifest-ledger-v1.md`
   - `/phases/phase-08-safe-outputs-export-gateway.md`
3. Then review the current repository generally — reviewed redaction output manifests, governance-related models if any, privacy approval snapshots, storage adapters, typed contracts, routes, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second governance route family, a second artefact lineage model, or conflicting candidate-snapshot semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. current repository state as the implementation reality to reconcile with
  2. this prompt
  3. the precise `/phases` files listed above
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for governance route ownership, artefact lineage, readiness projections, and candidate-snapshot contracts.
- Official docs win only for implementation mechanics.
- Preserve the rule that governance artefacts are first-class outputs, immutable attempts are append-only, and later export candidates pin the exact governance pair that made them eligible.

## Objective
Model manifests, candidate snapshots, and artefact-lineage contracts for governed downstream outputs.

This prompt owns:
- the Phase 6 governance IA and route family
- redaction manifest and evidence-ledger attempt models
- governance readiness projections and governance event streams
- ledger verification-run lineage scaffolding
- export-candidate snapshot contract scaffolding from Phase 8
- immutable artefact supersession and readiness-pointer rules
- governance status and event read surfaces
- shell-level governance overview and run-detail surfaces

This prompt does not own:
- screening-safe manifest generation
- evidence-ledger content generation
- export request workflows
- release-pack generation
- a second artefact-lineage system

## Phase alignment you must preserve
From Phase 6 Iteration 6.0 and Phase 8 candidate-snapshot rules:

### Required governance routes
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
- `/privacy` owns Phase 5 review and safeguarded preview work
- `/governance` owns Phase 6 manifest and evidence-ledger access once a run is approved

### Required tables
Implement or reconcile:
- `redaction_manifests`
- `redaction_evidence_ledgers`
- `governance_readiness_projections`
- `governance_run_events`
- `ledger_verification_runs`

Use the exact core field sets from Phase 6.0, including:
- source review snapshot key and sha256 pinning
- attempt numbers
- supersedes / superseded-by lineage
- manifest and ledger hashes
- readiness projection with:
  - `status`
  - `generation_status`
  - current ready pointers
  - latest verification state

### Required candidate snapshot contract
Prepare or reconcile `export_candidate_snapshots` from Phase 8:

Core fields include:
- `project_id`
- `source_phase`
- `source_artifact_kind`
- `source_run_id`
- `source_artifact_id`
- pinned governance run / manifest / ledger IDs and hashes
- policy snapshot hash and later policy lineage fields
- `candidate_kind`
- `artefact_manifest_json`
- `candidate_sha256`
- eligibility and supersession fields

Rules:
- Phase 6 candidates later pin `source_artifact_kind = REDACTION_RUN_OUTPUT`
- candidate lineage is immutable and append-only
- no live governance projection may replace pinned governance lineage inside a candidate snapshot

### Required APIs
Implement or refine the Phase 6.0 read surfaces:
- `GET /projects/{projectId}/documents/{documentId}/governance/overview`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/overview`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/events`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest/status`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/ledger/status`

This prompt may scaffold candidate-snapshot typed contracts and internal helpers, but it does not need to implement full user-facing candidate-list routes yet if that would overstep Phase 8 workflows.

### UX rules
- manifest and governance-overview surfaces are screening-safe internal outputs readable by `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, and read-only `AUDITOR`
- evidence ledger remains `Controlled-only`, access-gated separately, and never shown on safeguarded-facing surfaces
- governance run detail views show latest attempt plus prior attempts when regenerate is later used
- manifest and ledger tabs must remain honest about not-yet-generated content in this prompt

## Implementation scope

### 1. Canonical governance route family
Implement or refine the governance IA and shell.

Requirements:
- no second governance route family
- tabs and run-detail routes follow the phase contract
- shell, breadcrumbs, and page headers remain coherent
- manifest/ledger tabs respect role visibility rules
- not-yet-generated states are calm and truthful

### 2. Artefact attempt models
Implement or reconcile the canonical manifest and ledger attempt models.

Requirements:
- append-only attempts
- pinned source review snapshot key and hash
- attempt lineage via supersedes fields
- hashes and keys tracked as nullable until generation succeeds
- no in-place mutation of completed artefact rows

### 3. Governance readiness projections
Implement or refine readiness projections.

Requirements:
- explicit `status` and `generation_status`
- current ready manifest/ledger pointers
- verification status fields
- readiness remains `PENDING` until real downstream artefacts exist
- later phases can advance readiness without schema changes
- no “looks ready” heuristic

### 4. Governance event stream
Implement or refine the append-only governance event stream.

Requirements:
- deterministic ordering
- system and user events represented explicitly
- regenerate, verification, failure, and cancellation transitions can later be appended without contract changes
- read surfaces do not reconstruct history from mutable projections

### 5. Ledger verification-run scaffolding
Implement or reconcile verification attempt lineage.

Requirements:
- append-only verification runs
- independent status and result lineage
- no need to infer history from a single mutable verification field
- admin-triggered re-verification can be added later without schema churn

### 6. Candidate snapshot contract scaffolding
Prepare the Phase 8 candidate-snapshot contract.

Requirements:
- canonical schema or typed internal contract exists
- pinned governance lineage fields are explicit
- source artefact kind disambiguates lineage
- supersession fields exist
- no registration workflow yet if the repo is not ready
- docs make clear this is a downstream contract, not a live Phase 8 workflow

### 7. Read APIs and typed contracts
Expose typed governance reads.

Requirements:
- overview, runs, run detail, status, and events endpoints are typed
- manifest and ledger status endpoints remain truthful
- browser consumers do not need to reverse-engineer lineage from raw rows
- no route-local fetch drift

### 8. Audit and docs
Use the canonical audit path and document the contracts.

Requirements:
- manifest/ledger/governance view events remain auditable
- docs explain artefact model ownership, readiness projections, and candidate lineage pinning
- later prompts 68–71 can build on these contracts without schema churn

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- governance artefact schemas
- readiness projections
- governance events
- verification-run scaffolding
- candidate-snapshot contract scaffolding
- typed read APIs
- tests

### Web
- governance overview and run-detail shells
- route/tab structure
- truthful unavailable/pending states

### Docs
- governance artefact model and readiness doc
- candidate snapshot and pinned-lineage contract doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small governance-shell/table/status refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- manifest bytes generation
- evidence-ledger content generation
- export request workflows
- candidate registration workflows
- a second artefact-lineage system

## Testing and validation
Before finishing:
1. Verify governance routes exist and fit the canonical shell.
2. Verify manifest and ledger tabs respect role visibility rules.
3. Verify artefact attempt rows are append-only and snapshot-pinned.
4. Verify readiness projections initialize truthfully and remain typed.
5. Verify governance event reads are append-only and ordered deterministically.
6. Verify verification-run lineage is scaffolded coherently.
7. Verify candidate-snapshot contracts pin governance lineage explicitly.
8. Verify docs match the implemented governance and candidate-lineage contracts.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- governance IA and route family are real
- artefact attempt models and readiness projections are real
- candidate-snapshot lineage contracts are prepared coherently
- later manifest, ledger, and export prompts can build without contract churn
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

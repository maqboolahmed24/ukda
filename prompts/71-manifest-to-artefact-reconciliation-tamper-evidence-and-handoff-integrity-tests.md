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
   - `/phases/phase-06-redaction-manifest-ledger-v1.md`
   - `/phases/phase-08-safe-outputs-export-gateway.md`
   - `/phases/phase-09-provenance-proof-bundles.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — manifest and ledger generation, readiness projections, candidate-snapshot scaffolding, provenance bundle scaffolding if any, CI gates, browser tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second integrity-test harness, a second lineage-reconciliation model, or duplicate candidate-handoff checks outside the canonical governance path.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for governance readiness, candidate-snapshot pinning, manifest/ledger lineage, tamper evidence, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that downstream export and provenance phases must consume pinned governance artefacts, not reconstruct mutable live state.

## Objective
Ship manifest-to-artefact reconciliation, tamper evidence, and handoff integrity tests.

This prompt owns:
- reconciliation checks between approved Phase 5 decisions, reviewed previews, manifests, ledgers, and governance projections
- tamper-evidence verification for manifest and ledger artefacts
- readiness-projection integrity checks under replacement attempts
- candidate-snapshot handoff integrity tests
- provenance-handoff contract tests for later Phase 9 consumers
- CI wiring and failure artefacts for governance integrity

This prompt does not own:
- new manifest or ledger generation features
- export request workflows
- provenance proof generation
- bundle generation
- a second test framework

## Phase alignment you must preserve
From Phase 6.1, 6.2, 6.3, Phase 8, and Phase 9:

### Existing manifest integrity expectations
- every manifest entry maps back to an audited Phase 5 decision
- manifest hash matches streamed bytes
- manifest excludes raw sensitive source text
- manifest bytes are stable for the same approved run

### Existing ledger integrity expectations
- ledger rows are append-only
- hash-chain verification succeeds for untampered chains
- verification history is readable from persisted `ledger_verification_runs`
- unauthorized ledger access is blocked

### Existing governance readiness expectations
- `governance_readiness_projections.status = READY` only when:
  - `manifest_id` points at a `SUCCEEDED` manifest row
  - `ledger_id` points at a `SUCCEEDED` ledger row
  - latest verification status is `VALID`
- replacement attempts preserve prior ready pointers until a new valid pair exists
- canceled or failed replacements do not collapse a previously valid ready pair

### Existing downstream handoff expectations
- Phase 8 candidate snapshots pin:
  - `governance_run_id`
  - `governance_manifest_id`
  - `governance_ledger_id`
  - hashes for both
- Phase 9 later consumes those pinned governance artefacts rather than following mutable live projections

## Implementation scope

### 1. Manifest-to-decision reconciliation harness
Implement a deterministic reconciliation check.

Requirements:
- every applied Phase 5 decision appears in the manifest exactly as required by the screening-safe rules
- no manifest entry is orphaned from the approved decision set
- line/page references remain coherent
- reconciler output is reviewable and precise
- no manual spreadsheet comparison is needed for engineering confidence

### 2. Ledger-to-decision reconciliation harness
Implement reconciliation for the evidence ledger.

Requirements:
- every relevant approved decision, override reason, actor, and timestamp has a corresponding ledger event or row where expected
- ledger rows remain append-only
- no decision history disappears between Phase 5 approval and Phase 6 evidence generation
- reconciliation report clearly identifies missing, duplicated, or mismatched entries

### 3. Tamper-evidence tests
Add artefact tamper-evidence coverage.

Requirements:
- ledger hash-chain verification fails on modified rows
- manifest hash validation fails on modified bytes
- result reporting is exact and test-friendly
- verification history remains append-only and auditable
- no false positive “valid” state when bytes or rows were changed

### 4. Readiness projection integrity tests
Test replacement and readiness edge cases.

Requirements:
- failed finalize jobs do not leave partial artefacts marked ready
- regenerate appends new attempts
- old ready pointers remain active until replacement artefacts are both successful and verified
- canceled replacement attempts do not collapse into `FAILED`
- status endpoints reflect both the active ready pair and replacement attempt state truthfully

### 5. Candidate-snapshot handoff integrity
Add downstream handoff checks for Phase 8 compatibility.

Requirements:
- candidate snapshot lineage pins exact governance artefacts and hashes
- later replacement of live governance projections does not rewrite prior candidate lineage
- canonical field `source_artifact_kind = REDACTION_RUN_OUTPUT` remains explicit and stable (identifier spelling is intentional)
- tests prove later candidate consumers can load governance lineage without inferring from mutable state

### 6. Provenance-handoff integrity
Prepare Phase 9 consumers without implementing proofs.

Requirements:
- governance artefact hashes and references are available in a form that later provenance proof builders can consume deterministically
- tests prove the pinned governance lineage is sufficient and stable
- no ad hoc backdoor dependence on mutable live routes or convenience queries

### 7. CI and artefact workflow
Wire these integrity checks into the existing quality-gate path.

Requirements:
- governance reconciliation and tamper tests run in CI
- failures produce useful artefacts or summaries
- commands are documented
- no second CI test stack is introduced

### 8. Documentation
Document:
- what reconciliation covers
- how tamper evidence is validated
- how candidate-snapshot and provenance handoff checks work
- what later phases may assume from these integrity guarantees

## Required deliverables
Create or refine the closest coherent equivalent of:

### Tests / CI / contracts
- manifest-to-decision reconciliation tests
- ledger-to-decision reconciliation tests
- tamper-evidence tests
- readiness projection integrity tests
- candidate-snapshot handoff checks
- provenance-handoff checks
- CI wiring

### Docs
- governance integrity and reconciliation doc
- downstream handoff integrity doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- test directories and CI/workflow files
- `/api/**` only if tiny deterministic status/read helpers are required
- `/packages/contracts/**` only if tiny typed integrity helpers help
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- new governance artefact generation features
- export workflows
- provenance proof generation
- bundle generation
- a second governance integrity framework

## Testing and validation
Before finishing:
1. Verify every manifest entry reconciles to an approved Phase 5 decision.
2. Verify ledger rows reconcile to the approved decision history.
3. Verify manifest hash validation and ledger hash-chain validation fail on tampered inputs.
4. Verify readiness projections remain truthful during regenerate, fail, and cancel scenarios.
5. Verify candidate snapshots pin exact governance artefact lineage.
6. Verify pinned governance lineage is sufficient for later provenance consumers.
7. Verify CI wiring produces useful governance-integrity failure artefacts.
8. Verify docs match the implemented reconciliation and handoff behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- manifest-to-artefact reconciliation is real
- tamper evidence is real and test-backed
- readiness-projection integrity is test-backed
- downstream handoff to candidate snapshots and provenance is verified
- CI can block governance-integrity regressions
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

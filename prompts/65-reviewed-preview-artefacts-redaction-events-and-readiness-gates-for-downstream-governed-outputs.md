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
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`
   - `/phases/phase-05-privacy-redaction-workflow-v1.md`
   - `/phases/phase-06-redaction-manifest-ledger-v1.md`
   - `/phases/phase-08-safe-outputs-export-gateway.md`
3. Then review the current repository generally — privacy run reviews, approved snapshot logic, per-page preview generation, run-level output manifests, governance-ready scaffolding if any, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second reviewed-output pipeline, a second run-output manifest model, or conflicting readiness rules for downstream governance/export phases.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. current repository state as the implementation reality to reconcile with
  2. this prompt
  3. the precise `/phases` files listed above
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for approved snapshot locking, preview/readiness rules, run-output manifest lineage, and downstream-governance handoff intent.
- Official docs win only for implementation mechanics.
- Preserve the rule that downstream governed outputs start from immutable reviewed Phase 5 artefacts, not from mutable live page state.

## Objective
Generate reviewed preview artefacts, redaction events, and readiness gates for downstream governed outputs.

This prompt owns:
- immutable approved-snapshot capture at run approval
- deterministic per-page reviewed preview regeneration from approved decisions
- immutable run-level safeguarded output manifest generation
- explicit run output status and readiness projection
- append-only reviewed-output eventing
- downstream-ready handoff contracts for Phase 6 governance and later export candidate registration
- controlled-only retrieval of reviewed preview artefacts and run-level output manifests

This prompt does not own:
- screening-safe manifest generation
- evidence-ledger generation
- export request workflows
- pseudonymisation or policy reruns
- public preview or download paths

## Phase alignment you must preserve
From Phase 5.0, 5.2, 5.3 and Phase 6/8 handoff rules:

### Existing approval and snapshot rules
- approving a privacy run persists:
  - `approved_snapshot_key`
  - `approved_snapshot_sha256`
  - `locked_at`
- once approved, findings, page reviews, and area-mask revisions are immutable
- any further reviewer changes require a new successor run

### Existing preview rules
- dual layers:
  - controlled transcript source
  - safeguarded preview text
- preview hash changes only when resolved decisions change
- `redaction_outputs.status = PENDING | READY | FAILED | CANCELED`

### Existing run-level output rules
Use or refine:
- `redaction_run_outputs`
  - `status`
  - `output_manifest_key`
  - `output_manifest_sha256`
  - `page_count`
  - timestamps and failure reason
- later Phase 6 and Phase 8 consumers must reference `redaction_run_outputs.output_manifest_key` or `output_manifest_sha256` for `source_artifact_kind = REDACTION_RUN_OUTPUT`
- they must not reconstruct a candidate ad hoc from mutable page-output state

### Downstream readiness rule
A reviewed run is downstream-ready only when:
- run review is `APPROVED`
- page preview projections are `READY`
- `redaction_run_outputs.status = READY`

This prompt must expose that readiness explicitly for later Phase 6 and Phase 8 consumers.

## Implementation scope

### 1. Immutable approved snapshot generation
Implement or harden the approved snapshot path.

Requirements:
- approval locks the run
- snapshot is deterministic over current finding decisions, area-mask revision refs, page-review projections, and run-level safeguarded output references
- snapshot is immutable and stored in controlled storage
- snapshot hash is persisted
- later consumers can load the snapshot without chasing mutable tables

### 2. Reviewed per-page preview regeneration
Implement or refine reviewed preview generation from the approved snapshot.

Requirements:
- per-page preview bytes regenerate from the locked approved decision set
- no mutable live-page state is consulted once the run is approved
- per-page `redaction_outputs` update truthfully
- canceled and failed preview generations remain explicit
- no raw original text is stored in preview artefacts
- controlled-only retrieval path remains intact

### 3. Run-level output manifest generation
Implement or refine the immutable run-level safeguarded output manifest.

Requirements:
- generated from the approved snapshot and reviewed page previews
- persisted to `redaction_run_outputs.output_manifest_key`
- `output_manifest_sha256` is deterministic
- page count and readiness are coherent
- no ad hoc reconstruction by later consumers is needed
- no mutation of prior successful run-output manifest rows

### 4. Explicit readiness gates
Expose explicit downstream-readiness truth.

Requirements:
- run readiness is not inferred only from page previews
- status/readiness contract clearly distinguishes:
  - approved but output pending
  - output generation running
  - output failed
  - output ready
- APIs are typed and suitable for later Phase 6 governance and Phase 8 candidate-registration prompts
- no “latest looks good” heuristic

### 5. Append-only reviewed-output events
Use or extend the canonical event path.

Requirements:
- reviewed-output generation start/success/fail/cancel are represented in append-only event history
- later governance and export surfaces can rely on this event stream
- no second event subsystem is created
- event ordering remains deterministic

### 6. Read APIs and retrieval
Implement or refine the canonical read surfaces.

At minimum ensure coherence for:
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/output`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/output/status`
- page preview/status endpoints for approved runs

Requirements:
- typed contracts
- controlled-only retrieval
- no raw storage-key leakage
- no export implication

### 7. Governance and export handoff contract
Prepare later phases without implementing them.

Requirements:
- the run-level output manifest is the only supported Phase 5 source artefact for downstream governance/export candidate registration
- Phase 6 and Phase 8 do not need to reconstruct from mutable page preview state
- docs and typed contracts make this explicit
- no premature export-candidate registration is required in this prompt

### 8. Audit and regression
Use the canonical audit path and add coverage.

At minimum cover:
- approved snapshot immutability
- deterministic preview and run-output manifest hashing
- readiness transitions
- canceled/failed preview/output generation truthfulness
- no leakage of raw original text
- downstream readers consume the run-level output manifest rather than mutable page state

### 9. Documentation
Document:
- approved snapshot semantics
- reviewed preview artefact generation
- run-level output manifest semantics
- readiness gates for downstream governance/export phases
- what Prompt 67–68 and later phases consume from this contract

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / workers / contracts
- approved snapshot generation
- reviewed page preview regeneration
- run-level output manifest generation
- readiness/status contracts
- append-only event coverage
- tests

### Web
- only small truthful readiness/output-status refinements if required for current privacy surfaces

### Docs
- reviewed preview artefact and output-manifest doc
- downstream governance/export handoff contract doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**` only if small readiness/status refinements are required
- `/packages/contracts/**`
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- screening-safe manifest generation
- evidence ledger generation
- export requests or release packs
- public preview delivery
- candidate registration
- a second reviewed-output pipeline

## Testing and validation
Before finishing:
1. Verify approved snapshot is deterministic and immutable.
2. Verify reviewed page previews regenerate only from the approved snapshot.
3. Verify run-level output manifest is deterministic and stored through the canonical path.
4. Verify readiness status is explicit and typed.
5. Verify canceled and failed generations remain truthful.
6. Verify no raw original text leaks into preview or run-level output artefacts.
7. Verify downstream contracts point Phase 6/8 to the run-level output manifest rather than mutable page state.
8. Verify docs match the implemented reviewed-output and readiness behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- reviewed preview artefacts are real
- run-level safeguarded output manifest is real
- downstream readiness gates are explicit and trustworthy
- later governance/export phases have a stable Phase 5 handoff contract
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

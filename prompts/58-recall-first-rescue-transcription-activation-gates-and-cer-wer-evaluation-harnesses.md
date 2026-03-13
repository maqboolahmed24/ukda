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
   - `/phases/phase-04-handwriting-transcription-v1.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — layout recall checks, rescue candidates, stable line/context artefacts, transcription runs, token-anchor gates, model assignments, tests, CI workflows, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second rescue-source model, a second activation-gate system, or a second evaluation harness outside the canonical test/eval path.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. current repository state as the implementation reality to reconcile with
  2. this prompt
  3. the precise `/phases` files listed above
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for recall-first rescue behavior, activation gates, token-anchor prerequisites, and production-confidence evaluation intent.
- Official docs win only for implementation mechanics.
- Preserve the rule that missed-text rescue is part of normal processing, not an afterthought, and that no promoted transcription basis may silently omit unresolved rescue work.

## Objective
Ship recall-first rescue transcription, activation gates, and CER/WER evaluation harnesses for production confidence.

This prompt owns:
- rescue transcription over `RESCUE_CANDIDATE` and `PAGE_WINDOW` sources
- rescue-source scheduling and persistence
- explicit activation gates tied to rescue completion and token-anchor readiness
- production-confidence evaluation harnesses for CER/WER
- rescue-vs-ordinary evaluation splits
- promoted-run gating based on evaluation and recall safety
- evaluation artefacts and docs for reviewer/engineer confidence

This prompt does not own:
- manual correction UI
- privacy or search features
- public benchmark sharing
- external evaluation services
- a second transcription schema outside the canonical run/result models

## Phase alignment you must preserve
From the normative patch and Phase 4:

### Recall-first rules
- suspicious faint, noisy, or irregular writing areas become rescue candidates
- rescue flow is part of normal processing
- every persisted token must still have stable source links and geometry
- no downstream activation may treat pages as complete when missed-text risk remains unresolved

### Existing source semantics
- `source_kind = LINE | RESCUE_CANDIDATE | PAGE_WINDOW`
- `source_ref_id` must remain stable and explicit
- line-based and rescue-based outputs may coexist in the same page/run

### Existing activation prerequisite
- a run cannot be activated unless token anchors are materialized for the promotable basis
- pages not yet safe for activation must block promotion explicitly

### Production-confidence intent
This prompt must add evaluation rigor:
- CER/WER on internal gold sets
- rescue-specific quality visibility
- deterministic evaluation artefacts
- no hidden “good enough” promotion

## Implementation scope

### 1. Canonical rescue transcription path
Implement or refine rescue transcription using the canonical transcription worker path.

Requirements:
- rescue candidates and page-window sources can be transcribed through the approved internal engine path
- rescue-derived outputs persist through the existing canonical result models
- `source_kind` and `source_ref_id` remain explicit
- line-backed and rescue-backed outputs remain distinguishable
- no silent remapping of rescue text onto ordinary line anchors

Where possible, reuse the primary transcription orchestration with explicit source selection rather than creating a second inference framework.

### 2. Rescue-source scheduling
Implement or refine rescue scheduling behavior.

Requirements:
- pages with `NEEDS_RESCUE` status can schedule rescue transcription targets deterministically
- rescue sources are processed only when they exist and are valid
- canceled or invalid rescue sources remain truthful and do not masquerade as completed
- per-page rescue completion state can be derived explicitly
- ordinary line transcription and rescue transcription do not stomp each other’s provenance

### 3. Activation gate hardening
Refine activation so promoted runs meet production-confidence expectations.

Requirements:
- activation fails when rescue-required pages still lack resolved rescue transcription output or explicit manual-review resolution
- activation fails when token anchors required by the promoted basis are missing
- activation blockers are typed, explicit, and UI-readable
- no hidden override path silently promotes an incomplete run
- pages marked `NEEDS_MANUAL_REVIEW` remain explicit and cannot be silently treated as complete

### 4. Rescue status and readiness reads
Expose the cleanest canonical read surfaces needed for reviewers and operators.

You may extend existing overview/run-detail/status endpoints or add the closest coherent equivalents of:
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/rescue-status`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/rescue-sources`

Requirements:
- typed contracts
- explicit ready / blocked / unresolved rescue states
- no need for UI code to guess readiness from raw rows alone
- no secret-bearing references or raw storage leakage

### 5. CER/WER evaluation harness
Implement a controlled evaluation harness.

Requirements:
- internal gold set only
- line-level and page-level CER/WER
- separate reporting for:
  - ordinary line transcription
  - rescue-source transcription
  - fallback-invoked samples where relevant
- deterministic evaluation artifacts
- clear mapping from evaluated outputs back to run/version metadata
- CI-friendly and reviewable

If the repo already has a generic evaluation harness, extend it rather than creating a second framework.

### 6. Evaluation artefacts and gating
Persist or publish evaluation artefacts in the repo’s cleanest controlled/test path.

Requirements:
- evaluation results are reproducible
- failures identify the run, fixture set, and slice that regressed
- production-confidence gates are documented and enforceable
- no public or external evaluation upload path
- do not overclaim with one giant blended score; keep CER/WER split and explainable

### 7. Web and operator integration
Refine only the minimum needed UI surfaces to make rescue and evaluation truth visible.

Requirements:
- overview or run-detail surfaces can show rescue completion and blocker summaries
- activation-block reasons surface calmly and exactly
- no fake “healthy” badge when rescue work is unresolved
- evaluation summaries may appear in run detail or operator docs if low churn and coherent
- no large evaluation dashboard is required in this prompt

### 8. Audit and regression
Use the canonical audit path where appropriate and add regression coverage.

At minimum cover:
- rescue-source scheduling
- rescue-source provenance
- activation blocked for unresolved rescue or missing token anchors
- CER/WER harness runs deterministically
- rescue and non-rescue slices are reported separately
- no-silent-drop behavior remains preserved

### 9. Documentation
Document:
- rescue transcription flow
- rescue completion and activation gate rules
- CER/WER harness scope and slices
- promotion requirements for production confidence
- how later prompts must preserve rescue provenance into privacy/search/export phases

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / workers / contracts
- rescue transcription path
- rescue-status/readiness contracts
- activation-gate hardening
- CER/WER evaluation harness
- tests

### Web
- only small truthful status/blocker refinements needed for overview or run detail

### Docs
- rescue transcription and activation-gate doc
- CER/WER and production-confidence evaluation doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**` only if small blocker/status refinements are required
- `/packages/contracts/**`
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- manual correction UI
- privacy/search/export features
- public benchmark publication
- a second rescue model
- a second evaluation framework

## Testing and validation
Before finishing:
1. Verify rescue transcription can run on `RESCUE_CANDIDATE` and `PAGE_WINDOW` sources.
2. Verify rescue-derived outputs preserve correct `source_kind` and `source_ref_id`.
3. Verify activation is blocked when rescue-required pages remain unresolved.
4. Verify activation is blocked when token anchors are missing for the promotable basis.
5. Verify CER/WER harness runs deterministically on the internal gold set.
6. Verify evaluation reports separate ordinary-line and rescue slices.
7. Verify no-silent-drop behavior remains intact.
8. Verify docs match the implemented rescue and evaluation behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- rescue transcription is real
- activation gates reflect rescue and anchor readiness truthfully
- CER/WER evaluation harness is real
- production-confidence promotion rules are explicit and enforceable
- rescue provenance remains stable for later phases
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

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
   - `/phases/phase-05-privacy-redaction-workflow-v1.md`
   - `/phases/phase-07-policy-engine-v1.md`
3. Then review the current repository generally — redaction runs, findings, area masks, decision events, page/run reviews, preview routes, projections, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second decision engine, a second preview layer model, or premature pseudonymisation/generalization behavior that belongs to Phase 7.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for mask-only baseline behavior, safeguarded preview rules, append-only decision events, and the explicit deferral of pseudonymisation to Phase 7.
- Official docs win only for implementation mechanics.
- Preserve the rule that Phase 5 baseline decisions are masking-only and that safeguarded preview is reviewable but not yet a release/export channel.

## Objective
Implement the Phase 5 baseline decision engine for masking and privacy-safe defaults; keep pseudonymisation deferred to Phase 7.

This prompt owns:
- the mask-only decision engine
- span-safe replacement behavior
- deterministic overlap resolution
- append-only decision-event persistence
- safeguarded preview generation
- dual-layer controlled vs safeguarded preview behavior
- workspace and triage integration for baseline masking
- preview hashes and readiness projection
- explicit deferral of pseudonymisation and generalization to later phases

This prompt does not own:
- pseudonymisation
- generalization
- dual-control review completion
- Phase 6 manifest/export behavior
- a second preview pipeline
- public or external preview delivery

## Phase alignment you must preserve
From Phase 5 Iteration 5.2:

### Decision engine rules
- apply span-safe replacements
- preserve punctuation and whitespace integrity
- resolve overlapping spans deterministically
- persist every decision as an append-only `redaction_decision_events` row
- treat `redaction_findings` as the current projection
- apply token-linked masks first when token refs exist
- apply conservative area masks when unreadable-but-sensitive handwriting is reviewer-confirmed
- area-mask edits never mutate geometry in place; every change appends a new `redaction_area_masks` revision and moves the finding’s active `area_mask_id` pointer

### Preview rules
- keep dual layers:
  - Controlled transcript source
  - safeguarded preview text
- recompute preview hash only when resolved decisions change
- persist `redaction_outputs.status = PENDING | READY | FAILED | CANCELED`
- never store raw original text inside preview artefacts or later release artefacts

### Web rules
- workspace mode switch:
  - `Controlled view`
  - `Safeguarded preview`
- triage breakdown:
  - auto-applied
  - needs review
  - overridden

### Required RBAC
- finding decision mutations are limited to `REVIEWER`, `PROJECT_LEAD`, and `ADMIN`
- `AUDITOR` may view decision and preview state but cannot mutate findings or area masks in Phase 5
- `RESEARCHER` does not perform Phase 5 decision mutations

### Required APIs
Use or refine:
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/findings`
- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/findings/{findingId}`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/preview-status`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/preview`

Lock enforcement rule:
- once run review is `APPROVED`, mutation writes are rejected and only read surfaces remain available

### Required tests
- deterministic overlap resolution
- safeguarded invariant: masked values cannot leak raw originals
- preview hash changes only when resolved decisions change
- token-linked findings and area-mask fallback both render correctly in preview and event history

### Deferral rule
- pseudonymisation and later generalization remain deferred to Phase 7
- do not add `PSEUDONYMIZE` or `GENERALIZE` as baseline decision actions here unless the repo already carries them as future-reserved enums that remain disabled and unused

## Implementation scope

### 1. Canonical mask-only decision engine
Implement or refine the baseline decision engine.

Requirements:
- masking only
- span-safe replacements
- punctuation and whitespace preservation
- deterministic overlap resolution
- uses canonical findings and token refs / area masks
- no second decision subsystem
- no pseudonymisation or generalization behavior enabled

### 2. Decision persistence and projection updates
Implement or refine append-only decision handling.

Requirements:
- finding changes append `redaction_decision_events`
- `redaction_findings` act as the current projection
- decision status changes are explicit and typed
- auto-applied vs needs-review vs overridden state remains truthful
- approved runs reject later decision mutations according to the canonical locking rules

### 3. Token-linked masks and conservative area masks
Apply masking from the canonical finding geometry.

Requirements:
- token-linked masks are used first when token refs exist
- conservative area masks are used when unreadable-but-sensitive handwriting is reviewer-confirmed
- no fake token masking for area-mask-only findings
- area-mask revision lineage remains append-only and auditable
- preview and event history both reflect which masking path was used

### 4. Safeguarded preview generation
Implement or refine preview generation.

Requirements:
- dual layers remain explicit:
  - controlled source transcript
  - safeguarded preview
- preview generation is deterministic
- preview hash updates only when resolved decisions change
- `redaction_outputs.status` moves through `PENDING -> READY | FAILED | CANCELED`
- preview bytes are retrievable only through the controlled authenticated preview endpoint
- no raw original text is stored inside preview artefacts

### 5. Preview retrieval and workspace integration
Refine the web integration for real baseline masking.

Requirements:
- workspace mode switch between Controlled view and Safeguarded preview
- toggling is exact and honest
- triage breakdown reflects auto-applied / needs review / overridden counts
- preview readiness is visible and truthful
- missing preview or failed preview states are calm and actionable
- no public or raw preview path is introduced

### 6. Review-state and lock semantics
Honor the Phase 5.0 review locking model.

Requirements:
- once a run review is `APPROVED`, later finding decisions, page-review updates, and area-mask revisions are rejected
- approved snapshot and lock behavior remain coherent
- preview generation after locked approval remains deterministic and traceable
- no hidden bypass mutation path exists

### 7. Audit and regression
Use the canonical audit path and add regression coverage.

At minimum cover:
- deterministic overlap resolution
- masked values do not leak raw originals
- preview hash changes only when resolved decisions change
- token-linked and area-mask-backed findings both render correctly in preview and event history
- approved runs reject later mutations
- no pseudonymisation/generalization path is accidentally enabled

### 8. Documentation
Document:
- mask-only baseline rules
- overlap resolution semantics
- preview generation and hash rules
- token-linked vs area-mask masking behavior
- explicit deferral of pseudonymisation/generalization to Phase 7
- what later prompts must preserve when adding review and governance layers

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / workers / contracts
- mask-only decision engine
- append-only decision-event handling
- deterministic preview generation
- preview status and retrieval behavior
- tests

### Web
- workspace controlled vs safeguarded preview mode
- triage breakdown refinements
- truthful preview readiness and error states

### Docs
- baseline masking engine and safeguarded preview doc
- Phase 7 deferral and scope-boundary doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small preview-mode or triage-breakdown refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- pseudonymisation
- generalization
- dual-control review completion
- export/release logic
- a second decision engine
- public preview delivery

## Testing and validation
Before finishing:
1. Verify masking decisions are applied with span-safe replacements.
2. Verify punctuation and whitespace integrity are preserved.
3. Verify overlap resolution is deterministic.
4. Verify masked values cannot leak raw originals into safeguarded preview artefacts.
5. Verify preview hash changes only when resolved decisions change.
6. Verify token-linked and area-mask-backed findings both render correctly in preview and event history.
7. Verify approved runs reject later decision and area-mask mutations.
8. Verify no pseudonymisation/generalization path is enabled.
9. Verify docs match the implemented baseline masking and preview behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the baseline mask-only decision engine processes queued decisions and persists typed decision outcomes with timestamps
- safeguarded preview generation is real
- append-only decision and area-mask lineage is preserved
- workspace and triage surfaces consume the real preview path
- pseudonymisation remains deferred to Phase 7
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

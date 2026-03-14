You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed phase files before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first on each run.

## Mandatory first actions
1. Inspect the full repository tree.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/phase-03-layout-segmentation-overlays-v1.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`
   - `/phases/phase-04-handwriting-transcription-v1.md` for downstream rescue/transcription handoff expectations
   - `/phases/phase-05-privacy-redaction-workflow-v1.md` only for conservative geometry-fallback awareness, not for implementing privacy workflows
3. Then review the current repository generally — layout runs, page layout results, line artifacts, PAGE-XML/overlay outputs, layout workspace routes, typed contracts, audit code, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second recall-status model, a second rescue-candidate path, or conflicting activation gates.

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
- `/phases` wins for recall-first behavior, no-silent-drop gating, rescue-candidate semantics, downstream activation blocking, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the normative patch: `find text -> check for missed text -> rescue missed text -> anchor every word/token -> then permit search/redaction`.

## Objective
Implement recall-first missed-text checks and rescue-candidate generation before any downstream activation.

This prompt owns:
- the second-stage missed-text recall check after layout generation
- page-level recall status resolution
- rescue-candidate generation
- rescue-candidate and recall-status APIs
- triage/workspace surfacing of recall-risk and rescue information
- recall-status prerequisites that block activation until every page has explicit recall-status resolution
- gold-set recall and rescue regression coverage
- explicit downstream handoff preparation for Phase 4 rescue transcription

This prompt does not own:
- actual rescue transcription
- token anchor materialization
- privacy redaction decisions
- search indexing
- manual correction tooling
- transcription workspace implementation
- full layout activation-gate evaluator and downstream invalidation orchestration (owned by Prompt 48)

## Phase alignment you must preserve
From the normative patch and Phase 3 Iteration 3.1:

### Normative recall-first rules
- Layout output is not complete by itself.
- Every page must run a second-stage missed-text check after layout generation.
- Suspicious faint, noisy, or irregular writing areas become `rescue candidates`.
- Rescue flow is part of normal processing, not only manual exception handling.
- No page may silently drop potential handwriting content.

### Required explicit completion classes
Every page must resolve to one explicit class:
- `COMPLETE`
- `NEEDS_RESCUE`
- `NEEDS_MANUAL_REVIEW`

No downstream activation may treat a page as fully complete when it still indicates missing-text risk.

### Required data model usage
Use or reconcile the canonical Phase 3 models:
- `page_layout_results.page_recall_status`
- `layout_recall_checks`
- `layout_rescue_candidates`

Where already defined:
- `layout_recall_checks`
  - `run_id`
  - `page_id`
  - `recall_check_version`
  - `missed_text_risk_score`
  - `signals_json`
  - `created_at`
- `layout_rescue_candidates`
  - `id`
  - `run_id`
  - `page_id`
  - `candidate_kind` (`LINE_EXPANSION | PAGE_WINDOW`)
  - `geometry_json`
  - `confidence`
  - `source_signal`
  - `status` (`PENDING | ACCEPTED | REJECTED | RESOLVED`)
  - `created_at`
  - `updated_at`

### Required APIs
Implement or refine:
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/recall-status`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/rescue-candidates`

### Required gating rule
- no run activation can bypass unresolved recall status
- a layout run cannot be promoted if any page lacks explicit recall-status resolution

### Required regression expectations
- missed-text recall check metrics are mandatory and versioned
- regression tests fail when recall drops below the pinned floor for the handwritten gold set
- rescue-candidate quality is tracked

## Implementation scope

### 1. Canonical missed-text recall check
Implement the second-stage recall check after layout generation.

Requirements:
- runs after the structural segmentation stage
- evaluates risk of missed handwriting or missed text
- produces a versioned recall-check result
- computes `missed_text_risk_score`
- persists typed `signals_json`
- does not silently downgrade suspicious pages to `COMPLETE`
- remains deterministic and reviewable enough for regression testing

Use the strongest heuristic already compatible with the current repo, or a model-backed internal approach that fits the secure no-egress posture.
Do not call external services.

### 2. Explicit page recall-status resolution
Implement or refine explicit `page_recall_status` assignment.

Requirements:
- every page resolves to one of:
  - `COMPLETE`
  - `NEEDS_RESCUE`
  - `NEEDS_MANUAL_REVIEW`
- assignment is based on actual recall-check output
- no hidden “looks okay” fallback
- page results remain queryable and auditable
- later work can consume the status without reverse-engineering it from warnings

### 3. Rescue-candidate generation
Implement or refine rescue-candidate generation.

Requirements:
- suspicious faint, noisy, or irregular areas can create rescue candidates
- candidate kinds supported:
  - `LINE_EXPANSION`
  - `PAGE_WINDOW`
- candidate geometry is explicit and valid
- candidate confidence and `source_signal` are persisted
- candidate status starts explicitly and can be updated later by downstream flows
- no speculative downstream transcription is attempted here

### 4. Recall-status activation prerequisites
Implement the recall-status prerequisites consumed by the canonical layout activation gate.

Requirements:
- no layout run may be activated while any page lacks resolved recall status
- no layout run may be activated while unresolved recall work still implies missed-text risk without an explicit resolution class
- activation failure paths are exact and actionable
- prerequisite outputs are typed and compatible with downstream projection logic
- no hidden override path bypasses recall gating

### 5. Triage and workspace surfacing
Refine the layout triage and workspace surfaces to expose recall truth.

Requirements:
- page triage can show recall status and rescue indicators
- workspace inspector can show recall risk summary
- rescue candidates can be listed or previewed in a calm, dense way
- clear empty/no-candidate state when none exist
- no noisy “AI detection” theatrics
- no route pretends rescue has already happened

### 6. Rescue-candidate API behavior
Implement or refine the canonical read surfaces.

Requirements:
- `recall-status` endpoint is typed and explicit
- `rescue-candidates` endpoint is typed and explicit
- RBAC remains aligned with layout artefact readers
- geometry is browser-safe and internal-only
- no raw storage leakage
- no second API family for the same data

### 7. Gold-set and recall-floor regression
Add meaningful regression gates.

At minimum cover:
- recall check versioning
- pinned recall-floor expectations on the handwritten gold set
- rescue-candidate quality expectations on curated fixtures
- no-silent-drop activation gate
- deterministic behavior under the same fixture/params/runtime
- failure artefacts useful enough for an engineer to review

Keep the suite stable and reviewable.

### 8. Audit alignment
Use the existing canonical audit path.

At minimum emit or reconcile the cleanest existing event coverage for:
- recall-status reads
- rescue-candidate reads
- activation failures caused by unresolved recall status

If the current repo needs small new event names for these exact surfaces, add them carefully through the canonical audit system. Do not create a second audit path.

### 9. Downstream handoff preparation
Prepare Phase 4 without implementing it.

Requirements:
- rescue candidates are persisted in a form that Phase 4 can consume as:
  - `source_kind = RESCUE_CANDIDATE` or `PAGE_WINDOW`
  - stable source references
  - explicit geometry
- line-based pages remain available for ordinary transcription
- pages marked `NEEDS_MANUAL_REVIEW` remain explicit and do not masquerade as rescued
- nothing in this prompt claims token anchors already exist

### 10. Documentation
Document:
- recall-first rules
- recall-status semantics
- rescue-candidate generation rules
- activation blocking rules
- how Phase 4 will consume rescue candidates
- what later work should handle for token anchors, conservative masks, and downstream search/redaction safety

## Required deliverables

### Backend / workers / contracts
- missed-text recall-check implementation
- recall-check persistence
- rescue-candidate generation
- recall-status and rescue-candidate APIs
- activation gate hardening
- tests and gold-set recall-floor coverage

### Web
- triage/workspace recall-status and rescue-candidate surfacing
- activation-block feedback where useful
- accurate empty/loading/error/not-ready states

### Docs
- recall-first and rescue-candidate contract doc
- layout activation gating and downstream handoff doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small triage/workspace recall-status presentation refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- rescue transcription
- token anchors
- privacy redaction decisions
- search indexing
- manual correction tooling
- a second recall model
- any public or external service calls

## Testing and validation
Before finishing:
1. Verify every page resolves to `COMPLETE`, `NEEDS_RESCUE`, or `NEEDS_MANUAL_REVIEW`.
2. Verify missed-text recall checks are versioned and persisted.
3. Verify rescue candidates are generated with valid geometry and stable source metadata.
4. Verify the recall-status and rescue-candidates APIs are typed and RBAC-protected.
5. Verify no run activation can bypass unresolved recall status.
6. Verify the handwritten gold-set recall floor is enforced and regression failures are meaningful.
7. Verify triage/workspace surfaces show recall status accurately.
8. Verify downstream handoff data is ready for Phase 4 rescue transcription without claiming tokens already exist.
9. Verify docs match the implemented recall-first behavior and activation gates.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- recall-first missed-text checks are real
- page recall status is explicit on every page
- rescue candidates are real
- activation cannot bypass unresolved recall
- triage/workspace surfaces display page recall status, blocker reason codes, and unresolved counts from typed APIs
- rescue-candidate handoff payload fields and enums are versioned and documented for downstream consumers
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

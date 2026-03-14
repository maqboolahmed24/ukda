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
   - `/phases/phase-04-handwriting-transcription-v1.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` so rescue-related fallback handling stays accurate
3. Then review the current repository generally — primary transcription pipeline, approved model catalog and role map, jobs/workers, result schemas, compare route shells if any, typed contracts, audit code, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second fallback framework, a second comparison schema, or silent merge/promotion behavior.

## Source-of-truth hierarchy
Use this precedence order when implementing:
1. The specific `/phases` files listed in this prompt for product behavior and acceptance logic.
2. `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md` when this prompt depends on web-first execution semantics.
3. `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` when this prompt depends on recall-first, rescue, token-anchor, search-anchoring, or conservative-masking semantics.
4. `/phases/blueprint-ukdataextraction.md`, `/phases/README.md`, `/phases/ui-premium-dark-blueprint-obsidian-folio.md`, and `/phases/phase-00-foundation-release.md` as supporting product context when they are listed or clearly relevant.
5. This prompt for task scope and deliverables.
6. Current repository state for reconciling implementation details.
7. Official external docs for implementation mechanics only.

Treat current repository state as implementation context, not as the primary source of product truth.

## Conflict-resolution rule
- `/phases` wins for fallback invocation rules, immutable primary-output preservation, compare semantics, stable role-map use, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that fallback and comparison are governed recovery paths, not silent replacements for the primary VLM output.

## Objective
Add a governed fallback transcription path and multi-engine comparison hooks for recovery and validation.

This prompt owns:
- the fallback-engine invocation rules
- plugin-style engine interface for governed fallback engines
- immutable preservation of primary VLM output even when fallback runs
- comparison API and comparison-decision persistence
- comparison route shell and workspace compare mode scaffolding
- audit coverage for compare reads and decisions
- gating so new fallback engines cannot be promoted silently

This prompt does not own:
- token-anchor materialization
- manual correction workspace
- automatic merge or silent promotion
- public or external model services
- arbitrary project-local engine registration

## Phase alignment you must preserve
From Phase 4 Iteration 4.5:

### Fallback invocation rules
- invoke `KRAKEN_LINE` when structured-response validation fails, anchors cannot be resolved, or the configured confidence threshold is missed
- preserve the original VLM output as immutable source data even when fallback is invoked

### Plug-in engine interface
Support:
- `KRAKEN_LINE`
- optional `TROCR_LINE`
- optional `DAN_PAGE`

Rules:
- `TROCR_LINE` and `DAN_PAGE` remain disabled until they are approved in the catalog, mapped through the stable `TRANSCRIPTION_FALLBACK` role, and assigned through the same governance path
- outputs must be normalised into the existing transcription run/result schema
- no ad hoc engine-specific schema fork

### Fallback run lifecycle APIs
Implement or refine:
- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/fallback`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/status`
- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/cancel`

Rules:
- fallback run lifecycle remains on the canonical transcription-runs family
- status transitions are typed and auditable

### Comparison API
Implement or refine:
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`
  - returns line-level or token-level diffs, changed-confidence summaries, and engine metadata
- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/compare/decisions`
  - records explicit keep-or-promote decisions in `transcription_compare_decisions`
  - does not mutate original source runs

### Compare UI
- compare route:
  - `/projects/:projectId/documents/:documentId/transcription/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}&page={pageNumber}&lineId={lineId}&tokenId={tokenId}`
- workspace compare mode:
  - run A vs run B or engine A vs engine B
  - explicit user acceptance per line, token, or region
- no automatic merge or silent promotion

### Audit events
- `TRANSCRIPTION_FALLBACK_RUN_CREATED`
- `TRANSCRIPTION_FALLBACK_RUN_CANCELED`
- `TRANSCRIPTION_FALLBACK_RUN_STATUS_VIEWED`
- `TRANSCRIPTION_RUN_COMPARE_VIEWED`
- `TRANSCRIPTION_COMPARE_DECISION_RECORDED`

### Required RBAC
- `PROJECT_LEAD`, `REVIEWER`, `RESEARCHER`, and `ADMIN` can view fallback runs, compare reads, and compare status surfaces
- only `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can create/cancel fallback candidate runs or record compare keep-or-promote decisions

## Implementation scope

### 1. Canonical fallback engine interface
Implement or refine the governed fallback interface.

Requirements:
- fallback engine adapters conform to one canonical interface
- `KRAKEN_LINE` is the first concrete fallback path
- optional engine families can be registered but remain disabled until approved and assigned
- no route-local engine branching
- no second result schema per engine family

### 2. Fallback invocation and immutability rules
Implement fallback invocation safely.

Requirements:
- fallback can be triggered on:
  - structured-response validation failure
  - anchor resolution failure
  - confidence below threshold
- original VLM output remains immutable and preserved
- fallback outputs are persisted as part of a new or governed candidate run path consistent with the repository model
- the system never silently overwrites the primary VLM result with fallback text
- invocation reasons are explicit and queryable

### 3. Result normalization
Normalize fallback output into the canonical run/result schema.

Requirements:
- use the existing `transcription_runs`, `page_transcription_results`, `line_transcription_results`, and related result models
- populate engine metadata clearly
- when hOCR is emitted by fallback engines, store it only through the governed storage path
- no engine-specific result drift across routes or APIs

### 4. Comparison API and decision persistence
Implement the comparison path.

Requirements:
- `GET .../transcription-runs/compare` returns:
  - line-level or token-level diffs
  - changed-confidence summaries
  - engine metadata
  - output availability status
- `POST .../transcription-runs/compare/decisions` persists explicit keep-or-promote decisions
- decisions are append-only and auditable
- decisions do not mutate the original source runs directly
- no hidden merge behavior

### 5. Compare route shell and minimal web integration
Implement or refine the compare route shell.

Requirements:
- deep-link-safe compare route exists
- base/candidate run context is explicit
- line-level or token-level diff shells are present
- safe empty/not-ready/error states
- explicit decision affordances only for `PROJECT_LEAD`, `REVIEWER`, and `ADMIN`
- no giant polished compare workspace yet if the repo is not ready; keep it minimal and explicit

### 6. Role-map and governance alignment
Use the approved model catalog and stable role map from the repo.

Requirements:
- fallback engines are selected only through approved model assignments and role contracts
- a new engine path cannot become active without passing the same governance checks
- role-map changes do not alter route or run-table semantics
- no hardcoded ad hoc engine picks in the UI

### 7. Audit and safety gates
Use the canonical audit path.

Requirements:
- compare views and compare decisions are auditable
- logs remain privacy-safe
- no public or external service path is introduced
- outputs from new engine paths require explicit user confirmation before promotion

### 8. Documentation
Document:
- fallback invocation rules
- immutable preservation of primary VLM output
- comparison API and decision semantics
- how new fallback engines must enter through the approved model catalog and stable role map
- what later work owns for broader compare UX and correction flows

## Required deliverables
### Backend / workers / contracts
- fallback engine interface
- Kraken fallback path
- comparison API
- compare-decision persistence
- tests

### Web
- compare route shell
- explicit decision affordances for `PROJECT_LEAD`, `REVIEWER`, and `ADMIN`
- accurate compare-state handling

### Docs
- fallback and compare-governance doc
- compare decision contract doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small compare-shell refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- silent merge or promotion
- token-anchor materialization
- full correction workspace
- public or external model calls
- arbitrary engine registration outside the approved model catalog
- a second comparison system

## Testing and validation
Before finishing:
1. Verify fallback run create/status/cancel lifecycle APIs are real, typed, and coherent.
2. Verify fallback can be invoked on schema failure, anchor failure, or confidence below threshold.
3. Verify the original VLM output remains immutable when fallback runs.
4. Verify fallback outputs normalize into the canonical run/result schema.
5. Verify comparison diffs are returned for base and candidate runs.
6. Verify compare decisions persist append-only and do not mutate source runs.
7. Verify only approved, assigned fallback engines can be used.
8. Verify fallback run create/cancel actions are limited to `PROJECT_LEAD`, `REVIEWER`, and `ADMIN`, with `RESEARCHER` read-only.
9. Verify compare decision actions are limited to `PROJECT_LEAD`, `REVIEWER`, and `ADMIN`, with `RESEARCHER` read-only.
10. Verify fallback lifecycle and compare events are audited.
11. Verify docs match the implemented fallback and compare behavior.
12. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- fallback transcription runs can be created, executed, and finalized with typed status transitions
- original primary output remains immutable
- comparison hooks return typed primary-vs-fallback deltas, and promotion/reject decisions are persisted with actor/timestamp provenance
- no silent merge or promotion exists
- fallback stays inside the approved internal model-governance path
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

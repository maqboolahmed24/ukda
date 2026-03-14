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
   - `/phases/phase-10-granular-data-products.md`
3. Then review the current repository generally — active entity index projection, entity index schemas, transcription/workspace deep links, shared UI/data-layer primitives, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second entity product, a second occurrence model, or conflicting occurrence-to-source navigation semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for controlled entity index semantics, occurrence provenance, activation gates, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that the entity index is a governed internal data product, not an ad hoc search side effect, and that every occurrence remains traceable back to transcript context.

## Objective
Build the controlled entity index as a governed internal data product with explicit lineage.

This prompt owns:
- entity extraction pipeline into the versioned entity index
- canonical `controlled_entities` and `entity_occurrences`
- occurrence provenance completeness and canonicalization validation
- activation gates for entity index generations
- entity list/detail/occurrence APIs and routes
- deep-link-safe occurrence navigation back into the transcription workspace
- confidence summaries and entity detail presentation
- audit and regression coverage for entity lineage

This prompt does not own:
- search UI
- derivative indexes
- broad knowledge graph features
- external entity services
- a second entity store

## Phase alignment you must preserve
From Phase 10 Iteration 10.2:

### Required tables
Implement or reconcile:
- `controlled_entities`
  - `id`
  - `project_id`
  - `entity_index_id`
  - `entity_type`
  - `display_value`
  - `canonical_value`
  - `confidence_summary_json`
  - `created_at`
- `entity_occurrences`
  - `id`
  - `entity_index_id`
  - `entity_id`
  - `document_id`
  - `run_id`
  - `page_id`
  - `line_id`
  - `token_id`
  - `source_kind`
  - `source_ref_id`
  - `page_number`
  - `confidence`
  - `occurrence_span_json`
  - `occurrence_span_basis_kind` (`LINE_TEXT | PAGE_WINDOW_TEXT | NONE`)
  - `occurrence_span_basis_ref`
  - `token_geometry_json`
  - `created_at`

### Required APIs
- `GET /projects/{projectId}/entities?q={q}&entityType={entityType}&cursor={cursor}&limit={limit}`
- `GET /projects/{projectId}/entities/{entityId}`
- `GET /projects/{projectId}/entities/{entityId}/occurrences?cursor={cursor}&limit={limit}`
- `POST /projects/{projectId}/entity-indexes/{indexId}/activate`

Rules:
- reads only from `project_index_projections.active_entity_index_id`
- reject when no active entity index exists
- response payloads include `entity_index_id`
- list, detail, and occurrence reads must all remain within the same active entity index generation
- occurrence links preserve token and source provenance when available
- `occurrence_span_json` is interpreted only through persisted basis fields, not guessed client-side

### Activation rule
- `POST /projects/{projectId}/entity-indexes/{indexId}/activate` is rejected unless the candidate index passes:
  - occurrence-provenance completeness
  - canonicalization validation
  - eligible-input coverage gates

### RBAC
- `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, and `ADMIN` can read entity lists, detail, and occurrence views for projects they can access
- `AUDITOR` does not use the project-scoped entity workspace

### Web routes
- `/projects/:projectId/entities`
- `/projects/:projectId/entities/:entityId`

## Implementation scope

### 1. Canonical entity extraction pipeline
Implement or refine the entity indexing pipeline.

Requirements:
- entity extraction generates versioned `controlled_entities` and `entity_occurrences`
- no hidden side-effect indexing
- extraction is tied to `entity_index_id`
- outputs remain deterministic enough for rebuild comparisons
- no second entity schema is introduced

### 2. Canonicalization and occurrence provenance
Implement the entity quality gates.

Requirements:
- canonicalization of entity values is explicit and typed
- confidence summaries are computed coherently
- every occurrence has provenance back to page/line/token/source context
- activation is blocked if occurrence provenance or canonicalization validation fails
- no mixed-generation rows appear in reads

### 3. Entity list and detail APIs
Implement or refine the core entity read surfaces.

Requirements:
- server-side search/filter by query and entity type
- cursor pagination
- typed payloads
- entity detail remains within the same active `entity_index_id`
- no broad “all generations” mixing

### 4. Occurrence navigation
Make occurrences actionable.

Requirements:
- occurrence detail includes enough provenance to reopen the correct transcription workspace context
- token and source provenance are preserved when available
- page-window spans use `occurrence_span_basis_kind` and `occurrence_span_basis_ref` coherently
- no ambiguous line-only fallback where richer provenance exists

### 5. Entity workspace web surfaces
Implement or refine the entity list and detail UI.

Requirements:
- entity search/filter list
- detail panel or page with confidence summary and occurrence list
- calm, dense internal-tool design
- empty/loading/error/no-active-index states remain honest
- opening an occurrence jumps to the correct transcript context

### 6. Audit and regression
Use the canonical audit path and add coverage.

At minimum cover:
- occurrence links match transcript segments
- list/detail/occurrence reads resolve through the same active `entity_index_id`
- activation blocks on provenance or canonicalization failures
- occurrence navigation preserves token/source context
- read events:
  - `ENTITY_LIST_VIEWED`
  - `ENTITY_DETAIL_VIEWED`
  - `ENTITY_OCCURRENCES_VIEWED`
  - index lifecycle events from the index management layer

### 7. Documentation
Document:
- entity index model and lineage
- occurrence provenance semantics
- canonicalization and activation gates
- what Prompt 92 will build next for safeguarded derivative indexes

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / workers / contracts
- entity extraction/index population
- canonicalization validation
- entity list/detail/occurrence APIs
- activation gates
- tests

### Web
- entity list route
- entity detail route
- occurrence navigation into transcription context

### Docs
- controlled entity index and lineage doc
- occurrence provenance and navigation doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small entity-list/detail refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- search UI
- derivative indexes
- knowledge graph expansion
- public entity APIs
- a second entity product

## Testing and validation
Before finishing:
1. Verify entity extraction populates `controlled_entities` and `entity_occurrences` under one `entity_index_id`.
2. Verify occurrence provenance is complete and usable.
3. Verify activation fails when canonicalization or occurrence provenance completeness gates fail.
4. Verify list, detail, and occurrence reads all stay within the active `entity_index_id`.
5. Verify occurrence links reopen the correct transcription context.
6. Verify docs match the implemented entity-index and provenance behavior.
7. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the controlled entity index is real
- occurrence provenance is real
- activation gates are real
- entity discovery routes are real
- the repo is ready for safeguarded derivative and downstream data-product work
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

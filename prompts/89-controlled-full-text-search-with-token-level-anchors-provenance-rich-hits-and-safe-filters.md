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
   - `/phases/phase-10-granular-data-products.md`
3. Then review the current repository generally — search index schemas, token anchors, transcription workspace routes, active search index projection, typed contracts, shared UI/data layer, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second search backend, a second hit payload shape, or conflicting deep-link semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for token-anchor-first search provenance, fallback hit semantics, RBAC, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the recall-first patch: token-level anchors are required when available, and non-token hits must carry exact fallback provenance instead of approximate line-only guesses.

## Objective
Implement controlled full-text search with token-level anchors, provenance-rich hits, and safe filters.

This prompt owns:
- the canonical search query API
- active-search-index-only serving
- search document population and hit payload shape
- token-anchored and rescue/page-window provenance
- exact fallback match-span behavior when token anchors are unavailable
- ACL-safe search access
- deep-link handoff to the transcription workspace

This prompt does not own:
- search UI polish
- query auditing and admin quality surfaces
- entity indexing
- derivative indexes
- a second search backend

## Phase alignment you must preserve
From Phase 10 Iteration 10.1 and the normative patch:

### Required search API
- `GET /projects/{projectId}/search`
  - query params:
    - `q`
    - optional `documentId`
    - optional `runId`
    - optional `pageNumber`
    - optional `cursor` (absent cursor means first page)
    - `limit`

Rules:
- read only from `project_index_projections.active_search_index_id`
- reject when no active search index exists
- response includes the active `search_index_id`
- hit payload includes:
  - `documentId`
  - `runId`
  - `pageNumber`
  - `lineId` when available
  - `token_id` and geometry when available
  - `source_kind`
  - `source_ref_id`
  - `match_span_json` fallback when token provenance is unavailable
- exact fallback match spans are used for non-token hits
- search results must never mix rows across search-index generations

### Required table usage
Use or reconcile `search_documents`:
- `search_index_id`
- `document_id`
- `run_id`
- `page_id`
- `line_id`
- `token_id`
- `source_kind` (`LINE | RESCUE_CANDIDATE | PAGE_WINDOW`)
- `source_ref_id`
- `page_number`
- `match_span_json`
- `token_geometry_json`
- `search_text`
- `search_metadata_json`

### Required deep link
Open result jumps to:
- `/projects/:projectId/documents/:documentId/transcription/workspace?page={pageNumber}&runId={runId}[&lineId={lineId}][&tokenId={tokenId}][&sourceKind={sourceKind}][&sourceRefId={sourceRefId}]`
- API-to-route identifier mapping is deterministic and lossless for available fields only: `token_id -> tokenId`, `source_kind -> sourceKind`, `source_ref_id -> sourceRefId`, `line_id -> lineId`, `documentId -> :documentId`

### RBAC
- `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, and `ADMIN` can search controlled transcripts for projects they can already access
- `AUDITOR` does not use the interactive project search surface

## Implementation scope

### 1. Canonical search query API
Implement or refine the project search API.

Requirements:
- typed query params
- typed cursor pagination
- safe defaults and bounded limits
- exact active-search-index enforcement
- no “latest successful” fallback
- no cross-project result leakage

### 2. Search hit payload contract
Implement the canonical search hit schema.

Requirements:
- token-level provenance when available
- rescue/page-window source provenance when available
- exact fallback `match_span_json` when token anchors are unavailable
- geometry included when available
- no approximate or guessed hit context
- no second hit payload shape in different routes

### 3. Search index document population
Refine or implement search document ingestion for active index generations.

Requirements:
- rows are versioned under `search_index_id`
- rebuilds and rollbacks do not mix generations
- search documents preserve provenance back to page/line/token/source
- no hidden search-text generation outside the index pipeline

### 4. Deep-link workspace handoff
Implement or refine result opening semantics.

Requirements:
- token-anchored hits deep-link to exact token highlight
- rescue/page-window hits deep-link to exact source context
- non-token hits use exact `match_span_json` fallback
- deep links include only provenance fields present in the hit payload; missing token/line provenance is never fabricated into route params
- route payload is coherent and reload-safe
- no hidden client-only mapping layer

### 5. Access control and safety
Harden search access.

Requirements:
- project RBAC enforced server-side
- unauthorized search requests fail closed
- no broad admin override route unless the current repo already uses one safely
- no raw transcript payload leakage in logs or error messages

### 6. Audit and regression
Use the canonical audit path where present and add coverage.

At minimum cover:
- correct active `search_index_id` resolution
- unauthorized access blocked
- token-anchored hits resolve correctly
- rescue/page-window hits resolve correctly
- non-token fallback highlighting uses exact stored spans
- opening a search hit emits `SEARCH_RESULT_OPENED`

### 7. Documentation
Document:
- search API contract
- hit payload semantics
- token-anchor vs fallback behavior
- deep-link handoff rules
- what Prompt 90 will polish in the search UX

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- search query API
- typed hit payloads
- search document population/refinement
- tests

### Web
- only minimal result-open integration needed to prove workspace handoff is coherent

### Docs
- controlled full-text search API doc
- token-anchor and fallback hit contract doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**` if search document build helpers are required
- `/web/**` only if minimal result-open integration is needed
- `/packages/contracts/**`
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- polished search UI
- query audit/admin quality surfaces
- entity index
- derivative index
- a second search backend

## Testing and validation
Before finishing:
1. Verify search rejects when no active search index exists.
2. Verify results come only from the active `search_index_id`.
3. Verify token-anchored hits return exact token and geometry payloads when available.
4. Verify rescue/page-window hits preserve exact source provenance.
5. Verify non-token hits use exact `match_span_json` fallback highlighting.
6. Verify search without a cursor returns the deterministic first result page for the query/filter set.
7. Verify deep-link generation omits unavailable optional provenance params (`lineId`, `tokenId`, `sourceKind`, `sourceRefId`) and still opens the correct workspace context.
8. Verify RBAC blocks unauthorized search access.
9. Verify docs match the implemented search API and hit semantics.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- controlled full-text search is real
- token-anchored and provenance-rich hits are real
- fallback hit behavior is exact and safe
- active-search-index semantics are real
- the repo is ready for a polished search UX without contract churn
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

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
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`
   - `/phases/phase-10-granular-data-products.md`
3. Then review the current repository generally — search route/API, result-open deep links, workspace highlight behavior, shared UI primitives, browser tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second search UI, a second result-card system, or conflicting highlight/jump-to-context behavior.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for search route ownership, jump-to-context semantics, token-level highlight expectations, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the search surface as a calm, exact, internal discovery workspace — not a consumer search site, not an AI chat box, and not a dashboard.

## Objective
Make search feel instant and exact with zero-state, query UX, result cards, jump-to-context, and precise highlighting.

This prompt owns:
- the `/projects/:projectId/search` web UX
- zero-state, empty-state, loading, and no-results behavior
- query and filter ergonomics
- result cards and grouped-result presentation
- precise jump-to-context transitions into the transcription workspace
- result-highlight and preview snippet rendering using token or fallback span provenance
- keyboard-safe search interaction
- visual and accessibility baselines for the search surface

This prompt does not own:
- search backend logic
- query audits
- entity or derivative products
- a second search route or omnibox
- fuzzy/semantic ranking beyond the canonical backend response order

## Phase alignment you must preserve
From Phase 10 Iteration 10.1 and the recall-first patch:

### Required route
- `/projects/:projectId/search`

### Existing backend contract
Search UI must consume:
- `GET /projects/{projectId}/search`
- query params:
  - `q`
  - optional `documentId`
  - optional `runId`
  - optional `pageNumber`
  - optional `cursor` (absent cursor means first page)
  - `limit`
- active `search_index_id` included in response
- hit payload includes token, source, geometry, and/or exact span fallback information

### Required jump behavior
- open result jumps to transcription workspace with:
  - required `page`
  - required `runId`
  - optional `lineId`
  - optional `tokenId`
  - optional `sourceKind`
  - optional `sourceRefId`
- token hits highlight exact token when available
- rescue/page-window hits open exact source context
- fallback span hits highlight exact stored span instead of approximate line-only text
- route params include only provenance fields present in the selected hit payload

### Existing access rule
- `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, `ADMIN` may use project search where they already have project access
- `AUDITOR` does not use the interactive project search surface

## Implementation scope

### 1. Canonical search page UX
Implement or refine the search route.

Requirements:
- one coherent search page
- route access behavior matches existing role rules (`PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, `ADMIN` allowed; `AUDITOR` blocked)
- query input
- compact filters
- results list
- clear active index/version context when helpful
- calm, internal-tool visual tone
- no second search surface elsewhere

### 2. Zero, empty, loading, and no-results states
Use the shared state system coherently.

Requirements:
- zero-state invites exact project search without fluff
- loading preserves layout stability
- no-results state is specific and helpful
- query-error state is safe and exact
- no marketing-search clichés or fake suggestions

### 3. Result cards and grouping
Implement or refine result presentation.

Requirements:
- result cards show:
  - document
  - page
  - run context when useful
  - hit text snippet
  - token/source provenance hint when useful
- grouping is calm and useful if the current repo can support it cleanly
- no giant table if result cards are the stronger fit
- keyboard focus order is clear
- cards do not become noisy mini dashboards

### 4. Highlight and snippet rendering
Make search previews exact.

Requirements:
- token-based hits highlight exact text where token provenance exists
- rescue/page-window hits explain source provenance without pretending a token exists
- fallback `match_span_json` is rendered exactly, not approximately
- snippets do not recompute search logic client-side
- snippet rendering is stable and auditable from the backend payload

### 5. Jump-to-context behavior
Implement or refine result-open transitions.

Requirements:
- result click/keyboard open goes to the exact transcription workspace context
- route transition is predictable
- back/forward returns to search coherently
- selected result can remain visible or restorable after back navigation where low churn and coherent
- no hidden client-only scroll state that breaks reloads

### 6. Filter ergonomics
Refine document/run/page filtering.

Requirements:
- filters map exactly to backend query params
- active filters are visible
- clearing filters is easy
- URL state is reload-safe where appropriate
- no sprawling advanced-search wall

### 7. Keyboard, focus, and accessibility
Harden the search UX.

Requirements:
- keyboard-first query entry and result traversal
- visible focus
- no keyboard traps
- search results can be opened without mouse
- reduced-motion and high-contrast behavior remain coherent
- visual baselines and accessibility scans cover the main search states

### 8. Documentation
Document:
- search page UX contract
- result-card and highlight behavior
- jump-to-context rules
- what later prompts must preserve when adding entity or derivative discovery alongside search

## Required deliverables
Create or refine the closest coherent equivalent of:

### Web
- `/projects/:projectId/search`
- zero/loading/empty/no-results states
- result cards
- exact snippet/highlight rendering
- jump-to-context behavior
- browser tests and visual baselines

### Backend / contracts
- only tiny typed or snippet-helper refinements if strictly needed to keep the UI exact and coherent

### Docs
- search UX and jump-to-context doc
- snippet/highlight rendering contract doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/web/**`
- `/api/**` only if tiny typed/snippet-helper refinements are strictly needed
- `/packages/contracts/**`
- `/packages/ui/**`
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- search backend logic
- entity discovery
- derivative discovery
- semantic ranking changes
- a second search UI
- AI chat or assistant-style search presentation

## Testing and validation
Before finishing:
1. Verify zero, loading, empty, and no-results states are distinct and coherent.
2. Verify result cards render exact provenance-backed snippets.
3. Verify token-based hits open with exact token context.
4. Verify rescue/page-window hits open exact source context.
5. Verify fallback span hits use exact stored spans.
6. Verify initial search fetch without cursor renders the deterministic first result page and pagination advances via cursor.
7. Verify jump URLs include only optional provenance params present in the selected hit payload and still open the correct workspace context.
8. Verify keyboard traversal and result opening work.
9. Verify back/forward navigation remains coherent.
10. Verify visual and accessibility checks pass on the search surface.
11. Verify route-access role boundaries are enforced (`PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, `ADMIN` allowed; `AUDITOR` blocked).
12. Verify docs match the implemented search UX behavior.
13. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the search UI is real and polished
- result snippets and highlights are exact
- jump-to-context is real and trustworthy
- the UX stays calm, dark, dense, and internal-tool grade
- later entity/derivative discovery can coexist without UX churn
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

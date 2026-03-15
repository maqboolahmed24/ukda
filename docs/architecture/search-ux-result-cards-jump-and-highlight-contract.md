# Search UX, Result Cards, Jump, And Highlight Contract

Status: Implemented in Prompt 90
Scope: `/projects/:projectId/search` presentation behavior, state handling, and jump-to-context UX constraints on top of the Prompt 89 API contract.

## Route Ownership

Project search UX is owned by one route:

- `/projects/:projectId/search`

No secondary project search surface, omnibox variant, or alternate result-card system is allowed in this phase.

## Access Boundary

Interactive project search is available to:

- `PROJECT_LEAD`
- `RESEARCHER`
- `REVIEWER`
- `ADMIN`

`AUDITOR` is blocked from the interactive project search route.

## Query And Filter UX Contract

The search page maps exactly to backend query parameters:

- `q` (required)
- `documentId` (optional)
- `runId` (optional)
- `pageNumber` (optional)
- `cursor` (optional)

Behavior:

- zero-state when `q` is absent
- explicit query error state for failed requests
- no-results state when query succeeds but returns no hits
- loading skeleton handled by route `loading.tsx`
- filter state and cursor remain URL-driven and reload-safe
- clear-filters and clear-all actions do not mutate hidden client state

## Result Presentation

Search results are rendered as grouped result cards (grouped by `documentId`) instead of a single dense table.

Each card shows:

- document context
- run and page context
- optional line/token identifiers
- source provenance (`sourceKind`, `sourceRefId`)
- snippet text
- open action

Result order remains backend-defined; the UI does not re-rank.

## Snippet And Highlight Semantics

Snippet rendering is payload-driven.

Highlight precedence:

1. Exact `matchSpanJson` offsets when present.
2. Query-match fallback highlight when no explicit span is available.

Provenance handling:

- token hits are labeled as token-anchored
- rescue/page-window hits surface source provenance directly
- non-token fallback spans are labeled as exact fallback span

The UI does not fabricate synthetic provenance fields and does not run alternate client-side search ranking logic.

## Jump-To-Context Contract

`Open` uses the existing open endpoint flow and lands in:

- `/projects/:projectId/documents/:documentId/transcription/workspace`

With required:

- `page`
- `runId`

And optional provenance params only when present:

- `lineId`
- `tokenId`
- `sourceKind`
- `sourceRefId`

Back/forward remains URL-coherent because search query/filter/cursor state is encoded in route query params.

## Keyboard And Accessibility

The search route must support:

- keyboard-first query and filter entry
- tab navigation to per-hit `Open` actions
- Enter activation for jump-to-context
- visible focus treatment
- route-level accessibility scan coverage for core search states

## Prompt Boundary For Later Discovery Surfaces

Future entity/derivative discovery prompts must preserve:

- the canonical project search route behavior above
- Prompt 89 payload semantics
- provenance-aware jump rules

Additional discovery routes may coexist, but should not redefine search-card semantics or open-URL parameter rules for `/projects/:projectId/search`.

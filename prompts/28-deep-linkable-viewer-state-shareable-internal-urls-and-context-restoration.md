You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed phase files before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first on each run.

## Mandatory first actions
1. Inspect the relevant repository areas and any existing implementation this prompt may extend.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-01-ingest-document-viewer-v1.md`
3. Then review the current repository generally — viewer route code, URL-state helpers, shell/layout contracts, page APIs, typed data layer, browser tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second viewer-state model, a second route contract, or hidden client-only state that conflicts with the URL.

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
- `/phases` wins for deep-linkable route ownership, viewer workspace behavior, single-fold shell rules, browser page-query semantics, and acceptance logic.
- Official docs win only for implementation mechanics.
- Keep viewer URLs shareable, internal, stable, and exact. Do not dump noisy ephemeral state into the URL or hide important context in transient client memory.

## Objective
Add deep-linkable viewer state, shareable internal URLs, and exact context restoration.

This prompt owns:
- the canonical URL-state contract for the viewer
- internal shareable links for exact viewer context
- restoration of useful viewer context across refresh, back/forward, and route return
- explicit separation between URL-shareable state and local ephemeral state
- browser-safe normalization for viewer query params
- current viewer-state integration with the shell and typed data layer

This prompt does not own:
- annotation or review overlays
- compare-mode deep linking beyond what already exists in the repo
- public/share-anywhere URLs
- secret-bearing URLs
- a second local-only state system that fights the route state

## Phase alignment you must preserve
From Phase 1 and the shell/route contract:

### Canonical viewer route contract
- `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`

### Existing route-state rules to preserve
- browser `page` query parameters are human-facing 1-based page numbers
- route and URL state must be reload-safe and deep-linkable
- breadcrumbs provide orientation only
- the viewer remains a bounded single-fold workspace

### Viewer workspace contract to preserve
- toolbar
- filmstrip
- canvas
- inspector/drawer path
- keyboard-safe page navigation
- no raw-original delivery

### Shareable internal-URL rule
Links must remain:
- internal
- authenticated
- RBAC-protected
- free of secrets/tokens
- stable enough for reviewers and teammates inside the same secure environment

## Implementation scope

### 1. Canonical viewer URL-state contract
Define and implement the viewer's URL-state contract.

At minimum support:
- `page` (required canonical viewer state, 1-based)
- additional URL-shareable viewer state only where it is genuinely useful and stable

Good candidates for URL-shareable state:
- `zoom` (`fit-width`, `fit-page`, or a bounded numeric zoom value)
- `filmstrip` (`open|closed`)
- `inspector` (`open|closed`)
- `panel` or `tab` only if the current inspector already has stable subpanels

Rules:
- keep the contract small
- do not dump transient drag/pan offsets, hover state, or implementation noise into the URL
- malformed params degrade safely
- canonicalization is explicit and testable

### 2. Shareable internal links
Implement or refine shareable internal viewer links.

Requirements:
- a user can copy an internal link to the current viewer context
- the link preserves the canonical shareable state
- opening the link restores that state when the recipient is authorized
- unauthorized recipients fail closed through the normal auth/RBAC path
- no secrets, tokens, storage paths, or raw asset URLs are embedded in the link

You may expose this through a restrained “Copy link” action in the viewer toolbar or overflow if appropriate.

### 3. Context restoration
Implement useful viewer-state restoration across navigation and reload.

Requirements:
- refresh restores canonical URL-shareable state
- browser back/forward behaves predictably
- navigating from document detail or library back into the viewer preserves meaningful context
- non-shareable but useful local context may be restored from local/session state only if:
  - it does not fight the URL
  - it is scoped safely per document/project
  - it contains no sensitive secrets
  - it is clearly subordinate to the canonical URL state

Good candidates for local-only restoration:
- filmstrip scroll offset
- last focused pane
- non-shareable local inspector expansion state

### 4. URL normalization and helpers
Implement or refine typed URL-state helpers for the viewer.

Requirements:
- normalization for `page`
- normalization for any added state params
- safe fallback defaults
- canonical push/replace behavior
- no duplicated stringly-typed query handling scattered across components
- integration with the current repo's route/data layer

### 5. Viewer integration
Wire the viewer UI to the canonical URL-state contract.

Requirements:
- page navigation updates URL correctly
- page jump updates URL correctly
- zoom mode/value updates URL only if it is part of the canonical shareable contract you implement
- filmstrip/inspector state updates URL only if chosen as canonical shareable state
- non-shareable transient UI state stays out of the URL
- route-driven hydration stays consistent on reload and deep link open

### 6. Route safety and shell continuity
Preserve the viewer's shell quality.

Requirements:
- shell stays mounted while viewer state changes
- URL changes do not create unnecessary full resets
- focus behavior remains predictable across URL-driven state changes
- deep-linked openings still land inside the bounded viewer shell
- error and not-found behavior stay safe and serious

### 7. Copy-link ergonomics
If you expose copy-link UI, keep it restrained.

Requirements:
- one clear affordance
- exact confirmation state
- no noisy toast spam
- no marketing-style sharing copy
- internal-only wording
- no implication that the link is public or externally accessible

### 8. Testing
Add meaningful regression coverage for:
- deep link open
- refresh restoration
- back/forward behavior
- invalid query normalization
- page-jump URL updates
- share link generation
- unauthorized deep-link access failure path
- focus and shell continuity where practical

### 9. Documentation
Document:
- the viewer URL-state contract
- what is shareable vs local-only
- normalization rules
- copy-link behavior
- how later work should add viewer state without polluting the URL

## Required deliverables

### Web
- viewer URL-state helpers
- deep-link/share-link behavior
- context restoration behavior
- any small viewer-toolbar or overflow additions needed for copy-link or state awareness
- tests

### Docs
- viewer deep-link and URL-state contract doc
- context-restoration and share-link policy doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/web/**`
- `/packages/contracts/**` only if small shared viewer-state enums or types help consistency
- `/packages/ui/**` only if small toolbar/overflow/link-copy refinements are needed
- `/api/**` only if a small helper is required for consistent auth-safe link behavior, and only if the current repo truly needs it
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- public share links
- tokenized or secret-bearing URLs
- annotation/review overlays
- a giant URL-state matrix for every transient UI detail
- a second viewer-state store that conflicts with the route
- raw asset URLs in copied links

## Testing and validation
Before finishing:
1. Verify deep-linked viewer URLs open correctly for authorized users.
2. Verify refresh restores canonical viewer state.
3. Verify browser back/forward preserves viewer context predictably.
4. Verify malformed params normalize safely.
5. Verify `page` remains 1-based in the browser.
6. Verify copied internal links contain no secrets or raw asset paths.
7. Verify unauthorized deep-link access fails closed.
8. Verify shell continuity and focus behavior remain consistent during URL-state changes.
9. Verify docs match the implemented URL-state contract and restoration behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- the viewer has a real canonical URL-state contract
- internal links can restore meaningful viewer context
- refresh and back/forward behavior are consistent
- the URL stays clean and shareable without leaking secrets
- transient local-only state remains subordinate to canonical route state
- the viewer enforces bounded workspace behavior without uncontrolled page growth and preserves keyboard/pointer navigation
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

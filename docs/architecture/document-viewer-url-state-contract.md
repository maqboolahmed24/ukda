# Document Viewer URL-State Contract

> Status: Active (Prompt 28)
> Scope: Canonical deep-linkable viewer route state for internal authenticated use

This contract defines the shareable URL state for the Phase 1 document viewer.

## Canonical Route

- `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`

Viewer state is internal-only and RBAC-protected under authenticated routes.

## Shareable Query Keys

- `page` (required, 1-based)
- `zoom` (optional numeric percent, bounded)

### `page` Rules

- Human-facing and strictly 1-based.
- Missing, malformed, or out-of-range values normalize to a safe canonical value.
- Canonical URL always contains `page`.

### `zoom` Rules

- Numeric percent only.
- Bounds: `25` to `400`.
- Default zoom is `100`.
- Canonical URL omits `zoom` when value is default (`100`).
- Malformed or out-of-range values normalize to bounded canonical values.

## Canonicalization Behavior

Viewer query values are normalized by typed helpers and redirected to canonical URLs.

Examples:

- `?page=0002&zoom=100` -> `?page=2`
- `?page=0&zoom=9999` -> `?page=1&zoom=400`
- `?page=abc` -> `?page=1`

## URL-State Ownership

Shareable URL state is intentionally small:

- shareable: `page`, `zoom`
- local-only: pan offsets, drag state, transient hover/focus details, temporary control feedback

Local-only state must never override canonical URL state.

## Navigation Semantics

- page changes use history navigation suitable for back/forward workflows
- zoom updates replace route state to avoid history spam
- filmstrip page links and page-jump actions preserve current shareable viewer context

## Security And Privacy Rules

- No secrets/tokens are permitted in viewer URLs.
- No raw storage paths or raw asset URLs are permitted in viewer URLs.
- Deep links remain internal and require normal auth/session + project RBAC checks.

## Ingest-Status Recovery Handoff

Viewer recovery links may pass the same `page` and `zoom` values into the ingest-status route as optional handoff hints.
Those hints are used only for return navigation and do not expand canonical viewer URL ownership.

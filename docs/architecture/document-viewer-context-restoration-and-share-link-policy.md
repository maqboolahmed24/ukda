# Document Viewer Context Restoration And Share-Link Policy

> Status: Active (Prompt 28)
> Scope: Refresh/back-forward restoration, local-only context persistence, and internal copy-link behavior

This policy defines how viewer context is restored and how internal links are shared safely.

## Restoration Guarantees

- Refresh restores canonical shareable state from URL (`page`, `zoom`).
- Browser back/forward restores prior viewer context predictably.
- Deep-link openings restore viewer context when the user is authorized.

## Local-Only Restoration

Local-only restoration is allowed when it does not conflict with URL state.

Current local-only viewer restoration:

- filmstrip scroll offset persisted in `sessionStorage`
- storage scope key: `ukde.viewer.filmstrip-scroll:{projectId}:{documentId}`

Constraints:

- no secrets in local storage values
- no cross-document leakage of local context
- URL state remains source of truth for shareable context

## Internal Copy-Link Behavior

Viewer overflow includes one copy affordance:

- `Copy internal link`

Rules:

- Copies current canonical viewer URL (including normalized non-default `zoom` when present)
- Shows restrained inline confirmation state in the toolbar region
- No public-sharing language
- No tokenized or signed URLs

## Fail-Closed Behavior

- Unauthorized or unauthenticated deep-link opens follow normal auth/RBAC failure paths.
- Viewer links do not bypass session checks.
- Copied links never embed raw asset/storage paths.

## Extension Guidance

When adding future viewer state keys:

1. Add typed normalization helpers first.
2. Keep URL contract compact and review-grade.
3. Separate shareable keys from local-only interaction noise.
4. Add regression coverage for deep-link open, refresh restoration, and back/forward behavior.

## Ingest-Status Handoff

Viewer recovery actions now link to `/ingest-status` with optional `page` and `zoom` hints.
Those hints are used for return navigation into viewer context when available and do not replace canonical viewer URL ownership.

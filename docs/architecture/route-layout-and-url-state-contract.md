# Route Layout And URL-State Contract

> Status: Active baseline (Prompt 14)
> Scope: Canonical browser route hierarchy, nested layout ownership, and query-state rules

This document is the current implementation contract for route ownership in `web/app`.

## Canonical Route Groups

Routes are organized into one route-group hierarchy:

- Root:
  - `/` (auth-aware redirect to `/login` or `/projects`)
- Public/system group (`web/app/(public)/**`):
  - `/login`
  - `/logout`
  - `/health`
  - `/error` (safe user-facing error route)
- Authenticated group (`web/app/(authenticated)/**`):
  - `/projects`
  - `/activity`
  - `/admin/**`
  - `/projects/:projectId/**`

Auth callback and auth handshake handlers remain at `/auth/**`.

## Nested Layout Ownership

Layout ownership is singular and non-overlapping:

- `web/app/layout.tsx`: global app frame, theme/runtime sync
- `web/app/(public)/layout.tsx`: public/system routes
- `web/app/(authenticated)/layout.tsx`: authenticated shell
- `web/app/(authenticated)/projects/[projectId]/layout.tsx`: project workspace context and page header
- `web/app/(authenticated)/projects/[projectId]/documents/layout.tsx`: document-route family
- `web/app/(authenticated)/admin/layout.tsx`: admin role boundary

Admin route composition details are defined in:

- [`/docs/architecture/admin-governance-shell-contract.md`](./admin-governance-shell-contract.md)

Do not introduce a second authenticated shell path or duplicate global headers in child routes.

## Locked Project Route Contract

Project-scoped routes that are implemented or scaffolded now:

- `/projects/:projectId/overview`
- `/projects/:projectId/documents`
- `/projects/:projectId/documents/import`
- `/projects/:projectId/documents/:documentId`
- `/projects/:projectId/documents/:documentId/viewer?page={pageNumber}`
- `/projects/:projectId/documents/:documentId/ingest-status`
- `/projects/:projectId/jobs`
- `/projects/:projectId/jobs/:jobId`
- `/projects/:projectId/activity`
- `/projects/:projectId/settings`
- `/projects/:projectId/export-candidates`
- `/projects/:projectId/export-requests`
- `/projects/:projectId/export-review`

## URL-State Discipline

URL state is reserved for context that must survive refresh, sharing, and browser back/forward.

Rules:

- Use stable object IDs in path segments.
- Use query parameters for durable view state.
- Do not place secrets, raw PII, or mutable draft text in query params.
- Malformed query values degrade safely to defaults.

Current normalized query keys:

- Viewer:
  - `page` is human-facing and strictly 1-based.
  - Missing or malformed `page` is normalized to `1`.
  - `zoom` is optional, bounded numeric percent (`25` to `400`), and is omitted when default (`100`).
- Shell mode:
  - `shell=focus` is the only supported explicit shell override.
- Cursor/list routes:
  - cursor values are normalized to non-negative integers.
- Free-text filters:
  - whitespace-only values normalize to absent.
- Documents library:
  - canonical keys: `search`, `status`, `uploader`, `from`, `to`, `sort`, `direction`, `cursor`
  - `from` and `to` are `YYYY-MM-DD` in route state
  - legacy `q` aliases to `search` and is canonicalized on navigation

Detailed library behavior is defined in:

- [`/docs/architecture/document-library-search-filter-sort-contract.md`](./document-library-search-filter-sort-contract.md)

Persisted storage fields keep explicit 0-based naming when required (for example `page_index`).

## Breadcrumb Contract

Breadcrumbs are orientation-only.

- They reflect route ancestry from `Projects -> Project -> Surface -> Object`.
- They are not action menus.
- Actions stay in page headers or explicit controls.

Implemented ancestry examples:

- `Projects -> {Project} -> Documents`
- `Projects -> {Project} -> Documents -> Document`
- `Projects -> {Project} -> Documents -> Document -> Viewer -> Page {n}`
- `Projects -> {Project} -> Documents -> Document -> Ingest status`

## Boundary Contract

Every route family owns explicit loading/error/not-found behavior:

- Public, authenticated, admin, and project segments each define scoped boundaries.
- Project/document failures stay inside the mounted authenticated shell.
- `/error` is always available as a sanitized fallback route.

Detailed boundary placement is documented in:

- [`/docs/architecture/loading-error-boundary-placement.md`](./loading-error-boundary-placement.md)
- [`/docs/architecture/state-feedback-language-and-priority.md`](./state-feedback-language-and-priority.md)
- [`/docs/architecture/state-copy-guidelines.md`](./state-copy-guidelines.md)

## Route Extension Rules

When adding a new route:

1. Place it under the correct ownership layout (public, authenticated, project, or admin).
2. Define URL-state keys explicitly and normalize malformed values.
3. Add/verify segment-level `loading.tsx` and `error.tsx`; add `not-found.tsx` where object identity is part of the path.
4. Keep breadcrumbs purely orientational.
5. Preserve deep-link and reload safety; no hidden client-only state should be required to restore context.

Concrete nested-route example:

- New OCR review route:
  - Path: `/projects/:projectId/documents/:documentId/ocr-review`
  - Filesystem: `web/app/(authenticated)/projects/[projectId]/documents/[documentId]/ocr-review/page.tsx`
  - Ownership: inherits authenticated shell + project layout + documents layout
  - Query rule: if it adds `line`, normalize to a positive integer and fallback safely.

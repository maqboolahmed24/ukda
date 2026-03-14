# Document Library Search, Filter, Sort, And Drawer Contract

> Status: Active (Prompt 25)
> Route owner: `/projects/:projectId/documents`
> Scope: Phase 1.2 document library behavior for list management, URL state, details drawer, and restrained bulk actions

## Route And Surface Ownership

- Route: `/projects/:projectId/documents`
- Primary page-header action remains `Import document`.
- Primary canvas remains the shared `DataTable` + right-side `DetailsDrawer` pattern.

The route is the canonical document inventory surface and does not create a second list implementation.

## Canonical URL-State Keys

The route owns these query keys:

- `search`: free-text name filter
- `status`: document status enum
- `uploader`: uploader identifier filter
- `from`: lower date bound (`YYYY-MM-DD`)
- `to`: upper date bound (`YYYY-MM-DD`)
- `sort`: `updated | created | name`
- `direction`: `asc | desc`
- `cursor`: non-negative numeric cursor offset

Rules:

- URL state is reload-safe and back/forward-safe.
- Malformed values are normalized to safe defaults.
- Legacy `q` is accepted by the API for compatibility, but the web route canonicalizes to `search`.
- Filter/search updates reset cursor paging to `0`.

## List API Contract

- Endpoint: `GET /projects/{projectId}/documents`
- Supported query params: `search`, legacy `q`, `status`, `uploader`, `from`, `to`, `sort`, `direction`, `cursor`, `pageSize`
- RBAC: project-member scoped.
- Sorting and pagination: server-side only.
- Pagination contract: cursor-based (`nextCursor` in response).
- Date parsing: accepts `YYYY-MM-DD` and ISO-8601 datetimes; invalid ranges return `422`.

## Details Drawer Contract

Row selection opens right-side `DetailsDrawer` with:

- metadata summary
- processing timeline (hydrated from `GET /projects/{projectId}/documents/{documentId}/timeline`)
- primary CTA `Open document`
- secondary CTA `View ingest status` (anchors document detail timeline section in Phase 1.2)

Behavior:

- drawer is focus-trapped
- close returns focus to the prior table target
- timeline states are explicit (`loading`, `error`, `empty`, `ready`)

## Bulk Selection And Bulk Action Rail

Prompt 25 ships restrained bulk infrastructure:

- multi-select checkboxes in the table
- selection count
- clear selection control
- safe non-destructive action (`Open first selected`)
- role-aware deferred mutation slot (`Retry extraction (pending)`) shown only for roles that would own mutation rights later

Deferred explicitly:

- destructive bulk mutations
- unsupported server-side bulk semantics


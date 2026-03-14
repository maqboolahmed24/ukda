# Admin Governance Shell Contract (Prompt 18)

> Status: Active baseline
> Scope: Platform admin and auditor web surfaces under `/admin/**`

This document defines the canonical browser contract for platform governance surfaces.

## Ownership

The admin shell is implemented by:

- `web/app/(authenticated)/admin/layout.tsx`
- `web/components/admin-console-shell.tsx`
- `web/lib/admin-console.ts`

The authenticated app shell remains the top-level workspace frame, and `/admin/**` renders inside it. Admin navigation ownership is in the admin layout and is not duplicated by the shared authenticated context navigation.

## Route Family

Platform governance routes currently implemented:

- `/admin` (role-aware module landing)
- `/admin/audit`
- `/admin/audit/:eventId`
- `/admin/security`
- `/admin/operations`
- `/admin/operations/export-status`
- `/admin/operations/slos`
- `/admin/operations/alerts`
- `/admin/operations/timelines`
- `/admin/design-system`

`/admin/**` routes are platform-scoped and never substitute for project-scoped governance routes.

## Navigation Model

Admin navigation is grouped and role-aware:

- `Overview`
- `Governance`
- `Operations`
- `Internal`

Visibility is computed from `web/lib/admin-console.ts`, which is the single source for:

- visible surfaces by platform role
- grouping metadata
- read-only annotations for `AUDITOR`

## Role And Read-Only Contract

- `ADMIN` gets full access to implemented admin surfaces.
- `AUDITOR` gets explicit read-only access to designated governance routes.
- `PROJECT_LEAD` remains project-scoped unless a route explicitly grants platform access.

Read-only mode is shown directly in admin page headers and navigation labels instead of hidden behind failing actions.

## Page Contract

Admin pages should use:

- `PageHeader` with route intent and role/read-only context
- dense filter/list/detail patterns for review workflows
- URL-driven filters/cursors on list routes (`/admin/audit`, `/admin/operations/alerts`, `/admin/operations/timelines`)
- explicit "not yet implemented" states for future signals instead of synthetic data

## Platform vs Project Boundary

- Platform audit and operations live in `/admin/**`.
- Project-scoped governance/activity lives in `/projects/:projectId/**`.
- Shared visual primitives are allowed, but route ownership and RBAC boundaries stay explicit.

## Extension Rules

When adding new admin/governance routes:

1. Add route-level server guard with `requirePlatformRole(...)`.
2. Register the surface in `web/lib/admin-console.ts` with role visibility and group.
3. Keep auditor behavior read-only unless phases explicitly allow mutation.
4. Update this contract and the role matrix document.
5. Avoid introducing parallel admin navigation systems.

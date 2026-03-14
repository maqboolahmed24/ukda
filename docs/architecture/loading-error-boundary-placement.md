# Loading And Error Boundary Placement

> Status: Active baseline (Prompt 14)
> Scope: Segment-level suspense/loading/error/not-found behavior in the web app

This document defines where boundaries are placed so the shell remains stable and route failures stay safe.

## Boundary Map

Global:

- `web/app/loading.tsx`
- `web/app/error.tsx`
- `web/app/not-found.tsx`

Public/system:

- `web/app/(public)/loading.tsx`
- `web/app/(public)/error.tsx`
- `web/app/(public)/error/page.tsx` (safe fallback route)

Authenticated shell:

- `web/app/(authenticated)/loading.tsx`
- `web/app/(authenticated)/error.tsx`

Admin family:

- `web/app/(authenticated)/admin/loading.tsx`
- `web/app/(authenticated)/admin/error.tsx`
- `web/app/(authenticated)/admin/not-found.tsx`

Project family:

- `web/app/(authenticated)/projects/[projectId]/loading.tsx`
- `web/app/(authenticated)/projects/[projectId]/error.tsx`
- `web/app/(authenticated)/projects/[projectId]/not-found.tsx`

Document family:

- `web/app/(authenticated)/projects/[projectId]/documents/loading.tsx`
- `web/app/(authenticated)/projects/[projectId]/documents/error.tsx`
- `web/app/(authenticated)/projects/[projectId]/documents/[documentId]/loading.tsx`
- `web/app/(authenticated)/projects/[projectId]/documents/[documentId]/not-found.tsx`
- `web/app/(authenticated)/projects/[projectId]/documents/[documentId]/viewer/loading.tsx`
- `web/app/(authenticated)/projects/[projectId]/documents/[documentId]/viewer/error.tsx`

## Placement Rules

- Keep the authenticated shell mounted while child content suspends.
- Prefer skeleton surfaces (`RouteSkeleton`) over spinner-only loading states.
- Use safe, user-facing route error panels (`RouteErrorState`) and avoid exposing internal stack or exception details.
- Keep not-found handling local to route identity when possible (project/doc/admin) and global otherwise.
- Use canonical route copy from `web/lib/route-state-copy.ts` and keep snapshot
  coverage in `web/lib/route-state-copy.test.ts`.

## Failure-Handling Contract

- Route failures are recoverable via explicit retry where available.
- Sanitized fallback routes remain navigable (`/error`, `/projects`, `/login`).
- Unauthorized access remains explicit through existing auth/role guards.

## Adding New Route Families

For each new high-level family:

1. Add `loading.tsx` at the family segment.
2. Add `error.tsx` at the family segment.
3. Add `not-found.tsx` when routes include object IDs.
4. Reuse shared safe primitives:
   - `web/components/route-skeleton.tsx`
   - `web/components/route-error-state.tsx`
   - `web/components/route-not-found-state.tsx`

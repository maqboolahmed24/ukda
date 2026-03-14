# State Feedback Language and Priority

> Status: Active baseline (Prompt 15)
> Scope: Shared feedback vocabulary, priority hierarchy, and placement rules

This document defines one state language for UKDE route, page, section, dialog, drawer, table, and toast feedback.

## Canonical State Vocabulary

Use the shared primitives from `@ukde/ui/primitives`:

- `FeedbackState` (base)
- `PageState`
- `SectionState`
- `InlineState`
- `SkeletonLines`

Supported state kinds:

- `zero`
- `empty`
- `loading`
- `error`
- `success`
- `degraded`
- `disabled`
- `no-results`
- `not-found`
- `unauthorized`

Distinctions that must remain explicit:

- `not-found` is not `empty`
- `disabled` is not `unauthorized`
- `loading` is not long-running workflow progress
- `no-results` is not `zero`

## Feedback Priority Hierarchy

1. `Route boundary` (`loading.tsx`, `error.tsx`, `not-found.tsx`) for route-level ownership failures and recovery.
2. `PageState` for major workflow conditions affecting the whole surface.
3. `SectionState` for local workflow areas (table sections, timeline sections, details regions).
4. `InlineState` or `InlineAlert` for actionable contextual issues near controls.
5. `Toast` for low-risk transient confirmation only.

## Placement Rules

- Route boundaries:
  - Must use shared route primitives (`RouteSkeleton`, `RouteErrorState`, `RouteNotFoundState`).
  - Must keep shell continuity where possible.
- Page states:
  - Use when a user cannot proceed with the main task until the state is resolved.
- Section states:
  - Use for partial failures, local loading, local empty/no-results, and disabled sub-features.
- Dialog and drawer:
  - Use `SectionState` inside overlays for loading/empty/error payload states.
- Table:
  - Use built-in table state rows (`loading`, `error`, `empty`) rather than plain text rows.
- Toast:
  - Do not use as the only success signal when the page state also changes.

## Long-Running Status Rule

Long-running operations (jobs, ingest attempts) must show explicit status and attempts, not indefinite spinner-only feedback.

- Keep state labels visible (`QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELED`).
- Show safe failure summaries inline when available.
- Use polling degradation messaging (`degraded`) when status refresh fails.

## Current Adoption

Implemented in:

- Route boundaries across global/public/authenticated/admin/project/document/viewer route families
- Key route pages (`/login`, `/projects`, project jobs/activity/settings, admin audit/operations/security, export stubs)
- Document/import/viewer scaffolds with state previews for Phase 1 readiness
- `/admin/design-system` state gallery for ongoing validation

## Test Contract

- Route-level copy is snapshotted in:
  - `web/lib/route-state-copy.test.ts`
- Route-level copy source:
  - `web/lib/route-state-copy.ts`

# Project Workspaces And RBAC (Phase 0.2 / Prompt 06)

This document defines the current project workspace contract in the implemented web-first stack.

## Data Persistence

Project and membership persistence is stored in Postgres and initialized lazily by the API.

- `baseline_policy_snapshots`
  - deterministic seeded row id: `baseline-phase0-v1`
  - deterministic SHA-256 `snapshot_hash` over canonical baseline `rules_json`
  - seeded by `SYSTEM_PHASE_0`
- `projects`
  - `id`
  - `name`
  - required `purpose`
  - `status` (`ACTIVE | ARCHIVED`)
  - `created_by`
  - `created_at`
  - required `intended_access_tier` (`OPEN | SAFEGUARDED | CONTROLLED`)
  - required `baseline_policy_snapshot_id`
- `project_members`
  - `project_id`
  - `user_id`
  - `role` (`PROJECT_LEAD | RESEARCHER | REVIEWER`)
  - `created_at`
  - `updated_at`

## Baseline Policy Attachment Behavior

- Baseline snapshot seeding is deterministic and read-only for Phase 0.
- The seed row is inserted if missing and then reused.
- If the seeded row exists with a mismatched hash, API initialization fails to prevent silent drift.
- Every new project attaches `baseline-phase0-v1` during project creation.
- Policy authoring remains deferred until Phase 7.

## API Routes

All routes below require authentication.

- `GET /projects`
  - returns memberships for the current user only
- `POST /projects`
  - creates project
  - creates creator membership as `PROJECT_LEAD`
  - attaches current seeded baseline snapshot id
- `GET /projects/{projectId}`
  - member-scoped project summary (no platform-role override)
- `GET /projects/{projectId}/workspace`
  - workspace context route
  - allows explicit `ADMIN` override when caller is not a member
- `GET /projects/{projectId}/members`
  - settings-scoped members read
  - requires `PROJECT_LEAD` membership or explicit `ADMIN` override
- `POST /projects/{projectId}/members`
  - add member by email
  - requires `PROJECT_LEAD` or explicit `ADMIN` override
- `PATCH /projects/{projectId}/members/{memberUserId}`
  - change member role
  - requires `PROJECT_LEAD` or explicit `ADMIN` override
- `DELETE /projects/{projectId}/members/{memberUserId}`
  - remove member
  - requires `PROJECT_LEAD` or explicit `ADMIN` override

## RBAC Rules Enforced

- Ordinary member workspace routes require project membership.
- `ADMIN` override is explicit and route-scoped; it is not implicit across all project routes.
- `AUDITOR` has no implicit project workspace access.
- `PROJECT_LEAD` can manage members.
- `RESEARCHER` and `REVIEWER` cannot manage members.
- Settings access is restricted to `PROJECT_LEAD` and `ADMIN`.
- Last-`PROJECT_LEAD` demotion or removal is blocked.
- Jobs read access allows `PROJECT_LEAD`, `RESEARCHER`, and `REVIEWER` memberships (plus explicit `ADMIN` override).
- Jobs mutation access (`enqueue`, `retry`, `cancel`) allows `PROJECT_LEAD` and `REVIEWER` memberships (plus explicit `ADMIN` override).

## Web Route Ownership

- `/projects` (authenticated landing)
- `/projects/:projectId/overview` (member-scoped)
- `/projects/:projectId/documents` (member-scoped placeholder)
- `/projects/:projectId/jobs` (member-scoped jobs list and NOOP trigger)
- `/projects/:projectId/jobs/:jobId` (member-scoped job detail and lineage)
- `/projects/:projectId/export-candidates` (member-scoped disabled export candidate stub)
- `/projects/:projectId/export-requests` (member-scoped disabled export request stub)
- `/projects/:projectId/export-review` (member-scoped disabled export review stub)
- `/projects/:projectId/activity` (member-scoped activity/governance surface, distinct from `/admin/audit`)
- `/projects/:projectId/settings` (lead/admin scoped)

## Shell And Navigation Contract

- Project workspace layout includes:
  - header context (identity, switcher, environment, tier badge, help, user menu)
  - left project nav
  - page-header context region
  - content host
- Left nav is link-only.
- Settings nav entry is hidden unless the user can access settings.
- For `ADMIN` override without membership, nav surfaces only permitted settings entry.

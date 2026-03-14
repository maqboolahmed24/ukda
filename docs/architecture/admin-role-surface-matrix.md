# Admin Role-To-Surface Matrix (Prompt 18)

> Status: Active baseline
> Scope: Implemented `/admin/**` web surfaces and project activity boundary

This matrix describes current route visibility and interaction mode.

## Platform Routes

| Route | ADMIN | AUDITOR | PROJECT_LEAD (no platform role) | Notes |
| --- | --- | --- | --- | --- |
| `/admin` | Access | Access (read-only context) | No access | Role-aware module landing |
| `/admin/audit` | Access | Access (read-only) | No access | URL-driven filters and cursor |
| `/admin/audit/:eventId` | Access | Access (read-only) | No access | Event detail drilldown |
| `/admin/security` | Access | Access (read-only) | No access | Security posture summary |
| `/admin/operations` | Access | No access | No access | Operator overview (`ADMIN` only) |
| `/admin/operations/export-status` | Access | Access (read-only) | No access | Read-only governance signal |
| `/admin/operations/slos` | Access | No access | No access | `ADMIN` only |
| `/admin/operations/alerts` | Access | No access | No access | `ADMIN` only |
| `/admin/operations/timelines` | Access | Access (read-only) | No access | Read-only timeline review |
| `/admin/design-system` | Access | Access (read-only) | No access | Internal diagnostics route |

## Project-Scoped Governance Boundary

| Route | ADMIN | AUDITOR | PROJECT_LEAD | Notes |
| --- | --- | --- | --- | --- |
| `/projects/:projectId/activity` | Membership/override rules apply | No implicit access | Membership access | Project-scoped timeline surface, distinct from platform audit |

## Notes

- Platform role overrides are explicit and route-scoped.
- `AUDITOR` access is governance read-only only, never implied write access.
- This matrix must stay aligned with `web/lib/admin-console.ts`, route guards, and page-level UI affordances.

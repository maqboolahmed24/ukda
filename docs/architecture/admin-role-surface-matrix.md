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
| `/admin/security/findings` | Access | Access (read-only) | No access | Security findings and pen-test checklist |
| `/admin/security/findings/:findingId` | Access | Access (read-only) | No access | Finding detail and linked acceptances |
| `/admin/security/risk-acceptances` | Access | Access (read-only) | No access | Risk-acceptance projection list |
| `/admin/security/risk-acceptances/:riskAcceptanceId` | Access | Access (read-only) | No access | Acceptance detail; admin-only mutations |
| `/admin/security/risk-acceptances/:riskAcceptanceId/events` | Access | Access (read-only) | No access | Append-only acceptance events |
| `/admin/operations` | Access | No access | No access | Operator overview (`ADMIN` only) |
| `/admin/operations/readiness` | Access | Access (read-only safe slice) | No access | Cross-phase readiness matrix; auditor view excludes admin-only categories |
| `/admin/operations/export-status` | Access | Access (read-only) | No access | Read-only governance signal |
| `/admin/runbooks` | Access | No access | No access | Canonical launch and rollback runbook list (`ADMIN` only) |
| `/admin/runbooks/:runbookId` | Access | No access | No access | Runbook metadata and rendered content (`ADMIN` only) |
| `/admin/incidents` | Access | Access (read-only) | No access | Launch and early-life incident list |
| `/admin/incidents/status` | Access | Access (read-only) | No access | No-go trigger summary and rehearsal completion posture |
| `/admin/incidents/:incidentId` | Access | Access (read-only) | No access | Incident command summary and timeline preview |
| `/admin/incidents/:incidentId/timeline` | Access | Access (read-only) | No access | Incident timeline chronology |
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

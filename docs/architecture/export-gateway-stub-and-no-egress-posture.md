# Export Gateway Stub And No-Egress Posture (Phase 0.5)

Phase 0 reserves the export gateway contract while intentionally preventing any live export behavior.

## Disabled Route Contract

The following project-scoped routes exist as disabled stubs and return `501` with code `EXPORT_GATEWAY_DISABLED_PHASE0`:

- `GET /projects/{projectId}/export-candidates`
- `GET /projects/{projectId}/export-candidates/{candidateId}`
- `POST /projects/{projectId}/export-requests`
- `GET /projects/{projectId}/export-requests`
- `GET /projects/{projectId}/export-requests/{exportRequestId}`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/status`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/release-pack`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/events`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/reviews`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/start-review`
- `GET /projects/{projectId}/export-requests/{exportRequestId}/receipt`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/resubmit`
- `POST /projects/{projectId}/export-requests/{exportRequestId}/decision`
- `GET /projects/{projectId}/export-review`

`resubmit` and `decision` responses explicitly reserve Phase 8 semantics without implementing them.

## Minimal Stub Persistence

Phase 0 persistence is intentionally minimal:

- `export_stub_events`
  - `id`
  - `project_id` (nullable)
  - `route`
  - `method`
  - `actor_user_id` (nullable)
  - `request_id`
  - `created_at`

No Phase 8 export-request, review, receipt, or release-pack schemas are created in this iteration.

## Audit And Access

- Every stub attempt writes:
  - one `export_stub_events` row
  - one `EXPORT_STUB_ROUTE_ACCESSED` audit event
- Route access remains project-scoped and deny-by-default:
  - project members can access project export stubs
  - explicit admin override follows existing project workspace rules
  - unauthorized attempts emit `ACCESS_DENIED`

## Web Surfaces

The disabled routes are surfaced as explicit UI stubs:

- `/projects/:projectId/export-candidates`
- `/projects/:projectId/export-requests`
- `/projects/:projectId/export-review`

Each page keeps action controls disabled and explains that screening/export behavior is deferred to Phase 8.

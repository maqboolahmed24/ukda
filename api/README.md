# UKDE API

This package is the FastAPI bootstrap for UKDE. It owns:

- `GET /healthz` liveness
- `GET /readyz` readiness with a real Postgres probe and model-service-map validation
- auth/session boundaries with OIDC + explicit dev auth mode
- deny-by-default protected routes and reusable platform-role guards
- jobs framework baseline with append-only `job_events`, retry lineage, and worker claim/finalize transitions
- privacy-safe telemetry baseline for request metrics, trace propagation, and operations diagnostics
- operations read APIs under `/admin/operations/*` with role-scoped access
- baseline settings and internal-only model wiring contract validation
- provenance bundle verification and replay tooling (`ukde-bundle-verify`, `ukde-provenance-replay`)

Implemented project jobs APIs:

- `GET /projects/{projectId}/jobs`
- `POST /projects/{projectId}/jobs` (Phase 0 `NOOP`)
- `GET /projects/{projectId}/jobs/summary`
- `GET /projects/{projectId}/jobs/{jobId}`
- `GET /projects/{projectId}/jobs/{jobId}/status`
- `GET /projects/{projectId}/jobs/{jobId}/events`
- `POST /projects/{projectId}/jobs/{jobId}/retry`
- `POST /projects/{projectId}/jobs/{jobId}/cancel`

It intentionally stops short of Phase 1+ ingest/preprocessing/layout/transcription/privacy handlers.

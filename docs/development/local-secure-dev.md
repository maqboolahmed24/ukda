# Local Secure Development

This guide brings up the Phase 0.1 alive vertical slice: browser shell, API liveness/readiness, Postgres-backed `/readyz`, and model-service-map validation.
It now includes Phase 0.2 authentication boundaries, role-aware route guards, protected `/projects` and `/admin` surfaces, and the Phase 0.4 jobs runtime baseline.

## Prerequisites

- Node.js `24.10.0+`
- `pnpm 10.23.0+`
- Python `3.12+`
- Docker Desktop (for local Postgres and container smoke mode)

## Environment Setup

1. Copy `.env.example` to `.env`.
2. Adjust paths if needed:

- `MODEL_DEPLOYMENT_ROOT`
- `MODEL_ARTIFACT_ROOT`
- `MODEL_CATALOG_PATH`
- `MODEL_SERVICE_MAP_PATH`

3. Keep API origins aligned with runtime mode:

- `NEXT_PUBLIC_UKDE_API_ORIGIN` is the browser-visible API origin (default `http://127.0.0.1:8000`).
- `UKDE_API_ORIGIN_INTERNAL` is the server-side fetch origin used by the Next.js runtime. Keep it equal to `NEXT_PUBLIC_UKDE_API_ORIGIN` for host-native dev, and use service DNS (for example `http://api:8000`) in containerized mode.

4. Keep `MODEL_DEPLOYMENT_ROOT` and `MODEL_ARTIFACT_ROOT` outside the repository.
5. Keep list variables as JSON arrays:

- `WEB_ORIGINS=["http://127.0.0.1:3000","http://localhost:3000"]`
- `MODEL_ALLOWLIST=["TRANSCRIPTION_PRIMARY","ASSIST","PRIVACY_NER","PRIVACY_RULES","TRANSCRIPTION_FALLBACK","EMBEDDING_SEARCH"]`
- `OUTBOUND_ALLOWLIST=["localhost","127.0.0.1","::1",".internal",".local"]`

6. Auth defaults for local development:

- `AUTH_DEV_MODE_ENABLED=true` enables explicit seeded local identities.
- Keep `AUTH_SESSION_SECRET` set in local `.env`; replace it for any shared environment.
- Real OIDC is activated only when all required `OIDC_*` values are set.

7. Telemetry defaults for local development:

- `TELEMETRY_EXPORT_MODE=none` keeps export disabled by default.
- If export mode is enabled later, `TELEMETRY_OTLP_ENDPOINT` must remain internal-only.

8. Security hardening defaults:

- `SECURITY_CSP_MODE=enforce`
- `AUTH_RATE_LIMIT_MAX_REQUESTS=30`
- `PROTECTED_RATE_LIMIT_MAX_REQUESTS=300`

## Fast Host-Native Dev Path (Recommended)

1. Install dependencies:

```bash
pnpm install
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
make install-python
```

2. Start Postgres:

```bash
make dev-db-up
```

3. Start API:

```bash
source .venv/bin/activate
set -a && source .env && set +a
cd api
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

4. Start web shell in another terminal:

```bash
set -a && source .env && set +a
pnpm dev:web
```

5. Open:

- `http://127.0.0.1:3000/` (entry resolver redirects to `/login` until authenticated, then `/projects`)
- `http://127.0.0.1:3000/health` (live API diagnostics)
- `http://127.0.0.1:3000/login` (OIDC or seeded dev sign-in)
- `http://127.0.0.1:3000/projects` (protected route)
- `http://127.0.0.1:3000/projects/:projectId/overview` (member-scoped workspace route)
- `http://127.0.0.1:3000/projects/:projectId/jobs` (project jobs list)
- `http://127.0.0.1:3000/projects/:projectId/jobs/:jobId` (job detail and status polling)
- `http://127.0.0.1:3000/projects/:projectId/settings` (`PROJECT_LEAD` and `ADMIN` only)
- `http://127.0.0.1:3000/admin/design-system` (platform-role protected route)
- `http://127.0.0.1:3000/admin/audit` (`ADMIN` and `AUDITOR` read-only audit viewer)
- `http://127.0.0.1:3000/activity` (current-user activity surface)
- `http://127.0.0.1:3000/admin/operations` (`ADMIN` operations overview)
- `http://127.0.0.1:3000/admin/operations/slos` (`ADMIN` SLO surface)
- `http://127.0.0.1:3000/admin/operations/alerts` (`ADMIN` alert surface)
- `http://127.0.0.1:3000/admin/operations/timelines` (`ADMIN` and read-only `AUDITOR`)
- `http://127.0.0.1:3000/projects/:projectId/export-candidates` (export candidate snapshots)
- `http://127.0.0.1:3000/projects/:projectId/export-requests` (request history and receipt read state)
- `http://127.0.0.1:3000/projects/:projectId/export-review` (review queue and decisions)
- `http://127.0.0.1:3000/admin/security` (`ADMIN` and read-only `AUDITOR`)

## Containerized Smoke Path

Run the full smoke stack (`db`, `api`, `web`):

```bash
make dev-stack-up
```

Stop it:

```bash
make dev-stack-down
```

## Verification Commands

API:

```bash
curl -sS http://127.0.0.1:8000/healthz
curl -sS -o /tmp/readyz.json -w "%{http_code}\n" http://127.0.0.1:8000/readyz
cat /tmp/readyz.json
```

Quality gates:

```bash
make ci
pnpm build:web
make smoke-health
```

Auth checks:

```bash
# unauthenticated protected API route should reject
curl -i http://127.0.0.1:8000/projects

# authenticated project members route contract (replace <session_token> and <project_id>)
curl -sS -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/projects
curl -sS -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/projects/<project_id>
curl -sS -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/projects/<project_id>/members
```

Audit checks:

```bash
# admin/auditor audit list and integrity check
curl -sS -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/admin/audit-events
curl -sS -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/admin/audit-integrity

# current user activity feed
curl -sS -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/me/activity

# verify request-id correlation passthrough
curl -i -H "X-Request-ID: local-check-0001" http://127.0.0.1:8000/healthz
```

Jobs checks:

```bash
# project job list and summary
curl -sS -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/projects/<project_id>/jobs
curl -sS -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/projects/<project_id>/jobs/summary

# enqueue NOOP test job
curl -sS -X POST -H "Authorization: Bearer <session_token>" -H "Content-Type: application/json" \
  http://127.0.0.1:8000/projects/<project_id>/jobs \
  -d '{"logical_key":"local-noop","mode":"SUCCESS","max_attempts":1,"delay_ms":0}'

# run one worker pass and inspect status
ukde-worker run-once
curl -sS -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/projects/<project_id>/jobs/<job_id>/status
curl -sS -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/projects/<project_id>/jobs/<job_id>/events
```

Operations checks:

```bash
# admin operations overview / SLO / alerts
curl -sS -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/admin/operations/overview
curl -sS -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/admin/operations/slos
curl -sS -H "Authorization: Bearer <session_token>" "http://127.0.0.1:8000/admin/operations/alerts?state=OPEN"

# admin or auditor read-only timelines
curl -sS -H "Authorization: Bearer <session_token>" "http://127.0.0.1:8000/admin/operations/timelines?scope=all"

# trace propagation baseline on API
curl -i -H "traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-1111111111111111-01" http://127.0.0.1:8000/healthz
```

Security baseline checks:

```bash
# headers baseline
curl -i http://127.0.0.1:8000/healthz

# admin or auditor security status
curl -sS -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/admin/security/status

# export routes are active but egress remains gateway-only
curl -i -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/projects/<project_id>/export-candidates
curl -i -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/projects/<project_id>/export-requests
curl -i -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/projects/<project_id>/export-review
curl -i -H "Authorization: Bearer <session_token>" http://127.0.0.1:8000/projects/<project_id>/export-requests/<request_id>/receipt

# quick auth rate-limit smoke (expect one 429 with low limits in dedicated test env)
for i in 1 2 3; do curl -s -o /tmp/auth-rate-$i.json -w "%{http_code}\n" http://127.0.0.1:8000/auth/providers; done
```

## Shutdown

Stop Postgres and supporting containers:

```bash
make dev-db-down
```

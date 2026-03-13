# Deployment Runbook (Security Baseline)

## Scope

Deploy UKDE with Phase 0.5 secure defaults:

- deny-by-default egress policies rendered in Helm
- export gateway disabled stubs active
- security headers and rate limiting active
- admin security status endpoint available

## Pre-Deploy Checks

From repo root:

```bash
make render-manifests
pnpm test
.venv/bin/python -m pytest api/tests
```

Validate model posture for target environment variables:

```bash
.venv/bin/python -c "from app.core.config import get_settings; from app.core.model_stack import validate_model_stack; s=get_settings(); r=validate_model_stack(s); print(r.status, r.detail)"
```

If target is `staging` or `prod`, deployment must be blocked unless status is `ok`.

## Helm Render/Apply

Render with target values:

```bash
docker run --rm -v "$PWD/infra/helm/ukde:/chart" alpine/helm:3.17.3 \
  template ukde /chart -f /chart/values.yaml -f /chart/values-staging.yaml
```

Apply with your cluster tooling (example):

```bash
helm upgrade --install ukde infra/helm/ukde \
  -f infra/helm/ukde/values.yaml \
  -f infra/helm/ukde/values-staging.yaml
```

## Post-Deploy Verification

1. API hardening headers:

```bash
curl -i https://<api-host>/healthz
```

Confirm:

- `Content-Security-Policy` (or `Content-Security-Policy-Report-Only`)
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy`
- `Permissions-Policy`

2. Security status route:

```bash
curl -sS -H "Authorization: Bearer <admin_or_auditor_token>" \
  https://<api-host>/admin/security/status
```

3. Export stubs stay disabled:

```bash
curl -i -H "Authorization: Bearer <member_token>" \
  https://<api-host>/projects/<project_id>/export-candidates
```

Expected: `501` + `EXPORT_GATEWAY_DISABLED_PHASE0`.

4. Egress deny-by-default policy exists:

```bash
kubectl get networkpolicy -n <namespace> | grep -E "default-deny-egress|allow-internal-egress"
```

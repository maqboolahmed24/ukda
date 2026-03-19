# Key Rotation Runbook

## Scope

Rotate authentication/session and service secrets without weakening auditability.

## Keys Covered In Phase 0.5

- `AUTH_SESSION_SECRET`
- `OIDC_CLIENT_SECRET`
- `OPENAI_API_KEY` (internal-only model/service credential)
- any environment-specific API tokens used by internal services

## Rotation Procedure

1. Generate replacement secret material in your secret manager.
2. Update target environment secret values (staging first, then prod).
3. Roll deployments:

```bash
helm upgrade --install ukde infra/helm/ukde \
  -f infra/helm/ukde/values.yaml \
  -f infra/helm/ukde/values-staging.yaml
```

4. Invalidate existing sessions by restarting API pods after `AUTH_SESSION_SECRET` change.
5. Verify auth and security posture:

```bash
curl -sS https://<api-host>/healthz
curl -sS -H "Authorization: Bearer <admin_token>" https://<api-host>/admin/security/status
curl -sS -H "Authorization: Bearer <admin_token>" https://<api-host>/admin/security/findings
```

6. Confirm high/critical findings are either `RESOLVED` or actively risk-accepted:

```bash
curl -sS -H "Authorization: Bearer <admin_token>" \
  "https://<api-host>/admin/security/risk-acceptances?status=ACTIVE"
```

7. Confirm audit continuity on new requests in `/admin/audit`.

## Rollback

If authentication is broken after rotation:

1. Revert to previous secret version in secret manager.
2. Redeploy API.
3. Validate `/auth/providers` and `/auth/session` flow.
4. Open incident review and capture root cause before retrying rotation.

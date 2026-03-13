# Infrastructure Skeleton

Prompt 03 extends the original skeleton with a minimal Helm chart and delivery wiring for internal previews plus `dev`, `staging`, and `prod`.

## Boundaries

- Containerization notes remain under [`/infra/docker`](./docker).
- Environment overlays remain under [`/infra/environments`](./environments).
- Helm deployment skeleton lives under [`/infra/helm/ukde`](./helm/ukde).
- Model stack bootstrap files live under [`/infra/models`](./models).
- Runtime definitions must preserve no-egress, internal-only model execution, and single-export-gateway posture.

## What Exists Now

- Renderable Helm values for `preview`, `dev`, `staging`, and `prod`
- Internal preview namespace convention: `ukde-pr-<number>`
- Service wiring for `web`, `api`, and `workers`
- Starter model catalog and internal service map for Phase 0.1 runtime validation
- NetworkPolicy templates for Phase 0.5 deny-by-default egress posture (`default-deny-egress` + internal allowlist overlay)

This is intentionally only a deployment skeleton. It does not provision clusters, secrets, or external infrastructure.

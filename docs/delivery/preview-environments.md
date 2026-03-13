# Preview Environments

Preview environments exist only to validate web-first delivery inside an internal dev-class posture. They are not a public preview tier and they do not weaken governance.

## Trigger Model

- Apply the `internal-preview` label to a pull request to request a preview deployment.
- Remove the label or close the pull request to trigger cleanup.
- Manual override is available through [`/.github/workflows/deploy-preview.yml`](../../.github/workflows/deploy-preview.yml) via `workflow_dispatch`.

## Naming Convention

- Helm release: `ukde-pr-<number>`
- Kubernetes namespace: `ukde-pr-<number>`
- Preview values file: [`infra/helm/ukde/values-preview.yaml`](../../infra/helm/ukde/values-preview.yaml)

This keeps previews isolated, predictable, and easy to clean up.

## Environment Differences

- `preview`: internal dev-class deployment for a labeled PR; ephemeral and isolated by namespace.
- `dev`: persistent internal development baseline.
- `staging`: gated internal pre-production environment.
- `prod`: hardened internal production environment.

The difference is operational rigor and persistence, not governance tier. Preview remains governed like `dev`.

## Required Runner Capabilities

Preview and environment deploy jobs expect an internal self-hosted runner with:

- Docker access where image operations are required
- `helm`
- `kubectl`
- network access to the internal registry and cluster

## Cleanup Strategy

- On PR close or `internal-preview` label removal, the workflow uninstalls the Helm release and deletes the namespace.
- If cleanup cannot reach the cluster, the workflow fails visibly instead of silently leaking stale previews.

## Render And Validate Locally

Use the Dockerized Helm fallback:

```bash
make render-manifests
```

This renders preview, dev, staging, and prod values without requiring a local Helm installation.

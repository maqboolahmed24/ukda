# Frontend Cache And Optimistic-State Policy (Prompt 19)

> Status: Active baseline
> Scope: Query cache classes, retry behavior, invalidation policy, and optimistic-state constraints

This policy governs frontend data freshness and mutation behavior for current routes.

## Cache Class Registry

Cache classes are defined in:

- `web/lib/data/cache-policy.ts`

Current classes:

- `auth-critical`: session/RBAC truth, network-only, no optimistic behavior.
- `governance-event`: audit/security/governance reads, network-only.
- `mutable-list`: project/jobs lists and member-driven views, network-only with explicit post-mutation revalidation.
- `operations-live`: operational telemetry and job status polling, network-only with short poll windows when needed.
- `public-status`: health/readiness diagnostics, network-only.

Phase 0/1 default posture is conservative: authenticated and governance-sensitive reads are `no-store` to avoid stale RBAC or compliance state.

## Freshness And Polling

- Live operational/status surfaces use explicit polling (`operations-live` class).
- Mutable route lists rely on immediate server reads and explicit revalidation after successful writes.
- Append-only detail surfaces still favor exact server truth in current phase rather than speculative client caching.

## Mutation And Invalidation

Mutation rules are defined in:

- `web/lib/data/mutation-rules.ts`

Revalidation helper:

- `web/lib/data/invalidation.ts`

After successful mutation, route handlers call `revalidateAfterMutation(...)` with route-specific context.

## Optimistic-State Rules

Global rule: pessimistic by default.

Never optimistic for:

- auth/session truth
- RBAC truth
- audit/security/governance records
- job terminal state truth
- destructive or compliance-sensitive mutations

Current governed mutations all use `optimism: none`.

If future low-risk optimistic behavior is added, it must be:

- reversible
- rollback-tested
- isolated from governance-sensitive entities

## Retry Model

- Read requests may be retried only when error normalization marks them retryable (`NETWORK`/`SERVER` on `GET`).
- Mutations are not auto-retried by the data layer.
- Error normalization preserves actionable `detail` strings from backend responses.

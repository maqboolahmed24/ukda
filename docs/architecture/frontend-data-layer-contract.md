# Frontend Data Layer Contract (Prompt 19)

> Status: Active baseline
> Scope: Typed frontend contracts, shared API client, query-key ownership, and mutation integration

This document defines the canonical frontend data layer for the web app.

## Canonical Contract Source

- Shared DTO and response contracts live in `packages/contracts/src/index.ts`.
- Web route code must consume those types through `web/lib/**` data modules.
- Route files should not introduce local duplicate API DTOs.

## One Typed API Client

The single shared client is:

- `web/lib/data/api-client.ts`

It owns:

- typed request/response wrapping (`ApiResult<T>`)
- consistent error normalization (`ApiError` + code mapping)
- centralized origin resolution through `resolveApiOrigins()`
- server auth token attachment via cookie session token
- optional browser-safe requests for client pollers
- optional accepted non-2xx route statuses (for example readiness `503`)
- request-level correlation header propagation on server requests

Domain modules (`web/lib/projects.ts`, `web/lib/jobs.ts`, `web/lib/audit.ts`, `web/lib/security.ts`, `web/lib/operations.ts`, `web/lib/exports.ts`, `web/lib/system.ts`) must call this client and remain thin typed adapters.

## Query-Key Ownership

The canonical query-key factory is:

- `web/lib/data/query-keys.ts`

Rules:

- each route family has an explicit key namespace (`auth`, `projects`, `jobs`, `audit`, `operations`, `security`, `exports`, `system`)
- key filters are normalized to stable nullable values
- project-scoped activity keys remain distinct from admin audit and current-user activity keys
- new endpoints must add a query key before adding fetch helpers

## Mutation Pattern

Mutation policy and invalidation ownership:

- `web/lib/data/mutation-rules.ts`
- `web/lib/data/invalidation.ts`

All governed mutations are pessimistic (`optimism: none`) and use explicit post-success revalidation in route handlers.

Current mutation-integrated routes include:

- project creation
- project membership add/change/remove
- job enqueue/retry/cancel
- auth login/logout session boundary transitions

## Server/Client Split

- Server components and route handlers use server client requests (`requestServerApi`).
- Interactive browser pollers can use `requestBrowserApi` (for example job status polling).
- Avoid duplicated route-local `fetch()` wrappers when a `web/lib` data module exists.

## Extension Rules

When adding a new endpoint:

1. Add or reuse DTO types in `packages/contracts`.
2. Add query-key factory entry in `web/lib/data/query-keys.ts`.
3. Add/extend a `web/lib` domain module using `requestServerApi` or `requestBrowserApi`.
4. Assign the correct cache class and pessimistic mutation rule.
5. Add tests for key stability and error/mutation behavior.

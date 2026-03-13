# Auth And Session Boundaries (Phase 0.2)

This document describes the Prompt 05 authentication posture for the web-first UKDE stack.

## Identity Sources

- **Primary path:** OIDC authorization-code flow with PKCE.
- **Local path:** explicit seeded dev identities (`AUTH_DEV_MODE_ENABLED=true`) for implementation and tests.
- **Safety gate:** dev auth is blocked outside `dev/test` by settings validation.

## Session Boundary

- Session state is issued by the API and persisted in Postgres (`sessions` table).
- Browser session token is stored in an `HttpOnly` cookie (`AUTH_COOKIE_NAME`, default `ukde_session`).
- CSRF token is stored in a separate cookie (`AUTH_CSRF_COOKIE_NAME`, default `ukde_csrf`).
- Cookie flags:
  - `HttpOnly` for session token
  - `SameSite=Lax`
  - `Secure=true` for `staging/prod`, `false` for local `dev/test`
- Session token is signed server-side and validated on every protected request.
- Logout revokes the session in persistence and clears browser cookies.

## Persistence Foundations

- `users` table:
  - `id`
  - `oidc_sub`
  - `email`
  - `display_name`
  - `created_at`
  - `last_login_at`
- `user_platform_roles` table:
  - `user_id`
  - `role` (`ADMIN` | `AUDITOR`)
- `sessions` table:
  - `id`
  - `user_id`
  - `auth_method` (`dev` | `oidc`)
  - `issued_at`
  - `expires_at`
  - `csrf_token`
  - `revoked_at`

## Route Protection

- Public routes:
  - `/healthz`
  - `/readyz`
  - auth handshake routes (`/auth/providers`, `/auth/oidc/*`, `/auth/dev/login`)
- Protected API routes fail closed (`401` without a valid session).
- Admin API routes require explicit platform-role guards (`ADMIN`/`AUDITOR` only where declared).
- Web guards are server-side:
  - `/` resolves to `/login` (unauthenticated) or `/projects` (authenticated)
  - `/projects` is protected
  - `/admin` surfaces require platform role

## Web Flow Summary

1. User starts at `/login`.
2. OIDC path:

- web route `/auth/login` creates PKCE/state/nonce
- API returns OIDC authorization URL
- IdP redirects to `/auth/callback`
- callback exchanges code through API and receives UKDE session issuance payload

3. Dev path:

- `/auth/dev-login` posts selected seed to API and receives session issuance payload

4. Session cookies are set by web route handlers.
5. Protected pages resolve current user via API `/auth/session` using bearer forwarding.
6. Sign-out is confirmed at `/logout` and finalized via `/auth/logout`.

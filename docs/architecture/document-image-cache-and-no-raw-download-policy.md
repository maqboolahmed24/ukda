# Document Image Cache And No-Raw-Download Policy

> Status: Active (Prompt 27)
> Scope: Browser-safe caching and controlled-storage enforcement for derived page assets

This policy defines cache behavior for page images and thumbnails and codifies the no-raw-original guarantee.

## Cache Policy

Derived page assets use:

- `Cache-Control: private, no-cache, max-age=0, must-revalidate`
- `ETag` validators sourced from page-record hashes
- `If-None-Match` revalidation with `304 Not Modified`

Design intent:

- Browsers may keep local copies for fast repeat navigation.
- Every request still revalidates under user-scoped auth context.
- Shared/public cache behavior is explicitly disallowed.

## Security Headers

The delivery path always emits:

- `X-Content-Type-Options: nosniff`
- `Cross-Origin-Resource-Policy: same-origin`
- `Vary: Authorization`

Normal rendering responses do not include `Content-Disposition: attachment`.

## No-Raw-Download Guarantee

The system does not provide a browser endpoint for raw original source bytes.

Rules:

- No `/documents/{documentId}/original` route is exposed.
- No raw object-storage key is returned to browser clients.
- No signed/public object URL bypass is introduced.
- No legacy debug/raw route bypass is kept active.

Raw originals remain controlled internal storage artefacts and are not a user-download primitive.

## UI Recovery Contract

- Viewer and library surfaces must render explicit fallback copy when image fetches fail.
- Expired sessions and unauthorized fetches fail closed.
- Recovery follows normal auth/session renewal paths; no hidden image token is embedded in URLs.

## Validation Anchors

Current regression coverage includes:

- API image route header and ETag assertions (`api/tests/test_documents_routes.py`)
- cross-project denial for image access (`api/tests/test_documents_routes.py`)
- raw-original route absence (`api/tests/test_documents_routes.py`)
- web same-origin image proxy auth + revalidation behavior (`web/.../image/route.test.ts`)

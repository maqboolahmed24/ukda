# Document Image Delivery Contract

> Status: Active (Prompt 34)
> Scope: Canonical authenticated page-image, preprocess-variant delivery, and variant-availability metadata

This contract defines the only supported browser path for derived page-image bytes.
It applies to full-size page images and thumbnails.

## Canonical Paths

- Browser-facing path:
  - `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}/image?variant={variant}&runId={runId}`
- Variant metadata path:
  - `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}/variants?runId={runId}`
- Browser helper:
  - `projectDocumentPageImagePath(projectId, documentId, pageId, variant)`
- Web route implementation:
  - `web/app/(authenticated)/projects/[projectId]/documents/[documentId]/pages/[pageId]/image/route.ts`
- API delivery endpoint:
  - `api/app/api/routes/documents.py` image route for the same URL contract

Rules:

- A single same-origin authenticated delivery path is used by both the viewer canvas and the document-library thumbnail preview.
- Route handlers never expose raw storage keys, raw bucket URLs, or public object URLs.
- Project membership RBAC is enforced before image bytes are returned.

## Header Contract

Successful image responses and `304` revalidation responses use:

- `Cache-Control: private, no-cache, max-age=0, must-revalidate`
- `ETag: "<page-hash>"`
- `X-Content-Type-Options: nosniff`
- `Cross-Origin-Resource-Policy: same-origin`
- `Vary: Authorization`

Additional rules:

- No `Content-Disposition: attachment` is returned for viewer/library image rendering.
- Content type stays variant-specific:
  - `full` -> `image/png`
  - `thumb` -> `image/jpeg`
  - `preprocessed_gray` -> `image/png`
  - `preprocessed_bin` -> `image/png`

## Conditional Revalidation Contract

- API and same-origin web proxy support `If-None-Match`.
- ETag seeds are sourced from page metadata hashes:
  - full image -> `derived_image_sha256`
  - thumbnail -> `thumbnail_sha256`
- Matching validator returns `304 Not Modified` with the same security/cache headers.

## Variant Resolution And Failure Behavior

- Supported image variants:
  - `full`
  - `thumb`
  - `preprocessed_gray`
  - `preprocessed_bin`
- `runId` handling:
  - if provided, preprocess variants resolve against that run
  - if omitted for preprocess variants, active preprocess projection is required
  - if no active run exists and no run is provided, request fails closed
- `/pages/{pageId}/variants` returns availability and page-scoped metrics/warnings for the resolved run context.

## Failure And Re-Auth Behavior

- Missing browser session token at the proxy route returns `401` and no bytes.
- Cross-project or non-member access returns `403`.
- Missing page/document returns `404`.
- Not-ready variant assets return `409`.
- Viewer/library image surfaces fail closed and switch to explicit state copy when image loads fail (including session-expiry paths).

## Reuse Rule

Future derived image-like artefacts must reuse this contract:

- same canonical helper path pattern
- same RBAC and same-origin proxy posture
- same cache/security header baseline
- no raw-original bypass
- variant reads remain auditable (`PREPROCESS_VARIANT_ACCESSED` for preprocess variants)

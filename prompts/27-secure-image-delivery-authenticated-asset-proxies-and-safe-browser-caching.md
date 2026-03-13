You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed phase files before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first on each run.

## Mandatory first actions
1. Inspect the relevant repository areas and any existing implementation this prompt may extend.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-01-ingest-document-viewer-v1.md`
3. Then review the current repository generally — page image endpoints, storage adapters, auth/session code, asset delivery paths, caching headers, viewer integrations, tests, CI/browser regression setup, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second asset-delivery path, a second proxy layer, or conflicting cache/header rules.

## Source-of-truth hierarchy
Use this precedence order when implementing:
1. The specific `/phases` files listed in this prompt for product behavior and acceptance logic.
2. `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md` when this prompt depends on web-first execution semantics.
3. `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` when this prompt depends on recall-first, rescue, token-anchor, search-anchoring, or conservative-masking semantics.
4. `/phases/blueprint-ukdataextraction.md`, `/phases/README.md`, and `/phases/ui-premium-dark-blueprint-obsidian-folio.md` as supporting product context when they are listed or clearly relevant.
5. This prompt for task scope and deliverables.
6. Current repository state for reconciling implementation details.
7. Official external docs for implementation mechanics only.

Treat current repository state as implementation context, not as the primary source of product truth.

## Conflict-resolution rule
- `/phases` wins for controlled-storage posture, authenticated asset delivery, no-raw-download rules, viewer access boundaries, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the controlled environment. Do not introduce public object URLs, presigned download shortcuts, or any raw original bypass.

## Objective
Secure image delivery with authenticated asset proxies, no raw-download paths, and safe browser caching rules.

This prompt owns:
- hardening the canonical authenticated asset-delivery path
- same-origin or equivalent internal proxy delivery for page images and thumbnails
- secure response-header and caching behavior
- safe browser image loading without leaking storage topology
- raw-original path denial
- re-auth and session-expiry behavior for asset fetches
- viewer/library integration with the hardened asset path

This prompt does not own:
- viewer feature ergonomics
- public CDN delivery
- raw original delivery
- export or release-pack behavior
- later-phase derived artefact families beyond page full/thumb variants

## Phase alignment you must preserve
From Phase 1 Iteration 1.3:

### Canonical target page/image API contract
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}/image?variant={variant}`
  - `variant=full|thumb`

Rules:
- serve page assets through authenticated streaming or same-origin asset proxy endpoints
- no raw original download endpoint
- page metadata and failure state come from the page metadata API, not from guessing based on image reads

### Required integration gate
- asset proxy re-auth or token refresh path works

### Required security posture
- all routes are protected by project RBAC
- no direct export or raw-download bypass introduced

## Implementation scope

### 1. Canonical authenticated asset-delivery path
Implement or refine one canonical delivery path for page assets.

Requirements:
- full-size page image delivery
- thumbnail delivery
- same-origin browser-safe access
- RBAC-protected by project membership
- asset delivery does not expose raw storage keys or raw bucket URLs
- one consistent path only

Use the pattern that best suits the repository:
- API streaming endpoint
- same-origin internal proxy
- or an equivalent controlled authenticated delivery path
Do not leave multiple inconsistent image-delivery strategies alive.

### 2. Response headers and browser-safe behavior
Harden response behavior.

Requirements:
- correct content type for full images and thumbnails
- `X-Content-Type-Options: nosniff`
- no `Content-Disposition: attachment` for normal viewer/library image rendering
- safe caching headers
- safe conditional request support if appropriate
- do not leak internal storage paths in response bodies, redirects, or error payloads

If ETag or checksum-based validation is already available from the page records, reuse it for conditional requests (`If-None-Match` -> `304`) instead of introducing a second validator scheme.

### 3. Safe caching rules
Implement explicit caching behavior.

Requirements:
- browser caching improves repeat document browsing without weakening access control
- cache policy is private/user-scoped, not public
- full-size page caching and thumbnail caching can differ if useful
- stale auth/session must not produce a silent unauthorized leak
- the cache contract is documented and testable

Keep the rules conservative and understandable.
Do not invent complex CDN semantics the repo does not need.

### 4. Re-auth and expired-session behavior
Handle asset fetch failures with deterministic recovery behavior.

Requirements:
- viewer and library do not collapse into misleading broken-image chaos on expired auth
- unauthorized asset fetches fail closed
- the app can recover through the repo's existing auth/session path
- where the current architecture supports it, re-auth or route-level recovery is consistent
- no hidden bypass token is embedded in asset URLs

### 5. No-raw-download enforcement
Harden the no-raw-original posture end to end.

Requirements:
- no raw original file browser endpoint
- no storage-key leakage that lets a caller reconstruct a direct path
- no accidental attachment download controls for originals
- no debug route or legacy route bypass
- if legacy/raw endpoints exist, remove them or hard-fail them safely

### 6. Library and viewer integration
Refine the consuming UI surfaces.

Requirements:
- document library thumbnails use the canonical safe asset path
- viewer canvas uses the canonical safe asset path
- missing/unauthorized assets surface clear UI states
- image loading behavior integrates with shared loading/error states
- no ad hoc image-loading utilities remain where they duplicate the canonical path

### 7. Auditing and privacy-safe observability alignment
Use the current repo's existing audit/telemetry path where present.

Requirements:
- asset reads may emit sampled view telemetry or audit according to the current repo contract
- do not log raw storage paths, signed URLs, or sensitive cookies/tokens
- error logs remain privacy-safe

Do not create a second audit or telemetry path.

### 8. Documentation
Document:
- the canonical image-delivery path
- response-header and caching rules
- re-auth/error behavior
- the explicit no-raw-original guarantee
- what later work must reuse for any derived image-like artefacts

## Required deliverables

### Backend / delivery layer
- hardened authenticated full/thumb image delivery
- secure headers
- cache policy
- tests

### Web
- viewer and library integration with the canonical asset path
- safe unauthorized/missing/failure image states

### Docs
- authenticated asset-delivery contract doc
- caching and no-raw-download policy doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/api/**`
- storage adapters/config used by the repo
- `/web/**`
- `/packages/contracts/**` only if small shared asset-response contracts help
- `/packages/ui/**` only if small loading/error image-surface refinements are needed
- root config/task files
- `README.md`
- `docs/**`
- `infra/**` only if a small internal delivery config adjustment is needed

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- raw original delivery
- public image URLs
- public CDN integration
- export/release-pack delivery
- feature work unrelated to authenticated image transport
- a second proxy layer

## Testing and validation
Before finishing:
1. Verify full and thumbnail image endpoints remain RBAC-protected.
2. Verify unauthorized and cross-project access are denied.
3. Verify no raw storage keys or public URLs leak to the browser.
4. Verify response headers are correct and safe.
5. Verify the cache policy is private and consistent.
6. Verify expired-session or unauthorized asset fetches fail closed and surface safely in the app.
7. Verify library thumbnails and viewer pages use the canonical path.
8. Verify no raw original download path exists.
9. Verify docs match the actual delivery and caching behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- one hardened authenticated asset-delivery path exists
- library and viewer both use it
- no raw original or public asset bypass exists
- cache behavior is explicitly defined via `Cache-Control` and validator headers, with tests for auth expiry and revalidation paths
- auth expiry and errors are handled safely
- the controlled secure-environment posture is preserved
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

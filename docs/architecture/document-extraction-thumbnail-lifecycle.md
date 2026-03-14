# Document Extraction And Thumbnail Lifecycle

> Status: Active baseline (Prompt 24)
> Scope: Derived page assets, thumbnail assets, processing lineage, and authenticated delivery

This document defines how imported sources transition from accepted scan state into viewer-usable page assets.

## Lifecycle Overview

1. Upload and scan complete (`document_imports` projection).
2. `EXTRACT_PAGES(document_id)` is enqueued in canonical `jobs`.
3. Worker claims extraction job and appends a `document_processing_runs` row (`run_kind=EXTRACTION`).
4. Extraction resolves source metadata and writes derived page PNGs.
5. `pages` rows are replaced deterministically and `documents.page_count` is synchronized.
6. On extraction success, worker enqueues `RENDER_THUMBNAILS(document_id)`.
7. Worker appends thumbnail run (`run_kind=THUMBNAIL_RENDER`) and writes derived JPEG thumbnails.
8. Pages transition to `READY`; document transitions to `READY`.

Failure behavior:

- Failed extraction or thumbnail attempts remain explicit via run status and failure reason.
- Document projection transitions to `FAILED` for terminal pipeline failure.

## Source-Type Handling

Current baseline support:

- `application/pdf`
- `image/tiff` (multi-frame counted)
- `image/png`
- `image/jpeg`

Page metadata (`page_count`, dimensions, DPI) is derived before page-row materialization.

## Derived Storage Layout

All derived assets remain in Controlled storage:

- Full pages: `controlled/derived/{project_id}/{document_id}/pages/{page_index}.png`
- Thumbnails: `controlled/derived/{project_id}/{document_id}/thumbs/{page_index}.jpg`

Raw originals remain in:

- `controlled/raw/{project_id}/{document_id}/original.bin`

No public object-storage URLs are exposed.

## Jobs And Processing-Run Responsibilities

- `jobs`: queueing, claiming, leasing, retries/cancel orchestration primitives.
- `document_processing_runs`: document-scoped append-only historical attempts.

This separation ensures document timelines remain stable even as worker orchestration evolves.

## Page APIs

- `GET /projects/{projectId}/documents/{documentId}/pages`
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}`
- `PATCH /projects/{projectId}/documents/{documentId}/pages/{pageId}`
- `GET /projects/{projectId}/documents/{documentId}/pages/{pageId}/image?variant=full|thumb`

Rules:

- Viewer status and failure handling come from page metadata APIs.
- Image bytes are streamed from authenticated endpoints only.
- No route exposes raw-original bytes.

## Timeline Contract

`GET /projects/{projectId}/documents/{documentId}/timeline` reads append-only `document_processing_runs` and includes:

- `runKind`
- `status`
- `createdAt`
- `startedAt`
- `finishedAt`
- `failureReason`
- cancellation fields when present

## Audit Coverage

- `DOCUMENT_PAGE_EXTRACTION_STARTED`
- `DOCUMENT_PAGE_EXTRACTION_COMPLETED`
- `DOCUMENT_PAGE_EXTRACTION_FAILED`
- `PAGE_METADATA_VIEWED`
- `PAGE_IMAGE_VIEWED`
- `PAGE_THUMBNAIL_VIEWED`

## Deferred Work

- Rich extraction retries with supersession UX.
- Per-user viewer-state table (`page_viewer_preferences`) beyond shared page metadata rotation.
- Shareable multi-parameter viewer URL-state restoration beyond `page`.
- Advanced viewer polish beyond the current zoom/pan/rotate and filmstrip baseline.

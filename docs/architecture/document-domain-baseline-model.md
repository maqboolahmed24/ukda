# Document Domain Baseline Model

> Status: Active baseline and Prompt 30 hardening (Prompts 21-30)
> Scope: Document records, resumable import attempts, append-only processing runs, and page projections

This document captures the current persistence contract for document ingest and page-derivative lifecycles.

## Canonical Tables

## `documents`

Current projection for each project document:

- `id` (PK)
- `project_id` (FK -> `projects.id`)
- `original_filename`
- `stored_filename` (nullable until controlled storage write is finalized)
- `content_type_detected` (nullable)
- `bytes` (nullable)
- `sha256` (nullable)
- `page_count` (nullable)
- `status`:
  - `UPLOADING`
  - `QUEUED`
  - `SCANNING`
  - `EXTRACTING`
  - `READY`
  - `FAILED`
  - `CANCELED`
- `created_by` (FK -> `users.id`)
- `created_at`
- `updated_at`

## `document_imports`

Import-attempt projection used by upload wizard and status polling:

- `id` (PK)
- `document_id` (FK -> `documents.id`)
- `status`:
  - `UPLOADING`
  - `QUEUED`
  - `SCANNING`
  - `ACCEPTED`
  - `REJECTED`
  - `FAILED`
  - `CANCELED`
- `failure_reason` (nullable)
- `created_by` (FK -> `users.id`)
- `accepted_at` (nullable)
- `rejected_at` (nullable)
- `canceled_by` (nullable FK -> `users.id`)
- `canceled_at` (nullable)
- `created_at`
- `updated_at`

## `document_processing_runs`

Append-only document-scoped attempt lineage:

- `id` (PK)
- `document_id` (FK -> `documents.id`)
- `attempt_number` (integer, starts at `1`, increments for same `document_id + run_kind` lineage)
- `run_kind`:
  - `UPLOAD`
  - `SCAN`
  - `EXTRACTION`
  - `THUMBNAIL_RENDER`
- `supersedes_processing_run_id` (nullable FK -> `document_processing_runs.id`)
- `superseded_by_processing_run_id` (nullable FK -> `document_processing_runs.id`)
- `status`:
  - `QUEUED`
  - `RUNNING`
  - `SUCCEEDED`
  - `FAILED`
  - `CANCELED`
- `created_by` (FK -> `users.id`)
- `created_at`
- `started_at` (nullable)
- `finished_at` (nullable)
- `canceled_by` (nullable FK -> `users.id`)
- `canceled_at` (nullable)
- `failure_reason` (nullable)

Rules:

- Upload, scan, extraction, and thumbnail attempts append rows.
- Retry extraction creates a new `EXTRACTION` row, increments `attempt_number`, and links both:
  - backward via `supersedes_processing_run_id`
  - forward on the superseded run via `superseded_by_processing_run_id`
- Retry lineage rejects non-extraction supersede targets.
- `documents.status` remains a projection, not historical truth.
- Document timeline reads `document_processing_runs`.

## `document_upload_sessions`

Resumable upload-session projection:

- `id` (PK)
- `project_id` (FK -> `projects.id`)
- `document_id` (FK -> `documents.id`)
- `import_id` (FK -> `document_imports.id`)
- `original_filename`
- `status`:
  - `ACTIVE`
  - `ASSEMBLING`
  - `FAILED`
  - `CANCELED`
  - `COMPLETED`
- `expected_sha256` (nullable)
- `expected_total_bytes` (nullable)
- `bytes_received`
- `last_chunk_index` (`-1` means no acknowledged chunks)
- `created_by` (FK -> `users.id`)
- `created_at`
- `updated_at`
- `completed_at` (nullable)
- `canceled_at` (nullable)
- `failure_reason` (nullable)

Rules:

- Sessions remain project-scoped and server-controlled.
- Sessions can be resumed from `last_chunk_index + 1` only.
- Completion assembles chunks into the canonical immutable `original.bin`.

## `document_upload_session_chunks`

Chunk-level session ledger:

- `session_id` (FK -> `document_upload_sessions.id`)
- `chunk_index` (non-negative integer)
- `byte_length`
- `sha256`
- `created_at`
- primary key: `(session_id, chunk_index)`

Rules:

- Chunk writes are immutable per `(session_id, chunk_index)`.
- Replayed chunk index is idempotent only when payload digest matches.

## `pages`

Derived-page projection for viewer and later phase inputs:

- `id` (PK)
- `document_id` (FK -> `documents.id`)
- `page_index` (0-based, unique per document)
- `width`
- `height`
- `dpi` (nullable)
- `status`:
  - `PENDING`
  - `READY`
  - `FAILED`
  - `CANCELED`
- `derived_image_key` (nullable)
- `derived_image_sha256` (nullable)
- `thumbnail_key` (nullable)
- `thumbnail_sha256` (nullable)
- `failure_reason` (nullable)
- `canceled_by` (nullable FK -> `users.id`)
- `canceled_at` (nullable)
- `viewer_rotation` (default `0`)
- `created_at`
- `updated_at`

Rules:

- Extraction writes page rows and full-size derived keys/checksums.
- Thumbnail rendering updates thumbnail keys/checksums and page readiness.
- Page metadata drives viewer state; image presence is not treated as the source of truth.

## Jobs vs Processing Runs

- Generic `jobs` queue (`EXTRACT_PAGES`, `RENDER_THUMBNAILS`) owns execution orchestration.
- `document_processing_runs` owns document-scoped append-only attempt lineage.
- These systems coexist with separate responsibilities.

## Shared Type Contracts

`packages/contracts` exports:

- `DocumentStatus`
- `DocumentImportStatus`
- `DocumentProcessingRunKind`
- `DocumentProcessingRunStatus`
- `DocumentUploadSessionStatus`
- `DocumentPageStatus`
- `ProjectDocument`
- `DocumentTimelineResponse`
- `DocumentProcessingRunDetailResponse`
- `DocumentProcessingRunStatusResponse`
- `CreateDocumentUploadSessionRequest`
- `ProjectDocumentUploadSessionStatus`
- `ProjectDocumentPage`
- `ProjectDocumentPageDetail`

## Security Constraints

- Project membership is required for all document and page reads.
- Page images are streamed through authenticated endpoints.
- No direct raw-original download route is exposed.

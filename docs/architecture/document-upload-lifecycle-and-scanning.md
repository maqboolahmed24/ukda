# Document Upload Lifecycle And Scanning

> Status: Active baseline and Prompt 30 hardening (Prompts 23-30)
> Scope: Controlled upload wizard, resumable-session upload path, scanner boundary, extraction handoff, and cancellation rules

This document defines the active upload lifecycle for project-scoped document imports.
It extends the Phase 1 ingest baseline by replacing the import placeholder route with a real upload pipeline.

## Routes

### Browser route

- `/projects/:projectId/documents/import`

Wizard steps:

1. Select file.
2. Confirm metadata and destination project.
3. Upload and status.

Rules:

- Dedicated route, not modal.
- Primary action is `Upload`.
- Secondary action is `Cancel`.
- Upload is session-backed and resumable from the last acknowledged chunk.
- Once scan status is reached, the wizard becomes read-only.
- Successful scan handoff navigates to `/projects/:projectId/documents/:documentId`.

### API routes

- `POST /projects/{projectId}/documents/import-sessions`
- `GET /projects/{projectId}/documents/import-sessions/{sessionId}`
- `POST /projects/{projectId}/documents/import-sessions/{sessionId}/chunks?chunkIndex={chunkIndex}`
- `POST /projects/{projectId}/documents/import-sessions/{sessionId}/complete`
- `POST /projects/{projectId}/documents/import-sessions/{sessionId}/cancel`
- legacy direct upload path remains available:
  - `POST /projects/{projectId}/documents/import`
- `GET /projects/{projectId}/document-imports/{importId}`
- `POST /projects/{projectId}/document-imports/{importId}/cancel`
- extraction retry path:
  - `POST /projects/{projectId}/documents/{documentId}/retry-extraction`

## Status model

### Import status (`document_imports.status`)

- `UPLOADING`
- `QUEUED`
- `SCANNING`
- `ACCEPTED`
- `REJECTED`
- `FAILED`
- `CANCELED`

### Document status (`documents.status`)

- `UPLOADING`
- `QUEUED`
- `SCANNING`
- `EXTRACTING`
- `READY`
- `FAILED`
- `CANCELED`

### Active progression and terminal outcomes

Active progression during import:

- `UPLOADING -> QUEUED -> SCANNING`

After scan pass:

- import status: `ACCEPTED`
- document status: `EXTRACTING`
- extraction job handoff: enqueue `EXTRACT_PAGES(document_id)` in the canonical jobs system
- thumbnail job handoff: enqueue `RENDER_THUMBNAILS(document_id)` after extraction success

After scan reject:

- import status: `REJECTED`
- document status: `FAILED`

After pre-scan cancellation:

- import status: `CANCELED`
- document status: `CANCELED`

Resumable-session status progression:

- `ACTIVE -> ASSEMBLING -> COMPLETED`
- `ACTIVE -> CANCELED`
- `ACTIVE|ASSEMBLING -> FAILED`

Session completion invariants:

- assemble chunks in index order into immutable controlled raw object
- enforce optional expected byte and checksum match
- enforce upload type validation and project quotas before queueing scan

## Scanner hook architecture

The scanner integration is a pluggable adapter:

- `stub` backend: deterministic local/test scanner
- `none` backend: explicit unavailable state
- `auto` backend:
  - `dev/test` resolves to `stub`
  - `staging/prod` resolves to `none` unless explicitly configured

Local deterministic behavior:

- A fixed token check (`EICAR-STANDARD-ANTIVIRUS-TEST-FILE`) rejects the sample.
- Other content passes.

If no scanner backend is available, the import fails closed with `FAILED`.

## Source record and timeline extensions

Prompt 23 adds:

- immutable raw-source sidecar support at `source-meta.json`
- explicit post-write checksum and byte verification on stored `original.bin`
- explicit timeline stage fields (`stage`, `occurredAt`, `terminal`) derived from persisted import status

For complete source-record posture, see:

- `/docs/architecture/document-source-record-and-ingest-lineage.md`

## Cancellation semantics

- Cancel is allowed only while import status is `UPLOADING` or `QUEUED`.
- `SCANNING` and all terminal states reject cancel requests with conflict semantics.
- Canceled imports do not continue into scan acceptance or extraction handoff.
- Session cancel (`/import-sessions/{sessionId}/cancel`) is allowed only for non-terminal session states and marks both import and document as canceled.

## Extraction retry semantics

- Retry is role-gated to `PROJECT_LEAD` and `ADMIN`.
- Retry target must be the latest unsuperseded extraction attempt and must be `FAILED` or `CANCELED`.
- Retry appends a new extraction processing-run attempt; historical rows remain immutable.
- Retry does not supersede or fork scan or thumbnail lineage.

## Audit events

Upload and scanning lifecycle events:

- `DOCUMENT_UPLOAD_STARTED`
- `DOCUMENT_STORED`
- `DOCUMENT_SCAN_STARTED`
- `DOCUMENT_UPLOAD_CANCELED`
- `DOCUMENT_SCAN_PASSED`
- `DOCUMENT_SCAN_REJECTED`
- `DOCUMENT_IMPORT_FAILED`

## Active downstream linkage

- Upload/scan outcomes remain projected in `document_imports` for the wizard surface.
- Append-only historical lineage for upload, scan, extraction, and thumbnail attempts is written to `document_processing_runs`.
- Page and thumbnail metadata is materialized into `pages` and consumed by document detail and viewer routes.

See also:

- `/docs/architecture/document-domain-baseline-model.md`

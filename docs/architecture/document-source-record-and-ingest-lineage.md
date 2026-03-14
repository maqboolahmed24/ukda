# Document Source Record And Ingest Lineage

> Status: Active baseline (Prompt 23)
> Scope: Immutable source capture, checksum/size integrity, and upload-scan lineage visibility

This document defines the current source-record posture for Phase 1 ingest.
It extends the upload baseline with immutable raw-source metadata and explicit timeline staging.

## Immutable source record

The canonical source record is the uploaded original payload written once to controlled raw storage.

Current object layout:

- `controlled/raw/{project_id}/{document_id}/original.bin`
- `controlled/raw/{project_id}/{document_id}/source-meta.json`

Rules:

- Storage keys are generated server-side.
- User-provided filenames are metadata only and are never used as object keys.
- `original.bin` and `source-meta.json` are write-once for a document ID.
- Later phase derivatives must use separate derived prefixes and never overwrite raw source objects.
- Browser routes do not expose raw object download paths.

## Checksum and byte integrity

During upload:

1. API streams payload to a temporary file and computes `sha256` + byte count.
2. Temporary payload is moved into controlled raw storage as `original.bin`.
3. API re-reads the stored object and verifies:
   - byte count matches expected
   - computed `sha256` matches expected
4. Only after verification does the API persist queued upload metadata to `documents` and `document_imports`.

If verification fails:

- import transitions to `FAILED`
- a safe failure reason is persisted
- API returns service-unavailable behavior for the upload attempt

## Source metadata sidecar

`source-meta.json` is written from persisted DB state after queue handoff so the sidecar remains aligned with canonical records.

Current fields:

- `schemaVersion`
- `projectId`
- `documentId`
- `importId`
- `documentStatus`
- `importStatus`
- `originalFilename`
- `storedFilename`
- `contentTypeDetected`
- `bytes`
- `sha256`
- `createdBy`
- `uploadCreatedAt`
- `uploadStoredAt`
- `documentCreatedAt`
- `documentUpdatedAt`

The sidecar is lineage support data, not a second source of truth.
Database records remain authoritative.

## Ingest timeline surface (current phase)

`GET /projects/{projectId}/documents/{documentId}/timeline` is grounded in `document_imports`.

Each timeline entry now includes:

- `status` (persisted import status)
- `stage` (explicit ingest stage label)
- `occurredAt` (status-specific timestamp)
- `terminal` (whether the status is terminal)
- `failureReason` (nullable)

Stage mapping:

- `UPLOADING -> UPLOAD_STARTED`
- `QUEUED -> UPLOAD_STORED`
- `SCANNING -> SCAN_STARTED`
- `ACCEPTED -> SCAN_PASSED`
- `REJECTED -> SCAN_REJECTED`
- `FAILED -> IMPORT_FAILED`
- `CANCELED -> IMPORT_CANCELED`

No extraction or thumbnail history is implied here.
Later prompts extend lineage with those phases once append-only processing runs are available.

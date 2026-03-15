# Screening-Safe Manifest Contract

Status: Prompt 68  
Scope: Phase 6.1 canonical screening-safe manifest bytes, entries filters, hash verification, policy lineage, and reviewer sign-off lineage

## Canonical serializer

The run-level reviewed output manifest is now serialized through one canonical path:

- `api/app/documents/redaction_preview.py`
  - `canonical_preview_manifest_payload`
  - `canonical_preview_manifest_bytes`
  - `canonical_preview_manifest_sha256`

No route handler builds ad hoc manifest JSON.

Determinism rules:

- bytes are canonical JSON (`ensure_ascii=True`, `sort_keys=True`, compact separators)
- entry ordering is deterministic by `(pageIndex, pageId, lineId, decisionTimestamp, entryId)`
- payload fields are derived only from the approved snapshot decision set plus run metadata
- repeated serialization for the same locked run yields the same bytes and SHA-256

## Manifest shape (screening-safe)

Top-level fields:

- `manifestSchemaVersion`
- `manifestKind = SCREENING_SAFE_REDACTION_MANIFEST`
- `runId`
- `approvedSnapshotSha256`
- `internalOnly = true`
- `exportApproved = false`
- `notExportApproved = true`
- `exportApprovalStatus = NOT_EXPORT_APPROVED`
- `policyLineage` (`policySnapshotHash`, optional `policyId`, `policyFamilyId`, `policyVersion`)
- `reviewLineage` (run-review + page sign-off lineage)
- `outputs` (`pageCount`, `pages[]` with `pageId` + `previewSha256`)
- `entries[]`
- `entryCount`

Per-entry fields:

- `entryId`
- `appliedAction` (`MASK`, future-compatible for `PSEUDONYMIZE` / `GENERALIZE`)
- `category`
- `pageId`, `pageIndex`, `lineId`
- `locationRef` (safe span refs and `bboxToken` hash where needed)
- `basisPrimary`
- `confidence`
- `secondaryBasisSummary` (compact screening-safe summary only)
- `finalDecisionState`
- `reviewState`
- policy lineage fields (`policySnapshotHash`, optional policy version lineage IDs)
- `decisionTimestamp`, `decisionBy`, `decisionEtag`

## Privacy boundaries

Manifest bytes and entries exclude:

- raw sensitive source text
- reviewer-visible assist explanation text
- raw storage/object keys

`secondaryBasisSummary` is intentionally compact and whitelisted. It reports counts, categories, and risk markers without copying free-text detector payloads.

## API surfaces

Governance manifest routes:

- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest/status`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest/entries?category={category}&page={page}&reviewState={reviewState}&from={from}&to={to}&cursor={cursor}&limit={limit}`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest/hash`

`manifest/hash` reports both persisted manifest hash and streamed hash validation (`hashMatches`), so callers can verify byte integrity.

## Access contract

Read roles:

- `PROJECT_LEAD`
- `REVIEWER`
- `ADMIN`
- read-only `AUDITOR`

`RESEARCHER` remains denied for governance manifest surfaces.

All manifest read surfaces are internal authenticated routes and explicitly marked `Internal-only` and `Not export-approved`.

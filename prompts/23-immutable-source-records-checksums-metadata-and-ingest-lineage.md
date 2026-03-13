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
3. Then review the current repository generally — upload/storage code, document models, import models, timeline APIs, audit code, detail pages, contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second source-record model or a second ingest-lineage path unless the current repo architecture absolutely requires a thin adapter.

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
- `/phases` wins for checksum capture, metadata ownership, controlled-storage layout, timeline semantics, audit requirements, and immutable-version posture.
- Official docs win only for implementation mechanics.
- Prefer the phase-defined `documents` + `document_imports` + controlled storage object layout over inventing extra source-record abstractions that add unnecessary complexity.

## Objective
Capture immutable source records, checksums, metadata, and ingest lineage for every uploaded document.

This prompt owns:
- streaming or final checksum correctness
- immutable source-record posture for uploaded originals
- controlled raw-storage metadata sidecar support
- authoritative document and import metadata persistence
- upload/scan lineage surfaces
- timeline API correctness for upload and scan phases
- document-detail metadata and ingest-status clarity
- audit completeness for source capture

This prompt does not own:
- resumable/chunk upload
- extraction jobs
- thumbnail rendering
- the dedicated ingest-status route backed by append-only processing runs
- full viewer implementation
- policy or export lineage beyond the current ingest phase

## Phase alignment you must preserve
From Phase 1 Iteration 1.1 and the broader product blueprint:

### Required document metadata
The canonical `documents` record must capture:
- `id`
- `project_id`
- `original_filename`
- `stored_filename`
- `content_type_detected`
- `bytes`
- `sha256`
- `page_count`
- `status`
- `created_by`
- `created_at`
- `updated_at`

### Required import metadata
The canonical `document_imports` record must capture:
- `id`
- `document_id`
- `status`
- `failure_reason`
- `created_by`
- `accepted_at`
- `rejected_at`
- `canceled_by`
- `canceled_at`
- `created_at`
- `updated_at`

### Required controlled raw-storage layout
Preserve or reconcile:
- `controlled/raw/{project_id}/{document_id}/original.bin`
- `controlled/raw/{project_id}/{document_id}/source-meta.json` (optional but phase-compatible)

Rules:
- generate storage filenames server-side
- never use user-provided names as object keys
- the source record is the uploaded original, not a mutable transformed derivative
- later derived assets must not overwrite the original source record

### Required timeline contract
`GET /projects/{projectId}/documents/{documentId}/timeline` must reflect the current upload and scan timeline after the wizard hands off.

At this stage:
- the timeline is grounded in the actual import/source lifecycle
- later extraction work extends it with extraction and thumbnail attempts
- do not fake extraction history before it exists

### Required audit events
Emit or reconcile:
- `DOCUMENT_STORED`
- `DOCUMENT_SCAN_STARTED`
- `DOCUMENT_SCAN_PASSED`
- `DOCUMENT_SCAN_REJECTED`
- `DOCUMENT_IMPORT_FAILED`

## Implementation scope

### 1. Checksum capture and integrity
Implement or reconcile checksum capture rigorously.

Requirements:
- `sha256` is computed correctly
- the checksum is tied to the immutable uploaded original
- storage/write behavior and persistence agree on the same checksum
- the stored `bytes` count is correct
- any final verification step is explicit
- failures produce safe user-facing errors and clear internal diagnostics

If the repo already computes checksums, verify and harden it rather than duplicating the logic.

### 2. Immutable source-record posture
Implement the real source-record posture without inventing unnecessary schema.

Requirements:
- the uploaded original is preserved in controlled raw storage
- metadata about that original is recorded on the canonical document/import records and optional `source-meta.json`
- the original object is not overwritten by later phases
- user-provided filenames do not become storage keys
- cancellation or rejection preserves accurate history rather than erasing the source attempt
- the browser still has no raw-original access path

Do not invent a large separate “source registry” if the phase-defined models already cover the need.

### 3. Controlled raw-storage metadata sidecar
If the repo does not already have an equivalent, add or reconcile:
- `controlled/raw/{project_id}/{document_id}/source-meta.json`

Requirements:
- it is audit-safe
- it captures stable source metadata helpful for later lineage
- it does not contain unsafe secrets
- it stays aligned with the DB source of truth rather than drifting away from it

Good examples of safe content:
- document ID
- project ID
- original filename
- stored filename
- detected content type
- bytes
- sha256
- upload timestamps
- uploader ID or stable reference if the current repo uses one safely

### 4. Timeline and lineage correctness
Implement or refine the upload/scan timeline.

Requirements:
- document detail can show the current ingest lifecycle accurately
- upload-started, stored, scanning, accepted, rejected, failed, canceled states map one-to-one to persisted status values
- canceled or rejected uploads preserve the last true stage reached
- no timeline stage implies later success if it never happened
- failure reason handling is safe and user-appropriate

You may use the existing `document_imports` model as the lineage surface for this phase rather than inventing a later-phase run model too early.

### 5. Document detail metadata and ingest status
Refine the document-detail route so it presents the source record clearly.

At minimum show or support:
- original filename
- detected type
- size
- checksum
- uploader
- timestamps
- current ingest status
- current upload/scan timeline
- safe failure/canceled messaging where relevant

Rules:
- the page must remain calm and operational
- do not dump low-level storage internals into the UI
- do not show raw object keys as user-facing primary data unless the current product style already does so safely
- no raw-original download action

### 6. API and contract alignment
Refine or reconcile the document APIs and shared contracts so they expose the source and lineage model cleanly.

At minimum ensure:
- list payloads expose safe summary fields
- detail payloads expose the source metadata needed by the detail route
- timeline payloads are explicit and typed
- browser and backend contracts stay aligned
- status enums and timeline stage names are not duplicated inconsistently across apps

### 7. Audit completeness
Use the existing audit path and ensure the source lifecycle is adequately captured.

Requirements:
- source object store/write event is auditable
- scan start, pass, reject, and fail are auditable
- canceled uploads remain traceable
- no sensitive secrets or raw bytes enter audit payloads

### 8. Documentation
Document:
- the immutable source-record posture
- checksum and size capture
- controlled raw-storage layout
- what the timeline currently includes
- how later work will extend the timeline with extraction and thumbnails
- explicit no-raw-original-browser-access posture

## Required deliverables

### Backend / storage / contracts
- hardened document and import persistence
- checksum capture path
- source metadata sidecar path if absent
- timeline API correctness
- typed detail/timeline contracts
- tests

### Web
- document-detail route refined with real source metadata and timeline
- safe ingest status presentation

### Docs
- source-record and ingest-lineage doc
- checksum/storage metadata doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/api/**`
- storage adapters/config used by the repo
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small detail/timeline/status presentation refinements are needed
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- resumable upload
- extraction jobs
- thumbnails
- full viewer UX
- dedicated append-only processing-run lineage for extraction stages
- export or manifest lineage
- raw original browser downloads

## Testing and validation
Before finishing:
1. Verify `sha256` correctness.
2. Verify recorded byte size correctness.
3. Verify generated storage naming does not use user input as object keys.
4. Verify the original is stored under the controlled raw-storage path.
5. Verify safe source metadata sidecar behavior if implemented.
6. Verify timeline output reflects real upload/scan state without implying nonexistent extraction.
7. Verify rejected and canceled imports preserve accurate history.
8. Verify source lifecycle audit events are emitted.
9. Verify document detail shows safe source metadata and status clearly.
10. Verify docs match the actual storage, checksum, and lineage behavior.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- source checksum and size capture are real
- the immutable source-record posture is real
- controlled raw-storage metadata is consistent
- document detail shows accurate source and ingest metadata
- upload/scan timeline is accurate and typed
- the browser still has no raw-original access path
- immutable source record IDs and checksums are exposed through typed APIs for downstream extraction jobs
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

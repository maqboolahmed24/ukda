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
   - `/phases/phase-03-layout-segmentation-overlays-v1.md`
3. Then review the current repository generally — layout run models, page result models, storage adapters, authenticated asset delivery, workspace routes, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second layout-output contract, a second geometry-cache schema, or conflicting storage paths.

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
- `/phases` wins for canonical PAGE-XML ownership, overlay JSON as UI cache only, geometry storage layout, access rules, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that PAGE-XML is the canonical structural source of truth and overlay JSON is only the performance-oriented rendering cache that must stay serializable back to canonical layout output.

## Objective
Implement canonical PAGE-XML, overlay JSON, and geometry storage contracts for layout outputs.

This prompt owns:
- the canonical PAGE-XML contract and serializer/validator layer
- the canonical overlay JSON contract for browser rendering
- geometry validation and normalization rules
- canonical storage layout for layout outputs
- page-level layout output metadata and hashes
- controlled-only layout artefact delivery endpoints
- workspace integration with the canonical output contracts
- tests and docs for contract stability

This prompt does not own:
- the segmentation inference engine
- manual editing/versioning tools
- line crops, region crops, page thumbnails, and context-window artefacts
- read-only overlay rendering polish
- reading-order editing

## Phase alignment you must preserve
From Phase 3:

### Canonical output rule
- PAGE-XML remains the canonical output and source of truth for layout structure.
- Internal geometry caches may be JSON for UI performance, but every run must be serializable back to canonical PAGE-XML artefacts.

### Existing storage contract
Preserve or reconcile:
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}.xml`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/page/{page_index}.json`
- `controlled/derived/{project_id}/{document_id}/layout/{run_id}/manifest.json`

Later prompts own:
- page thumbnails
- line crops
- region crops
- context windows

Do not overstep into those artefacts here.

### Existing page-layout result contract
`page_layout_results` remains authoritative for:
- `page_xml_key`
- `overlay_json_key`
- `page_xml_sha256`
- `overlay_json_sha256`
- `metrics_json`
- `warnings_json`

### Existing artefact APIs
Implement or refine:
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/overlay`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/pagexml` (Controlled-only)

### Required audit events
Emit or reconcile:
- `LAYOUT_OVERLAY_ACCESSED`
- `LAYOUT_PAGEXML_ACCESSED`

## Implementation scope

### 1. Canonical PAGE-XML contract
Implement or refine one canonical PAGE-XML contract layer.

Requirements:
- stable page-level PAGE-XML serialization
- stable region/line/baseline element identity fields where known
- canonical structural mapping for:
  - page metadata
  - regions
  - lines
  - baselines if present
  - optional reading-order placeholders if present
- validation utilities for required fields and structure
- canonical writer and reader utilities where useful
- no second XML format drifting away from PAGE-XML

Do not overbuild the full editing/versioning model yet.
This prompt owns the canonical output contract, not later edit history.

### 2. Canonical overlay JSON contract
Implement or refine one canonical overlay JSON schema for browser rendering.

Requirements:
- overlay JSON is derived from canonical layout output
- optimized for rendering, but not a second source of truth
- includes:
  - simplified polygons
  - stable element IDs
  - parent/child references
  - element types
  - optional baselines
  - optional reading-order arrows when present
  - page metadata needed by the workspace
- typed contract shared between backend and web where the repo already uses shared contracts
- no ad hoc viewer-only overlay shape drifting separately

### 3. Geometry validation and normalization
Implement geometry guards.

Requirements:
- polygons remain within page bounds
- geometry is non-empty
- no NaN/Inf values
- normalized coordinate conventions are explicit
- simplification rules are deterministic
- invalid geometry is rejected or surfaced as a safe failure, not silently passed through
- stable ID and parent/child relationships remain consistent after normalization

This prompt may introduce geometry helper modules, but not a second incompatible geometry model.

### 4. Storage layout and hashes
Implement or refine canonical storage behavior for layout outputs.

Requirements:
- PAGE-XML writes to the canonical `.xml` path
- overlay JSON writes to the canonical `.json` path
- run manifest references page-level layout output artefacts with matching page IDs, storage keys, and SHA-256 values
- `page_xml_sha256` and `overlay_json_sha256` are populated correctly
- output keys stay inside the canonical controlled derived-storage layout
- no public or raw bucket paths leak to the browser

### 5. Controlled-only artefact delivery
Implement or refine the canonical access paths.

Requirements:
- `GET .../overlay` returns the canonical overlay JSON payload
- `GET .../pagexml` returns the canonical PAGE-XML artefact through a controlled authenticated path
- RBAC matches the phase contract for layout artefact readers
- no raw storage URL leakage
- no attachment-style raw download shortcut that bypasses controlled access
- errors remain safe and exact

### 6. Workspace integration
Connect the layout workspace shell to the canonical output contracts.

Requirements:
- workspace can request overlay payloads through the canonical endpoint
- if no overlay output exists yet, the workspace shows a clear not-ready state
- overlay toggles map cleanly to the overlay contract
- no viewer/workspace component invents its own geometry schema
- web code consumes typed overlay contracts rather than stringly-typed JSON

### 7. Contract round-tripping and stability
Add stability checks where practical.

Requirements:
- overlay JSON can be derived deterministically from canonical layout output
- PAGE-XML and overlay contracts remain aligned
- serializer and validator tests cover:
  - valid sample fixtures
  - invalid geometry rejection
  - stable hashes for canonicalized output
  - stable IDs and parent/child references
- do not claim full bidirectional editing round-trip if later edit prompts still own that behavior; keep the guarantee scoped to canonical serialization and cache derivation

### 8. Audit and privacy-safe observability alignment
Use the current canonical paths.

Requirements:
- pagexml and overlay reads emit the expected audit events
- no raw storage paths or secret-bearing URLs appear in logs
- layout output errors remain privacy-safe and operationally useful

### 9. Documentation
Document:
- PAGE-XML as canonical source of truth
- overlay JSON as rendering cache
- geometry validation rules
- storage layout
- controlled artefact access rules
- what later work should add for inference, overlays, crops, and editing

## Required deliverables

### Backend / storage / contracts
- canonical PAGE-XML serializer/validator layer
- canonical overlay JSON schema and builder
- geometry validation/normalization helpers
- controlled artefact endpoints
- storage and hash hardening
- tests

### Web
- workspace integration with the canonical overlay contract
- clear not-ready/error states for absent layout output

### Docs
- PAGE-XML and overlay contract doc
- geometry validation and storage layout doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/api/**`
- storage adapters/config used by the repo
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small overlay-consumption/workspace refinements are needed
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- the segmentation engine
- manual correction and version history
- line/region crop generation
- page thumbnails
- context-window artefacts
- a second geometry-cache format
- raw or public storage delivery

## Testing and validation
Before finishing:
1. Verify PAGE-XML output writes to the canonical storage path.
2. Verify overlay JSON writes to the canonical storage path.
3. Verify `page_xml_sha256` and `overlay_json_sha256` are populated correctly.
4. Verify geometry validation rejects invalid coordinates or polygons safely.
5. Verify overlay JSON has stable element IDs and parent/child references.
6. Verify the canonical overlay endpoint returns typed browser-ready payloads.
7. Verify the controlled PAGE-XML endpoint remains authenticated and RBAC-protected.
8. Verify workspace consumers use the canonical overlay contract and handle not-ready states explicitly.
9. Verify audit events are emitted through the canonical path.
10. Verify docs match the actual PAGE-XML, overlay, and storage contracts.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- PAGE-XML is implemented as the canonical layout-output contract
- overlay JSON is implemented as the canonical rendering cache contract
- geometry validation and storage rules are real
- controlled-only access to layout artefacts is real
- the web workspace consumes canonical overlay payloads directly, without an alternate payload shape
- downstream integration points (PAGE-XML location, overlay schema, geometry IDs) are documented with example payloads and validation coverage
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

You are the implementation agent for UKDE. Work directly in the repository. Do not ask clarifying questions. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: assume zero chat memory and reread the repo plus the listed phase files before changing anything.
- Sequenced: if the repo already contains partial implementation from earlier prompts, extend and reconcile it instead of restarting from scratch.

The actual product source of truth is the extracted `/phases` directory in repo root. Do not mention or expect a zip. Read `/phases` first on every run.

## Mandatory first actions
1. Inspect the full repository tree.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/phase-05-privacy-redaction-workflow-v1.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md`
3. Then review the current repository generally — token anchors, transcription outputs, layout geometry, privacy schemas, workspace routes, safe-preview shells, typed contracts, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second finding-geometry model, a second area-mask lineage path, or conflicting token-reference semantics.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for token-linked findings, conservative area-mask fallback, append-only area-mask revisions, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that findings should attach to token anchors when available and that unreadable sensitive handwriting may use conservative geometry masks with explicit rationale and auditability.

## Objective
Build token-linked findings, bounding geometry, and conservative area-mask fallbacks for unreadable risk.

This prompt owns:
- mapping findings to transcription token anchors
- bounding-box and polygon references for findings
- `token_refs_json` and `bbox_refs` materialization
- conservative area-mask fallback creation for unreadable or incompletely tokenized sensitive content
- append-only area-mask revision lineage
- finding-detail read surfaces with geometry and token provenance
- workspace highlight behavior for token-linked and area-mask-backed findings
- regression coverage for geometry, token linkage, and fallback integrity

This prompt does not own:
- the masking decision engine itself
- dual-control review completion
- export/release artefacts
- a second geometry system outside the canonical finding and area-mask models
- public preview delivery

## Phase alignment you must preserve
From Phase 5.0, 5.1, 5.2, and the recall-first patch:

### Finding linkage rules
- `redaction_findings` support:
  - `bbox_refs`
  - `token_refs_json`
  - `area_mask_id`
- findings produced from token-capable transcript runs prefer `token_refs_json`
- conservative `area_mask_id` is allowed when token decoding is incomplete but sensitivity risk is reviewer-confirmed

### Area-mask rules
`redaction_area_masks`:
- `id`
- `run_id`
- `page_id`
- `geometry_json`
- `mask_reason`
- `version_etag`
- `supersedes_area_mask_id`
- `superseded_by_area_mask_id`
- timestamps and actor fields

Rules:
- area-mask edits never mutate geometry in place
- every change appends a new revision
- the finding’s active `area_mask_id` pointer moves to the new revision
- masks remain auditable and reversible only within controlled evidence boundaries

### Recall-first patch rules
- token-linked redaction is preferred
- when tokenization cannot be trusted for a sensitive handwritten area, conservative area masking is allowed with explicit geometry and rationale
- no downstream system may assume exact token references exist when the system has explicitly fallen back to area-mask geometry

### Required RBAC
- area-mask create/revise actions are limited to `REVIEWER`, `PROJECT_LEAD`, and `ADMIN`
- `AUDITOR` is read-only in this phase and cannot create or revise area masks
- `RESEARCHER` does not perform area-mask writes in this phase

### Required APIs
Use or refine:
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/findings`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/findings/{findingId}`
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/area-masks`
- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/area-masks/{areaMaskId}` (append-only revision semantics; no in-place geometry mutation)

## Implementation scope

### 1. Canonical token-linked finding geometry
Implement or refine the canonical token-linking path for privacy findings.

Requirements:
- token-capable transcript runs prefer `token_refs_json`
- each finding can resolve to exact token IDs and optional per-token geometry refs when available
- `bbox_refs` or equivalent bounding geometry stays coherent with token anchors
- no ad hoc client-side recomputation of finding geometry is required to make the workspace usable
- token linkage remains internal-only and leak-free

### 2. Geometry normalization and validation
Validate and normalize finding geometry.

Requirements:
- geometry remains within page bounds
- no NaN/Inf or empty geometry silently passes through
- token-linked bounding boxes or polygons remain tied to canonical token/page coordinates
- same logical finding does not get contradictory duplicated geometry refs
- invalid geometry produces explicit errors or review-required findings instead of silent corruption

### 3. Conservative area-mask fallback
Implement or refine the fallback path for unreadable risk.

Requirements:
- when token decoding is incomplete or unreadable sensitive handwriting is reviewer-confirmed, the system can create a conservative area mask
- mask geometry is explicit and auditable
- mask reason is required
- findings using area masks remain clearly distinct from token-linked findings
- no fake token refs are fabricated just to satisfy downstream consumers

### 4. Area-mask revision semantics
Implement append-only area-mask revision behavior.

Requirements:
- no in-place geometry mutation
- each edit creates a new `redaction_area_masks` revision
- `supersedes_area_mask_id` and `superseded_by_area_mask_id` remain coherent
- finding projection moves to the new active mask revision
- previous masks remain readable and auditable

### 5. Finding-detail, page-level reads, and area-mask-write APIs
Implement or refine the canonical read and area-mask-write surfaces needed for privacy workspace review.

Prefer extending existing page-finding reads. At minimum ensure the canonical APIs expose:
- token refs
- bbox refs
- active area mask when present
- provenance showing whether the finding is token-linked or area-mask-backed
- typed geometry payloads that the workspace can consume directly

The finding-detail endpoint above is required and must not be treated as optional.

### 6. Workspace integration
Refine the privacy workspace to surface the new geometry truth.

Requirements:
- token-linked findings highlight exact spans or token-linked regions
- area-mask-backed findings highlight conservative geometry overlays
- the user can tell whether a finding is token-linked or area-mask-backed
- no noisy “AI uncertainty” theatrics
- empty/not-ready/error states remain calm and exact

### 7. Safe-preview and downstream-readiness truth
This prompt does not apply masking decisions yet, but it must keep the preview and downstream contract honest.

Requirements:
- preview and decision layers can later consume exact token refs or conservative masks without schema churn
- no UI surface falsely implies exact token masking when only area masks exist
- no raw transcript text or raw object-store path leaks through geometry payloads

### 8. Audit and regression
Use the canonical audit path where applicable and add regression coverage.

At minimum cover:
- token refs point at valid token IDs
- bbox refs remain page-bounded and valid
- area-mask fallback can be created for unreadable sensitive regions
- area-mask revisions append rather than mutate
- finding payloads remain typed and workspace-usable
- no secret-bearing or raw storage paths leak

### 9. Documentation
Document:
- token-linked finding semantics
- area-mask fallback rules
- geometry validation rules
- append-only area-mask revision behavior
- how Prompt 62 consumes these structures for masking and safeguarded preview

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / contracts
- token-linked finding geometry
- area-mask fallback and revision behavior
- typed finding geometry contracts
- read APIs
- tests

### Web
- privacy workspace geometry/highlight refinement
- token-linked vs area-mask-backed finding presentation

### Docs
- finding geometry and area-mask fallback doc
- append-only area-mask revision doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small finding-highlight/geometry presentation refinements are needed
- `/workers/**` only if a tiny helper is needed to compute canonical geometry refs
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- masking decision application
- dual-control completion logic
- a second geometry system
- public preview delivery
- fake token refs for unreadable content

## Testing and validation
Before finishing:
1. Verify token-linked findings point at valid token IDs.
2. Verify bounding geometry is valid and page-bounded.
3. Verify conservative area-mask fallback can be created when token decoding is incomplete.
4. Verify area-mask edits append new revisions instead of mutating prior geometry.
5. Verify finding payloads distinguish token-linked and area-mask-backed cases clearly.
6. Verify workspace highlights use the canonical geometry contracts.
7. Verify no raw transcript text or raw storage paths leak through finding geometry payloads.
8. Verify docs match the implemented token-link and area-mask behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- token-linked findings are real
- bounding geometry is real and validated
- conservative area-mask fallback is real
- area-mask revisions are append-only
- the privacy workspace can present these findings truthfully
- geometry and area-mask contracts are documented and validated by contract tests used by masking pipeline consumers
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

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
   - `/phases/phase-06-redaction-manifest-ledger-v1.md`
   - `/phases/phase-08-safe-outputs-export-gateway.md`
3. Then review the current repository generally — approved privacy runs, reviewed snapshot artefacts, run-level output manifests, governance routes/models, storage adapters, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second manifest format, a second screening-safe summary pipeline, or manifest content that leaks raw sensitive text.

## Source-of-truth rule
- The canonical truth for this prompt is:
  1. the precise `/phases` files listed above
  2. this prompt
  3. current repository state for reconciling implementation details
- Any other repo files are context only.
- Use current official docs for implementation mechanics only.

## Conflict-resolution rule
- `/phases` wins for screening-safe manifest content, deterministic serialization, pinned policy lineage, and non-export-approved internal access rules.
- Official docs win only for implementation mechanics.
- Preserve the rule that manifests explain what changed without leaking raw sensitive text and without implying Phase 8 release approval.

## Objective
Generate screening-safe manifests with contents, hashes, policy lineage, and reviewer sign-offs.

This prompt owns:
- deterministic manifest generation for approved Phase 5 runs
- manifest entry completeness and screening-safe redaction summaries
- manifest hash generation and verified streaming
- pinned policy snapshot and review-signoff lineage in manifest content
- manifest entries API and manifest hash API
- manifest tab and raw JSON viewer for allowed roles
- internal-only streaming and not-export-approved signaling
- regression coverage for completeness, determinism, and no-sensitive-text leakage

This prompt does not own:
- evidence-ledger content generation
- export request / release-pack workflows
- public download paths
- pseudonymisation/generalization semantics beyond what is already represented in decision data
- a second manifest serializer

## Phase alignment you must preserve
From Phase 6 Iteration 6.1:

### Goal
Generate a stable manifest that explains what changed without leaking raw sensitive text or implying release approval.

### Required manifest content
For every applied redaction include:
- applied action (`MASK`, later `PSEUDONYMIZE` or `GENERALIZE`)
- category
- page and line reference
- safe location reference or bbox token when needed
- `basis_primary` and confidence
- a screening-safe summary of any secondary detector evidence
- final Phase 5 decision state
- baseline policy snapshot hash or explicit Phase 7 policy version reference
- decision timestamp

### Required manifest rules
- do not include raw sensitive source text
- do not include reviewer-visible assist explanation text in the manifest
- only include a compact secondary-basis summary when present
- manifest bytes must be stable for the same approved run
- manifest must be derivable entirely from the locked `approved_snapshot_key` plus `approved_snapshot_sha256` decision set and run metadata

### Required web behavior
- `Manifest` tab:
  - filterable table by category, page, review state, and timestamp
  - entries endpoint:
    - `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest/entries?category={category}&page={page}&reviewState={reviewState}&from={from}&to={to}&cursor={cursor}&limit={limit}`
  - raw JSON viewer for `PROJECT_LEAD`, `REVIEWER`, `ADMIN`, and read-only `AUDITOR`
  - authenticated internal stream or staged retrieval action with clear `Internal-only` and `Not export-approved` status

### Related APIs from Phase 6.0
Implement or refine:
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest/status`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest/entries?...`
- `GET /projects/{projectId}/documents/{documentId}/governance/runs/{runId}/manifest/hash`

### Existing Phase 8 downstream linkage
Manifest generation must remain compatible with later candidate-snapshot pinning and release-pack generation.
Do not design a manifest shape that later export workflows must reinterpret from scratch.

## Implementation scope

### 1. Canonical manifest serializer
Implement or refine one canonical screening-safe manifest serializer.

Requirements:
- deterministic ordering
- deterministic bytes for the same approved run
- canonical format versioning
- no second serializer or ad hoc JSON shape in route handlers
- manifest generated only from locked approved snapshot and run metadata
- no dependence on mutable live finding/page state after approval

### 2. Manifest entry completeness
Ensure every applied redaction is represented.

Requirements:
- every applied decision contributes a manifest entry
- entries include the required fields from the phase
- safe location references are present where needed
- page and line references remain coherent with the canonical anchors
- no applied redaction is silently omitted

### 3. Screening-safe content guarantees
Enforce the privacy boundary.

Requirements:
- raw sensitive source text is excluded
- reviewer-visible assist explanation text is excluded
- only compact secondary-basis summaries are included
- no raw object-store paths or secret-bearing references appear
- manifest remains suitable for internal screening, not external release

### 4. Policy and reviewer lineage
Include governance lineage cleanly.

Requirements:
- baseline policy snapshot hash or explicit policy lineage reference is present
- approval / sign-off lineage is captured from the locked review snapshot and run-review metadata
- manifest clearly reflects that it is derived from an approved locked run
- later Phase 7 policy lineage can extend this without breaking the manifest contract

### 5. Manifest storage and hashes
Persist manifest artefacts coherently.

Requirements:
- manifest bytes stream through the canonical controlled path
- `manifest_key` and `manifest_sha256` are populated correctly
- hashes are stable and verifiable
- no raw/public URLs are returned
- status endpoint remains truthful for queued/running/failed/ready states

### 6. Manifest entries API and filters
Implement or refine the entry-read surface.

Requirements:
- filterable by category, page, review state, and timestamp
- typed cursor/limit behavior
- rows map back to the canonical manifest artefact and approved decision set
- table and entries remain screening-safe
- no client-side reconstruction of manifest content from mutable live rows is required

### 7. Manifest tab and raw JSON viewer
Refine the governance UI.

Requirements:
- manifest table is dense, calm, and exact
- raw JSON viewer is available to allowed roles only
- internal-only and not-export-approved status is explicit
- unavailable / queued / failed / ready states are truthful
- no noisy “download/export” affordances that imply Phase 8 approval

### 8. Audit and regression
Use the canonical audit path and add manifest coverage.

At minimum cover:
- manifest completeness
- deterministic serializer output
- manifest excludes raw sensitive source text
- manifest hash matches streamed bytes
- entries filters behave correctly
- access rules for allowed roles
- no raw storage leaks

### 9. Documentation
Document:
- screening-safe manifest contract
- deterministic serialization rules
- policy and reviewer lineage fields
- internal-only access rules
- what later governance and export prompts consume from this manifest

## Required deliverables
Create or refine the closest coherent equivalent of:

### Backend / storage / contracts
- canonical manifest serializer
- manifest storage and hash handling
- manifest entries API and hash API
- tests

### Web
- governance manifest tab
- filterable entries table
- raw JSON viewer
- internal-only status presentation

### Docs
- screening-safe manifest contract doc
- manifest hashing and policy-lineage doc
- any README updates required for developer usage

Reuse the current repo structure if it already has a coherent pattern.

## Allowed touch points
You may modify:
- `/api/**`
- storage adapters/config used by the repo
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small governance-table/json-viewer refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- evidence-ledger content generation
- export/release-pack workflows
- public manifest downloads
- a second manifest serializer
- inclusion of raw sensitive text or hidden assist reasoning

## Testing and validation
Before finishing:
1. Verify every applied redaction appears in the manifest.
2. Verify manifest output is deterministic for the same approved run.
3. Verify raw sensitive source text is excluded.
4. Verify reviewer-visible assist explanation text is excluded.
5. Verify manifest hash matches streamed bytes.
6. Verify manifest entries filters work correctly.
7. Verify allowed-role access and internal-only signaling are correct.
8. Verify docs match the implemented manifest contract and hashing behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- screening-safe manifest generation is real
- manifest hashes and storage are real
- manifest entries and raw JSON views are real
- no raw sensitive content leaks
- manifest contract version and required fields are documented and validated by manifest schema tests
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

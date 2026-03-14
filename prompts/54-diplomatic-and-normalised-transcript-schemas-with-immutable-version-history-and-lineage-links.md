You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed phase files before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first on each run.

## Mandatory first actions
1. Inspect the full repository tree.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/phase-04-handwriting-transcription-v1.md`
   - `/phases/phase-05-privacy-redaction-workflow-v1.md` for downstream stale-basis expectations only
3. Then review the current repository generally — transcription schemas, output projections, line/token results, typed contracts, routes, audit code, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second transcript-version model, a second normalised-layer store, or conflicting lineage semantics.

## Source-of-truth hierarchy
Use this precedence order when implementing:
1. The specific `/phases` files listed in this prompt for product behavior and acceptance logic.
2. `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md` when this prompt depends on web-first execution semantics.
3. `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` when this prompt depends on recall-first, rescue, token-anchor, search-anchoring, or conservative-masking semantics.
4. `/phases/blueprint-ukdataextraction.md`, `/phases/README.md`, `/phases/ui-premium-dark-blueprint-obsidian-folio.md`, and `/phases/phase-00-foundation-release.md` as supporting product context when they are listed or clearly relevant.
5. This prompt for task scope and deliverables.
6. Current repository state for reconciling implementation details.
7. Official external docs for implementation mechanics only.

Treat current repository state as implementation context, not as the primary source of product truth.

## Conflict-resolution rule
- `/phases` wins for append-only transcript history, corrected PAGE-XML projection behavior, normalised-layer separation, and downstream stale-basis rules.
- Official docs win only for implementation mechanics.
- Preserve the rule that diplomatic transcript remains primary and normalised text stays a separate auditable layer.

## Objective
Persist diplomatic and normalised transcript schemas with immutable version history and lineage links.

This prompt owns:
- append-only diplomatic transcript versioning
- corrected PAGE-XML projection materialization
- immutable `transcript_versions` lineage
- `transcription_output_projections` updates from approved corrections
- normalised transcript layer schema and storage
- suggestion-event lineage for reviewer-controlled normalisation
- token-anchor refresh or stale-marker rules after text correction
- APIs for variant-layer reads and suggestion decisions
- downstream redaction invalidation when active transcript basis changes

This prompt does not own:
- the full correction workspace UI
- reviewer assist UI polish
- automatic assist application
- transcription inference rollout
- privacy decisioning or masking
- a second transcript history system

## Phase alignment you must preserve
From Phase 4 Iteration 4.3 and 4.6:

### Required append-only diplomatic correction rules
- never overwrite model output directly
- each correction appends a new `transcript_versions` row
- update `line_transcription_results.active_transcript_version_id`
- mark the prior active version as superseded through `transcript_versions.superseded_by_version_id`
- update canonical PAGE-XML `TextEquiv` with approved diplomatic text
- refresh `transcription_output_projections` so later phases consume a stable corrected projection
- corrections that change token boundaries, token text, or token geometry must append refreshed `token_transcription_results` rows with `projection_basis = REVIEW_CORRECTED`, or else mark token anchors stale and block downstream activation until refreshed projections exist
- if the edited transcript belongs to the active transcription run, set `document_transcription_projections.downstream_redaction_state = STALE` with timestamp and reason

### Required normalised-layer rules
Use or reconcile:
- `transcript_variant_layers`
  - `variant_kind = NORMALISED`
  - `base_transcript_version_id`
  - `base_projection_sha256`
- `transcript_variant_suggestions`
- `transcript_variant_suggestion_events`

Rules:
- normalised output never overwrites diplomatic baseline
- every normalised layer points at the exact `transcript_versions.id` it was derived from
- regenerated normalised layers append a new row rather than rebinding an existing layer to a newer diplomatic correction
- persist only reviewer-visible suggestion text, confidence, and audit metadata
- never persist hidden reasoning text

### Required APIs
Implement or refine:
- `PATCH /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/lines/{lineId}`
  - appends a new `transcript_versions` row
  - leaves engine output immutable
  - returns the newly active version
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/variant-layers`
- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/variant-layers/NORMALISED/suggestions/{suggestionId}/decision`

For this prompt, variant-layer decisioning is scoped to `NORMALISED` only.

### Required RBAC
- `PROJECT_LEAD`, `REVIEWER`, `RESEARCHER`, and `ADMIN` can read transcript version and variant-layer surfaces
- only `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can save diplomatic corrections or record normalised suggestion decisions

### Required audit events
- `TRANSCRIPT_LINE_CORRECTED`
- `TRANSCRIPT_EDIT_CONFLICT_DETECTED`
- `TRANSCRIPT_DOWNSTREAM_INVALIDATED`
- `TRANSCRIPT_VARIANT_LAYER_VIEWED`
- `TRANSCRIPT_ASSIST_DECISION_RECORDED`

## Implementation scope

### 1. Canonical transcript versioning
Implement or refine append-only diplomatic transcript history.

Requirements:
- `transcript_versions` is authoritative for correction history
- every correction creates a new immutable version row
- `version_etag` is used for optimistic concurrency
- prior versions remain queryable and immutable
- diffs can be derived from version history without mutating engine output

### 2. Corrected PAGE-XML and output projections
Implement the corrected-output projection behavior.

Requirements:
- canonical PAGE-XML `TextEquiv` is refreshed to the approved diplomatic correction projection
- `transcription_output_projections` point at the corrected projection artefacts
- corrected-pagexml key and hashes are updated consistently
- source PAGE-XML hash remains preserved
- later phases consume the corrected projection, not ad hoc edit history reconstruction

### 3. PATCH line correction API
Implement or refine:
- `PATCH /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/lines/{lineId}`

Requirements:
- accepts new diplomatic text plus `version_etag`
- validates line ownership and current active version
- rejects stale writes with optimistic-lock conflict
- appends a new version row
- returns the newly active version and updated projection metadata
- only `REVIEWER`, `PROJECT_LEAD`, or `ADMIN` may save corrections

### 4. Token refresh or stale-marker rules
Corrected text affects anchors.

Requirements:
- when correction changes token boundaries, token text, or token geometry:
  - append refreshed `token_transcription_results` rows with `projection_basis = REVIEW_CORRECTED`
  - or explicitly mark token anchors stale and block downstream activation until refreshed
- no silent mismatch between corrected text and token anchors
- activation and downstream readers can detect stale token-anchor state explicitly

### 5. Normalised transcript layers
Implement or refine the normalised-layer schema and storage path.

Requirements:
- `variant_kind = NORMALISED`
- normalised text remains separate from diplomatic text
- each normalised layer is pinned to `base_transcript_version_id`
- `base_projection_sha256` is preserved
- normalised layers append new rows rather than rebinding old rows
- no silent overwrite of prior normalised outputs

### 6. Suggestion event persistence
Implement the suggestion-decision path.

Requirements:
- `transcript_variant_suggestions` remain explicit, reviewer-visible suggestion objects
- decisions append `transcript_variant_suggestion_events`
- decision flow updates suggestion projection state without mutating diplomatic text
- no hidden reasoning or chain-of-thought persistence
- suggestion lineage remains auditable and queryable

### 7. Downstream invalidation
Harden the stale-basis behavior.

Requirements:
- if the edited transcript belongs to the active transcription run, downstream redaction state becomes `STALE`
- invalidation timestamp and reason are persisted
- stale reason is explicit enough for later privacy/export phases to surface
- no silent “still current” basis after correction

### 8. Audit and regression
Use the canonical audit path and add regression coverage.

At minimum cover:
- version rows created per correction
- correct supersession links
- optimistic-lock conflict handling
- corrected PAGE-XML projection updates
- normalised layer pinned to exact base version
- suggestion decisions recorded append-only
- downstream redaction invalidation on active-run edits
- no hidden reasoning persisted

### 9. Documentation
Document:
- diplomatic vs normalised layer separation
- immutable transcript versioning
- corrected PAGE-XML projection rules
- token refresh vs stale-marker rules
- variant-layer lineage rules
- what later workspace and assist work must use

## Required deliverables
### Backend / contracts
- append-only transcript versioning
- corrected output projections
- PATCH line correction API
- normalised-layer and suggestion-event persistence
- downstream invalidation logic
- tests

### Web
- only small read-path or conflict-state refinements if required for accurate later UI consumption

### Docs
- transcript versioning and projection doc
- normalised-layer and suggestion-lineage doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**` only if a tiny projection refresh helper is needed
- `/packages/contracts/**`
- `/web/**` only if small read-path or conflict-state refinements are required
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- full correction workspace UI
- assist UI polish
- automatic assist application
- transcription inference rollout
- privacy masking
- a second transcript history system

## Testing and validation
Before finishing:
1. Verify each correction creates a new `transcript_versions` row.
2. Verify prior versions remain immutable and linked through supersession.
3. Verify stale `version_etag` writes are rejected safely.
4. Verify corrected PAGE-XML and output projections refresh consistently.
5. Verify token refresh or stale-marker behavior is explicit and accurate.
6. Verify normalised layers are pinned to exact base transcript versions.
7. Verify suggestion decisions append event rows and do not mutate diplomatic text.
8. Verify correction and suggestion-decision RBAC boundaries are enforced.
9. Verify editing the active transcription run marks downstream redaction state `STALE`.
10. Verify no hidden reasoning text is persisted.
11. Verify docs match the implemented versioning and lineage behavior.
12. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- diplomatic transcript history is append-only, with prior versions remaining immutable and queryable
- corrected PAGE-XML projections are persisted and the active projection pointer references the selected corrected version
- token refresh jobs or stale-marker updates are persisted with typed status so downstream consumers can detect freshness
- normalised layers are separate, pinned, and lineage-safe
- active-run transcript edits mark dependent redaction artefacts stale with persisted stale reason and timestamp
- correction/assist integration fields are exposed in typed transcript lineage contracts with documented semantics
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

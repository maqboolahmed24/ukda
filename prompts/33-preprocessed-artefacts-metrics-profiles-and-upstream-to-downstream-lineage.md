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
   - `/phases/phase-02-preprocessing-pipeline-v1.md`
   - `/phases/phase-03-layout-segmentation-overlays-v1.md` for downstream handoff expectations only
3. Then review the current repository generally — preprocessing models, workers, storage adapters, active-projection logic, document/page models, preprocessing routes, typed contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second preprocessing lineage model, a second profile system, or conflicting active-run selection rules.

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
- `/phases` wins for immutable artefact versioning, profile reproducibility, projection behavior, downstream lineage expectations, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the non-negotiable rule that original page images remain immutable inputs and preprocessing only creates new derived artefacts.

## Objective
Persist preprocessed artefacts, metrics, profiles, and upstream-to-downstream lineage with immutable versions.

This prompt owns:
- immutable preprocessing artefact persistence
- canonical profile versioning and persistence
- run manifests and per-page artefact metadata
- explicit active preprocess projection metadata alignment
- explicit upstream-to-downstream lineage from source page to preprocess outputs
- metadata and provenance surfaces for preprocessing
- downstream handoff contracts for later layout consumers

This prompt does not own:
- compare workspace rendering polish
- quality triage UX
- advanced aggressive preprocessing techniques
- layout segmentation work itself
- export/provenance bundle release behavior from later phases

## Phase alignment you must preserve
From Blueprint versioning rules and Phase 2 non-negotiables:

### Blueprint rules
- every pipeline stage creates a new immutable artefact version
- page entities persist preprocessing versions and quality metrics
- outputs remain reproducible and version-linked
- historical artefacts are not overwritten to reflect later choices

### Phase 2 non-negotiables
- original page images remain immutable inputs
- every preprocessing profile is versioned, reproducible, and provenance-linked to the source page
- compare and quality surfaces use the same controlled access rules as the Phase 1 viewer
- optional aggressive techniques never become silent defaults

### Existing Phase 2 preprocessing model
Preserve or reconcile:
- `preprocess_runs`
- `page_preprocess_results`
- `document_preprocess_projections`
- immutable source page metadata on `pages`

### Downstream handoff expectation
Phase 3 later consumes `document_preprocess_projections.active_preprocess_run_id` as the canonical input selection for layout analysis.
This prompt must make that handoff explicit and stable without implementing Phase 3 itself.

## Implementation scope

### 1. Canonical profile version registry
Implement or refine one canonical persisted preprocessing-profile registry.

Requirements:
- stable profile identity
- versioned profile definitions
- persisted expanded params
- canonical `params_hash`
- reproducible profile metadata
- no ad hoc hardcoded profile copies drifting across worker, API, and UI

Use the least disruptive correct strategy for the current repo:
- seeded DB table
- versioned registry materialized into persistence
- or a similarly durable canonical source

At minimum, the registry must support:
- stable `profile_id`
- human label
- description
- expanded `params_json`
- `params_hash`
- version or immutable revision identity
- advanced/gated flag where appropriate
- supersession relationship if a profile revision later replaces another

### 2. Immutable run and artefact manifests
Implement or refine immutable preprocessing manifests.

Requirements:
- every run has a manifest or equivalent durable summary
- manifest ties together:
  - document and project identity
  - source page inputs
  - selected profile/version
  - expanded params
  - params hash
  - pipeline version
  - container digest
  - output artefact keys
  - output hashes
  - per-page metrics references where applicable
- manifests are immutable once the run is finalized
- reruns append new manifests rather than rewriting prior ones

If the repo already writes `manifest.json`, harden and expand it instead of inventing a second manifest path.

### 3. Per-page lineage and artefact metadata
Implement or refine explicit per-page lineage records using the canonical phase models.

Requirements:
- `page_preprocess_results` stay authoritative for:
  - input object key
  - output object keys
  - metrics
  - hashes
  - warnings
  - failure reason
- every derived output is traceable to:
  - source page ID
  - run ID
  - profile/version
  - params hash
- no later rerun overwrites an earlier page result row
- historical rows remain queryable and accurate

### 4. Explicit active projection semantics
Preserve and expose the explicit active-run projection behavior established by the canonical preprocessing route family.

Requirements:
- if an active run exists, `active_profile_id` stays aligned with that activated run
- the projection is always explicit; no “latest successful wins” shortcut is allowed
- downstream consumers can resolve the active preprocess run without guessing
- this prompt may harden metadata alignment around the active projection, but activation rules, supersession semantics, and downstream invalidation behavior remain outside this prompt's scope

### 5. Metadata and lineage APIs
Implement or refine the smallest consistent API surface needed to expose immutable metadata and lineage.

Prefer extending existing canonical run/detail endpoints over creating parallel endpoints.
At minimum, the backend must expose enough typed information to support:
- preprocessing metadata view for a document and selected run
- manifest-level run summary
- per-page preprocess artefact metadata
- active preprocess projection lookup
- downstream-safe active projection state

If a dedicated metadata endpoint helps keep the UI consistent, you may add an equivalent endpoint:
- `GET /projects/{projectId}/documents/{documentId}/preprocessing/metadata?runId={runId}`
or extend existing run/detail endpoints instead.

### 6. Metadata tab / provenance surface
Implement or refine the preprocessing metadata surface.

Requirements:
- clear active-run display
- profile and profile-version display
- params hash
- pipeline version
- container digest
- source page metadata summary
- derived artefact summary
- manifest availability and integrity summary
- active projection state
- downstream-consumer note that this run is the canonical default only when explicitly activated

The surface must stay calm, dense, and exact.
Do not dump raw storage internals or giant debug JSON blobs into the primary UI.

### 7. Downstream handoff contract
Make the downstream contract explicit for later phases.

Requirements:
- the active preprocess run is the only default input selection for later phase consumers
- downstream consumers do not infer “best” or “latest” run implicitly
- run activation and lineage remain explicit and auditable
- if a later run is activated, historical runs remain accessible and immutable
- the contract is documented so Phase 3 does not need schema changes

### 8. Audit alignment
Use the current repo's existing audit path.

At minimum emit or reconcile:
- `PREPROCESS_RUN_VIEWED`
- `PREPROCESS_ACTIVE_RUN_VIEWED`

Activation-event semantics are outside this prompt's scope. If a metadata-tab or manifest-view event fits the existing taxonomy cleanly, add it through the canonical audit system rather than inventing a new path.

### 9. Documentation
Document:
- profile versioning rules
- immutable artefact versioning rules
- active projection behavior
- per-page lineage ownership
- downstream handoff contract
- what later work should add in compare, triage, and advanced profiles

## Required deliverables

### Backend / workers / storage / contracts
- canonical profile registry
- manifest persistence or hardening
- per-page preprocess artefact lineage
- active projection metadata alignment
- typed lineage/metadata contracts
- tests

### Web
- preprocessing metadata surface
- active-run and manifest/provenance presentation
- shell integration

### Docs
- preprocessing artefact versioning and lineage doc
- active projection and downstream handoff doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**`
- storage adapters/config used by the repo
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small metadata/provenance presentation refinements are needed
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- compare rendering polish
- quality triage UI
- advanced aggressive profiles
- layout segmentation
- export or release provenance bundles
- a second lineage model
- rewriting history on prior runs

## Testing and validation
Before finishing:
1. Verify profile identity/version persistence is stable.
2. Verify identical expanded params serialize to the same `params_hash`.
3. Verify run manifests are immutable after finalization.
4. Verify historical preprocess runs and page results remain queryable after activation or rerun.
5. Verify activating a run updates only the projection and not prior historical rows.
6. Verify the metadata/provenance surface reflects the canonical active run accurately.
7. Verify downstream resolution uses the explicit projection instead of “latest successful”.
8. Verify docs match actual lineage, profile, and projection behavior.
9. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- preprocessing profiles are versioned, persisted, and queryable by `profile_version` and `run_id`
- derived artefacts are immutable and lineage-linked
- run manifests and per-page artefact metadata are persisted, queryable, and linked by run/page identifiers
- active projection behavior is explicit and hardened
- downstream consumers have a stable handoff contract
- the UI can inspect preprocessing provenance without noise
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

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
   - `/phases/phase-02-preprocessing-pipeline-v1.md`
3. Then review the current repository generally — jobs/workers, derived page assets, preprocessing schema, storage adapters, no-egress guards, typed contracts, preprocessing routes, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second preprocessing engine, a second derived-storage path, or conflicting params/provenance logic.

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
- `/phases` wins for preprocessing algorithm order, determinism rules, metric contract, storage layout, and no-egress requirements.
- Official docs win only for implementation mechanics.
- Preserve deterministic, internal-only preprocessing. No external calls, no public image pipelines, no silent parameter drift.

## Objective
Build the deterministic preprocessing engine v1 with reproducible image-transform profiles.

This prompt owns:
- preprocessing job types and worker integration
- grayscale preprocessing outputs
- deterministic parameter hashing and run provenance
- per-page metrics and warning generation
- preprocess manifest generation
- run finalization and page-result population
- active-run visibility in the web app
- golden-set regression coverage and no-egress enforcement for preprocessing

This prompt does not own:
- compare-mode polishing
- aggressive preprocessing profiles beyond a clean v1 profile system
- later activation/supersession logic beyond what already exists
- layout/transcription/privacy work
- external model/service calls

## Phase alignment you must preserve
From Phase 2 Iteration 2.1:

### Required job types
- `PREPROCESS_DOCUMENT(run_id)`
- `PREPROCESS_PAGE(run_id, page_id)`
- `FINALIZE_PREPROCESS_RUN(run_id)`

### Required storage layout
Inputs:
- `controlled/derived/{project_id}/{document_id}/pages/{page_index}.png`

Outputs:
- `controlled/derived/{project_id}/{document_id}/preprocess/{run_id}/gray/{page_index}.png`
- `controlled/derived/{project_id}/{document_id}/preprocess/{run_id}/metrics/{page_index}.json`
- `controlled/derived/{project_id}/{document_id}/preprocess/{run_id}/manifest.json`

### Required algorithm order
Run in a stable order:
1. decode and normalize to 8-bit grayscale
2. resolution standardization (record DPI; warn if unknown or low)
3. deskew (measure and correct skew angle)
4. background or shading normalization
5. denoise (small-kernel conservative cleanup)
6. contrast equalization (capped to avoid ink blowout)
7. write output and SHA-256

### Required page metrics
- `skew_angle_deg`
- `dpi_estimate`
- `blur_score`
- `background_variance`
- `contrast_score`
- `noise_score`
- `processing_time_ms`
- `warnings` such as:
  - `LOW_DPI`
  - `HIGH_SKEW`
  - `HIGH_BLUR`
  - `LOW_CONTRAST`

### Required determinism and provenance rules
Every run persists:
- full parameter set
- pipeline version
- container digest

Constraint:
- same input + same params + same version must produce identical output hashes in the same container/runtime

### Required web integration
- Processing Runs tab:
  - primary CTA `Run preprocessing`
  - columns:
    - run ID
    - profile
    - started by
    - time
    - status
    - pages processed
- Run detail page:
  - summary cards
  - warning counts
  - parameters drawer collapsed by default
- Overview or equivalent page-status surface:
  - per-page preprocess status indicators come from `document_preprocess_projections.active_preprocess_run_id`, not from an implicit latest-successful scan

## Implementation scope

### 1. Canonical preprocessing engine
Implement the real preprocessing engine inside the current repo's canonical worker/job path.

Requirements:
- use the repo's existing jobs framework if present
- no second queue
- deterministic grayscale derivative generation
- no external calls
- no hidden dependence on mutable host state that breaks determinism
- safe failure and cancel behavior
- worker/logging remains privacy-safe

### 2. Job integration
Wire the engine to the required preprocessing job types.

Requirements:
- `PREPROCESS_DOCUMENT` orchestrates page work for a run
- `PREPROCESS_PAGE` processes a single page deterministically
- `FINALIZE_PREPROCESS_RUN` finalizes summary state and manifest
- canceled runs stop scheduling additional page work
- retry of `PREPROCESS_PAGE` is idempotent and does not create duplicate logical page-result rows
- run status transitions remain consistent

### 3. Parameter profiles and hashing
Implement a clean profile system for v1.

Requirements:
- support canonical `profile_id` values such as `BALANCED`, `CONSERVATIVE`, `AGGRESSIVE` if the repo already adopted them
- persist expanded `params_json`
- canonical serialization for `params_hash`
- same semantic params serialize identically
- no ad hoc parameter shape drift across API, worker, and UI
- the engine always records the actual parameters used

### 4. Output writing and checksums
Implement or refine output writing.

Requirements:
- write grayscale derivative PNGs to the canonical preprocess-derived prefix
- write metrics JSON per page
- write run manifest
- capture `sha256_gray`
- keep `output_object_key_bin` nullable unless the repo already has a consistent binary path
- do not overwrite source page assets
- do not write outside the controlled derived-storage layout

### 5. Metrics and warnings
Implement real metric capture.

Requirements:
- compute and persist the required metrics
- produce warnings deterministically from measured values
- warning names are stable and typed
- warning counts roll up to the run detail summary
- no fake “quality score” theater disconnected from real metrics

### 6. Run finalization and projections
Implement consistent run finalization.

Requirements:
- run state becomes `SUCCEEDED`, `FAILED`, or `CANCELED` accurately
- page result states roll up correctly
- manifest summarizes outputs and run identity
- active projection behavior remains explicit
- successful completion does not silently activate a run unless the current repo explicitly designed that behavior
- historical runs remain immutable

### 7. Web integration
Refine the preprocessing UI to consume real engine output.

Requirements:
- runs list reflects real status progression
- run detail shows summary cards and warning counts
- parameters drawer is present and collapsed by default
- the overview or equivalent page-status surface shows per-page preprocess status based on the active projection
- quality and overview surfaces can read real metrics where available
- no fake compare imagery or later-phase diagnostics are introduced here

### 8. Determinism and regression harness
Add the required determinism coverage.

Requirements:
- canonical param serialization test (`same params => same hash`)
- deskew stability tests on known skew fixtures
- derived-output key prefix tests
- golden dataset (10-20 pages) with:
  - hash checks or approved SSIM threshold
  - CI failure on unapproved drift
- no-egress enforcement on preprocessing jobs

Keep the regression pack deterministic and maintainable.

### 9. Documentation
Document:
- job types and run flow
- algorithm order
- profile and params hashing
- storage layout
- metric and warning semantics
- determinism expectations
- how later work extends compare and activation behavior without breaking provenance

## Required deliverables

### Backend / workers / storage
- preprocessing worker/handlers
- job integration
- output writing
- metrics JSON generation
- manifest generation
- tests and golden-set harness

### Web
- runs tab refinement
- run detail summary and parameters drawer
- pages-tab active-status integration
- accurate engine-backed status surfaces

### Docs
- preprocessing engine v1 doc
- determinism and golden-set regression doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**`
- storage adapters/config used by the repo
- `/packages/contracts/**`
- `/packages/ui/**` only if small run-detail/status/metrics refinements are needed
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- later compare-surface polish
- aggressive risky preprocessing defaults without explicit gating
- layout segmentation
- transcription
- privacy work
- export or provenance bundle work
- external service calls of any kind

## Testing and validation
Before finishing:
1. Verify create run -> enqueue pages -> outputs written -> run finalizes.
2. Verify deterministic param serialization and params hashing.
3. Verify deskew stability on known skew fixtures.
4. Verify output keys remain inside the preprocess derived prefix.
5. Verify metrics and warnings are persisted per page.
6. Verify golden-set regression passes or fails meaningfully on drift.
7. Verify canceled runs stop scheduling additional page work and surface `CANCELED`.
8. Verify retrying `PREPROCESS_PAGE` is idempotent.
9. Verify no-egress enforcement remains active for preprocessing jobs.
10. Verify the preprocessing UI shows real engine-backed statuses.
11. Verify docs match the implemented algorithm, storage layout, and regression behavior.
12. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- preprocessing jobs execute queued work to terminal states and persist per-page output records
- deterministic grayscale derivatives are produced
- metrics and warning records are persisted per run/page using typed schemas and deterministic warning codes
- parameter hashes and provenance fields are persisted per run and remain immutable after run finalization
- run finalization is consistent
- the preprocessing UI reflects real engine output
- no-egress enforcement remains intact
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

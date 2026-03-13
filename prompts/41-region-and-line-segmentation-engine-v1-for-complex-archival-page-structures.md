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
   - `/phases/phase-02-preprocessing-pipeline-v1.md`
   - `/phases/phase-03-layout-segmentation-overlays-v1.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` so you do not accidentally treat a layout-only pass as downstream-complete
   - `/phases/phase-04-handwriting-transcription-v1.md` for downstream stable-anchor expectations only
3. Then review the current repository generally — preprocessing projections, layout schemas, jobs/workers, storage adapters, canonical PAGE-XML and overlay contracts, typed API/client contracts, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second segmentation engine, a second layout-run lineage model, or conflicting page-result persistence rules.

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
- `/phases` wins for layout pipeline order, run lineage, page-result semantics, PAGE-XML/overlay ownership, internal-only execution, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that layout analysis consumes the explicitly activated preprocess run, writes canonical PAGE-XML plus overlay cache, and never makes downstream-complete claims merely because segmentation ran.

## Objective
Build the region-and-line segmentation engine v1 for complex archival page structures.

This prompt owns:
- the real layout-analysis worker pipeline
- layout job types and worker integration
- region and line segmentation over preprocessed page images
- polygon generation and simplification
- region/line association
- canonical per-page PAGE-XML and overlay output population
- layout metrics and warnings
- run finalization and accurate page-result state
- gold-set regression for structural quality
- no-egress enforcement for layout inference

This prompt does not own:
- read-only overlay workspace polish
- stable crop/context-window artefact materialization for downstream VLM use
- recall-first rescue-candidate generation beyond the minimum needed to keep status accurate
- manual edit tools
- reading-order editing
- transcription feature work

## Phase alignment you must preserve
From Phase 3 Iteration 3.1:

### Required jobs
- `LAYOUT_ANALYZE_DOCUMENT(run_id)`
- `LAYOUT_ANALYZE_PAGE(run_id, page_id)`
- `FINALIZE_LAYOUT_RUN(run_id)`

### Required per-page pipeline order
For each page, the pipeline must follow the phase order as closely as the current repo architecture allows:
1. select input image from the chosen preprocess run
2. run segmentation model for regions and lines/baselines
3. convert model output masks to polygons
4. simplify polygons for UI performance
5. associate lines to regions
6. compute layout metrics and warnings
7. emit canonical PAGE-XML
8. persist overlay JSON cache and page-result metadata
9. leave recall-status handling explicit and non-promotable until later recall-first work deepens it
10. finalize page-result state and run state without pretending later edit or recall work already happened

### Required metrics
At minimum persist:
- `num_regions`
- `num_lines`
- `region_coverage_percent`
- `line_coverage_percent`

### Required warnings
At minimum support:
- `LOW_LINES`
- `OVERLAPS`
- `COMPLEX_LAYOUT`

Do not falsely emit recall-completion warnings or rescue-candidate claims in this prompt unless they are genuinely backed by implemented logic.

### Required run and page-result behavior
- use the canonical `layout_runs` model
- use the canonical `page_layout_results` model
- runs are append-only attempts
- retry is idempotent
- canceled runs stop scheduling additional page work and surface `CANCELED`
- page outputs populate canonical PAGE-XML and overlay keys and hashes
- no page result should claim downstream-readiness if the recall-first stage has not yet resolved the page

### Required security posture
- internal-only execution
- no external calls
- no public model downloads
- no uncontrolled egress
- controlled derived-storage only

## Implementation scope

### 1. Canonical layout engine integration
Implement or refine the real layout-analysis worker pipeline inside the current repo's canonical worker/job system.

Requirements:
- use the existing jobs framework and worker runtime
- no second queue
- input page selection resolves through the active preprocess projection or the run's explicit `input_preprocess_run_id`
- worker execution is internal-only
- model/runtime selection is explicit and deterministic
- no ad hoc route-local inference calls

### 2. Region and line inference
Implement the real layout analysis for regions and lines.

Requirements:
- segmentation works against the preprocessed page image chosen for the run
- regions and lines/baselines are produced when the engine supports them
- line-to-region association is explicit and deterministic
- the result is suitable for later read-only overlays, line artifacts, and transcription anchoring
- do not invent fake elements just to satisfy UI shells

### 3. Polygon generation and simplification
Implement the structural geometry step.

Requirements:
- convert model masks to polygons
- simplify polygons for UI performance
- keep geometry valid and within page bounds
- preserve stable IDs needed by later work
- no NaN/Inf or empty geometry silently passes through
- parent/child relationships between regions and lines remain consistent

### 4. Metrics and warnings
Compute the phase-required metrics and warnings.

Requirements:
- `num_regions`
- `num_lines`
- region coverage percent
- line coverage percent
- warning emission for low lines, overlaps, and complex layout when justified
- warnings are typed and stable
- no fake “quality score” theater

### 5. Canonical output writing
Use the canonical output contract already established by the repo.

Requirements:
- write canonical PAGE-XML
- write canonical overlay JSON cache
- populate `page_xml_key`, `overlay_json_key`, `page_xml_sha256`, `overlay_json_sha256`
- keep output keys inside the canonical layout derived-storage prefix
- no raw/public storage exposure
- no second layout-output schema

### 6. Page-result and run finalization
Implement consistent finalization behavior.

Requirements:
- each page result reflects the actual outcome
- run status becomes `SUCCEEDED`, `FAILED`, or `CANCELED` based on actual work
- page-level failures do not get erased
- canceled work remains explicit in persisted state
- `FINALIZE_LAYOUT_RUN` summarizes page outcomes with accurate succeeded/failed/canceled counts and final run status
- no run is silently activated here
- no run claims downstream-safe completeness until later recall-first gating is satisfied

### 7. Explicit Recall-Status Posture
This prompt must not break the normative recall-first patch.

Requirements:
- if the dedicated recall-check stage is not yet implemented, page-level recall status must remain explicitly unresolved or non-promotable through the repo's existing scaffolding
- do not auto-mark pages `COMPLETE` just because layout geometry exists
- leave the system ready for later recall-check and rescue-candidate computation
- no-silent-drop behavior must remain preserved

Use the cleanest representation already present in the repo that still reflects the true state. Do not invent a hidden healthy-by-default state.

### 8. Regression and no-egress gates
Add meaningful regression coverage.

At minimum cover:
- polygon validity
- line-to-region association fixtures
- run creation -> page execution -> finalization
- retry idempotency
- canceled run behavior
- no-egress enforcement
- structural gold-set metrics such as:
  - region overlap score
  - line detection recall

Keep the suite deterministic and reviewable.

### 9. Audit alignment
Use the canonical audit path and emit or reconcile:
- `LAYOUT_RUN_CREATED`
- `LAYOUT_RUN_STARTED`
- `LAYOUT_RUN_FINISHED`
- `LAYOUT_RUN_FAILED`
- `LAYOUT_RUN_CANCELED`

Do not create a second audit path.

### 10. Documentation
Document:
- the layout-analysis worker flow
- input selection from preprocessing projections
- metric and warning semantics
- output-writing rules
- explicit non-promotable behavior before recall-first completion
- what later overlay, artifact, and recall-first work deepens next

## Required deliverables

### Backend / workers / storage / contracts
- layout-analysis worker handlers
- job integration for layout runs
- region/line inference path
- polygon and association helpers
- canonical PAGE-XML/overlay output writing
- run/page-result finalization
- tests and gold-set coverage

### Web
- only small accurate status/alive-path refinements if needed so current layout surfaces can show real run progress

### Docs
- layout engine v1 flow doc
- layout metrics/warnings and state-accuracy contract doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- storage adapters/config used by the repo
- `/packages/contracts/**`
- `/web/**` only if small status-surface refinements are required
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- overlay workspace polish
- line crops, region crops, page thumbnails, and context-window artefacts
- recall-first rescue-candidate generation
- manual edit tools
- reading-order editing
- transcription logic
- a second segmentation engine

## Testing and validation
Before finishing:
1. Verify `LAYOUT_ANALYZE_DOCUMENT`, `LAYOUT_ANALYZE_PAGE`, and `FINALIZE_LAYOUT_RUN` are real and consistent.
2. Verify polygon validity checks pass on valid fixtures and reject invalid geometry safely.
3. Verify line-to-region association fixtures pass.
4. Verify canonical PAGE-XML and overlay outputs are written and hashed.
5. Verify run creation to finalization writes expected artefacts.
6. Verify retry is idempotent and does not create duplicate logical page results.
7. Verify canceled runs stop scheduling additional page work and surface `CANCELED`.
8. Verify no-egress enforcement remains active.
9. Verify structural gold-set regression tracks region overlap score and line detection recall.
10. Verify no page is silently treated as downstream-complete merely because segmentation ran.
11. Verify docs match the implemented worker flow and state-accuracy rules.
12. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- layout runs execute document/page segmentation jobs and persist region/line outputs for processed pages
- canonical PAGE-XML and overlay outputs are real
- layout metrics and warning records are persisted per run/page with typed warning codes
- run finalization is consistent
- no-egress policy checks and regression tests run in CI and fail on violations
- overlay and artefact consumers can use existing run/page output contracts without introducing new schema entities in this prompt
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

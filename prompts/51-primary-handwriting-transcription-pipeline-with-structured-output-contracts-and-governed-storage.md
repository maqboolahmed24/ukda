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
   - `/phases/phase-03-layout-segmentation-overlays-v1.md`
   - `/phases/phase-04-handwriting-transcription-v1.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` for rescue-candidate and no-silent-drop expectations
3. Then review the current repository generally — layout projections, stable line/context artefacts, model-role assignment plumbing, jobs/workers, storage adapters, typed contracts, web surfaces, tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second transcription engine path, a second run/result schema, or conflicting structured-output contracts.

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
- `/phases` wins for VLM-first transcription behavior, governed storage, run lineage, structured response rules, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that the primary path is an approved internal transcription service behind the stable role contract, with no external calls and no uncontrolled egress.

## Objective
Implement the primary handwriting-transcription pipeline with structured output contracts and governed storage.

This prompt owns:
- the real primary VLM transcription worker path
- transcription job orchestration
- structured prompt and response contract enforcement
- line-context and rescue-context input assembly
- canonical page-level PAGE-XML transcription output
- raw structured response persistence in controlled storage
- line-level result population
- page-level result population
- run status/finalization behavior
- governed storage and deterministic output hashing
- overview/runs/workspace alive-path integration for real primary run progress

This prompt does not own:
- governed fallback engines
- token-anchor end-to-end materialization
- confidence triage UX
- manual correction UX
- normalised transcript layers
- public or external model services

## Phase alignment you must preserve
From Phase 4 Iteration 4.1:

### Required jobs
- `TRANSCRIBE_DOCUMENT(run_id)`
- `TRANSCRIBE_PAGE(run_id, page_id)`
- `FINALIZE_TRANSCRIPTION_RUN(run_id)`

### Required per-page flow
For each target page:
1. load preprocessed page image and layout PAGE-XML
2. load Phase 3 line crops, optional region crops, page thumbnail, per-line context-window artefacts, and approved rescue candidates
3. call the approved internal transcription service with a fixed structured prompt for each target line, rescue candidate, or page-window segment
4. validate the structured response against the configured response schema and existing `line_id` or rescue source anchors
5. emit PAGE-XML as canonical transcript output and persist the raw structured response in Controlled storage
6. do not silently persist invalid text when schema or anchor validation fails
7. persist outputs and SHA-256 hashes
8. keep activation blocked if token anchors required by the run are not yet materialized by later token-anchor work

### Required storage
- `controlled/derived/{project_id}/{document_id}/transcription/{run_id}/page/{page_index}.xml`
- `controlled/derived/{project_id}/{document_id}/transcription/{run_id}/page/{page_index}.response.json`
- `controlled/derived/{project_id}/{document_id}/transcription/{run_id}/page/{page_index}.hocr` only when a fallback engine later emits it; do not fake hOCR here

Deterministic mapping rule:
- worker and API `page_id` values must resolve through the canonical document-page mapping to one stable `page_index` (zero-based physical order) before storage keys are written
- storage and read paths must use that resolved `page_index` consistently; do not derive independent per-worker numbering

### Required schema contracts
Use or reconcile the canonical Phase 4 tables:
- `transcription_runs`
- `page_transcription_results`
- `line_transcription_results`
- `document_transcription_projections`
- `transcription_output_projections`

For this prompt, it is acceptable for token-level rows to remain unmaterialized if stable token-anchor generation is completed by later token-anchor work.
Do not fake token completeness just to mark runs as promotable.

### Required gates
- determinism in the same container/runtime for same input/model/prompt/params
- idempotent page retries
- PAGE-XML parse success with expected `TextLine/TextEquiv`
- every persisted line maps back to a valid `line_id` or rescue source anchor
- no-egress remains enforced

### Required RBAC
- `PROJECT_LEAD`, `REVIEWER`, `RESEARCHER`, and `ADMIN` can view transcription run status and output-read surfaces
- only `PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can create primary transcription runs

## Implementation scope

### 1. Primary VLM run creation and orchestration
Implement or refine the primary transcription orchestration path.

Requirements:
- `POST /projects/{projectId}/documents/{documentId}/transcription-runs` can create a `QUEUED` run for the primary engine path
- job orchestration uses the repo’s canonical job/worker runtime
- run records persist:
  - `engine = VLM_LINE_CONTEXT`
  - approved `model_id`
  - `prompt_template_id`
  - `prompt_template_sha256`
  - `response_schema_version`
  - `params_json`
  - `pipeline_version`
  - `container_digest`
- if the project lacks an active primary assignment through the stable role map, fail explicitly and safely
- do not call any unapproved engine directly from route handlers

### 2. Structured prompt and response contract
Implement the canonical structured-output contract.

Requirements:
- fixed prompt structure for target lines, rescue candidates, or page-window segments
- structured response schema validation
- explicit anchor validation against existing layout anchors or rescue-source references
- no silent persistence of malformed or anchorless output
- schema-validation failures remain explicit and actionable for later fallback handling

Do not persist free-form undocumented JSON blobs as if they were canonical structured responses.

### 3. Controlled storage of raw and canonical outputs
Persist governed outputs correctly.

Requirements:
- raw model response stored only in controlled storage
- raw response hash persisted
- canonical transcription PAGE-XML written to the governed storage path
- page-level hashes persisted
- no raw storage-key leakage to the browser
- no public URLs
- no overwriting of historical run outputs

### 4. Page and line result population
Populate canonical result rows.

Requirements:
- `page_transcription_results` reflect page-level run state accurately
- `line_transcription_results` populate:
  - `text_diplomatic`
  - `conf_line` when available
  - `confidence_basis`
  - `schema_validation_status`
  - `flags_json`
  - `machine_output_sha256`
  - `version_etag`
- rescue-candidate or page-window outputs must remain explicitly anchored to the correct source references
- no fake `active_transcript_version_id` values before manual correction exists

### 5. Run finalization
Implement consistent finalization behavior.

Requirements:
- `FINALIZE_TRANSCRIPTION_RUN` summarizes success/failure/cancel state accurately
- retries are idempotent and do not duplicate logical line results
- no run is silently activated here
- no run claims downstream-readiness when token-anchor prerequisites are still missing

### 6. Web alive-path integration
Refine the existing transcription shells only enough to make the primary engine visible.

Requirements:
- Runs tab can launch a run and show status progress
- Overview tab can show pages/lines/failures summary cards accurately
- read-only workspace can render multi-page transcript output for successful pages
- no fake confidence triage or correction UI yet
- use canonical data contracts and status endpoints

### 7. Security and no-egress posture
Preserve the controlled environment.

Requirements:
- primary transcription workers may call only the approved internal transcription service resolved through the stable role and service map
- no external AI API calls
- no public model pulls
- no public artefact delivery
- all persisted raw outputs remain controlled-only

### 8. Audit alignment
Use the canonical audit path and emit or reconcile:
- `TRANSCRIPTION_RUN_CREATED`
- `TRANSCRIPTION_RUN_STARTED`
- `TRANSCRIPTION_RUN_FINISHED`
- `TRANSCRIPTION_RUN_FAILED`
- `TRANSCRIPTION_RUN_CANCELED`
- `TRANSCRIPTION_RUN_VIEWED`
- `TRANSCRIPTION_RUN_STATUS_VIEWED`

Do not create a second audit path.

### 9. Documentation
Document:
- primary VLM pipeline flow
- structured response contract
- controlled raw response storage
- PAGE-XML output contract
- what later work owns:
  - fallback
  - token anchors
  - confidence triage
  - correction workspace

## Required deliverables
### Backend / workers / storage / contracts
- primary transcription job handlers
- structured prompt/response validation
- controlled raw-response storage
- page and line result population
- run finalization
- tests

### Web
- alive-path run launch/status integration for overview, runs, and read-only workspace

### Docs
- primary transcription pipeline doc
- structured output and governed storage doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- storage adapters/config used by the repo
- `/packages/contracts/**`
- `/web/**`
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- fallback engines
- token-anchor materialization end to end
- confidence triage UX
- manual correction UX
- normalised variant layers
- external model services
- public artefact delivery

## Testing and validation
Before finishing:
1. Verify `TRANSCRIBE_DOCUMENT`, `TRANSCRIBE_PAGE`, and `FINALIZE_TRANSCRIPTION_RUN` are real and consistent.
2. Verify same input/model/prompt/params in the same container/runtime produce the same structured output hash.
3. Verify retrying a page job does not duplicate logical line results.
4. Verify persisted line results map back to valid `line_id` or rescue source anchors.
5. Verify PAGE-XML parses successfully and contains expected `TextLine/TextEquiv` content.
6. Verify raw model responses persist only in controlled storage.
7. Verify no-egress enforcement remains active.
8. Verify run-creation RBAC boundaries are enforced.
9. Verify web surfaces show accurate run progress and output availability.
10. Verify docs match the implemented pipeline and storage behavior.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- primary transcription runs execute end-to-end (`QUEUED` to terminal) and persist typed page/line outputs
- structured output is validated against the typed schema, and validation failures are persisted with machine-readable error reasons
- raw responses and PAGE-XML artefacts are stored in governed internal storage with checksum-linked metadata records
- page-level and line-level transcription result rows are written for processed pages and queryable through typed APIs
- run state transitions follow one documented state machine enforced by worker and API tests
- downstream extension fields needed for fallback/confidence/token-anchor/correction flows are represented in current typed contracts without route-family rewrites
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

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
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-01-ingest-document-viewer-v1.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md`
3. Then review the current repository generally — upload APIs, document-processing models, worker/runtime code, browser tests, CI workflows, performance instrumentation, asset delivery, access-control tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second upload-resume path, a second processing-lineage model, or a second browser quality-gate stack.

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
- `/phases` wins for ingest hardening, resumable-upload intent, retry-extraction lineage, security gates, and phase quality-gate expectations.
- Official docs win only for implementation mechanics.
- Keep the secure controlled-environment posture intact. No raw-download path, no public asset path, no egress shortcuts.

## Objective
Ship ingest and viewer quality gates for access control, performance budgets, and cross-browser stability.

This prompt owns:
- resumable/chunk upload support for large-file deployments
- extraction retry lineage and retry endpoints
- processing-run lineage hardening for Phase 1.4
- access-control test coverage for document and viewer surfaces
- performance budgets for the document library and viewer
- cross-browser stability coverage for the ingest and viewer tranche
- CI wiring and docs for these gates

This prompt does not own:
- new viewer feature ergonomics
- preprocessing features from Phase 2
- export/release behavior
- raw original delivery
- a second quality-gate framework

## Phase alignment you must preserve
From Phase 1 Iteration 1.4:

### Required backend hardening
- malware scanning stage remains enforced before accept/extract
- quota enforcement remains enforced:
  - max total bytes per project
  - max documents
  - max pages
- resumable/chunk upload support for large-file deployments
- extend existing `document_processing_runs`:
  - `attempt_number`
  - `supersedes_processing_run_id`
  - `superseded_by_processing_run_id`
  - `run_kind = UPLOAD | SCAN | EXTRACTION | THUMBNAIL_RENDER`
  - append-only attempts preserved for timelines and retry views
- controlled-only `retry-extraction` action for `PROJECT_LEAD` and `ADMIN`

### Required endpoints
- `POST /projects/{projectId}/documents/{documentId}/retry-extraction`
- `GET /projects/{projectId}/documents/{documentId}/processing-runs`
- `GET /projects/{projectId}/documents/{documentId}/processing-runs/{runId}`
- `GET /projects/{projectId}/documents/{documentId}/processing-runs/{runId}/status`

### Required retry semantics
- retry creates a new extraction attempt
- increments `attempt_number`
- links backward via `supersedes_processing_run_id`
- records the forward link on the superseded run via `superseded_by_processing_run_id`
- rejects retries unless the superseded run is also `run_kind = EXTRACTION`
- does not silently fork scan or thumbnail lineage

### Required UI and operational outcomes
- network interruption UX for upload resume
- retry path for failed extraction by allowed roles
- visual regression for hard-failure and retry states
- accessibility checks pass on timeline and error surfaces

### Required security gates
- upload validation controls remain enforced
- scan failure blocks downstream processing
- no direct export or raw-download bypass introduced

## Implementation scope

### 1. Resumable/chunk upload support
Implement or refine large-file resumable upload support using the least disruptive design already present in the repo.

Requirements:
- interrupted uploads can resume without restarting from byte zero
- final assembled object matches expected checksum
- upload remains fully server-controlled
- no direct public object-store upload path
- project RBAC remains enforced
- status and final import/document state remain consistent with the existing upload/import models
- canceled or failed resumable uploads preserve accurate state

If the current repo lacks resumable primitives, add the smallest consistent upload-session model and endpoints needed.
Do not invent a public direct-to-storage flow.

### 2. Retry-extraction backend
Implement or refine extraction retry properly.

Requirements:
- `POST /projects/{projectId}/documents/{documentId}/retry-extraction`
- only `PROJECT_LEAD` and `ADMIN` can invoke it
- appends a new `document_processing_runs` row
- increments `attempt_number`
- links retry lineage correctly both backward and forward
- preserves historical run rows
- rejects retries against non-extraction runs
- downstream thumbnail lineage is not silently rewritten

### 3. Processing-runs read/status APIs
Implement or refine:
- processing-runs list
- processing-run detail
- processing-run status polling

Requirements:
- typed contracts
- project RBAC
- clear active/inactive states
- current run and historical run branches remain legible
- status polling is efficient and bounded

### 4. Upload-resume UX integration
Integrate the backend resumable upload path with the current import wizard using a single resumable-session contract.

Requirements:
- network interruption UX is clear and calm
- upload resume is explicit and safe
- progress/status messaging is exact
- inline errors remain actionable
- the wizard does not fake recovery if the backend session cannot resume
- completed upload still hands off into the canonical document/detail flow

### 5. Access-control gates
Add or harden feature-level access-control regression coverage.

At minimum cover:
- non-members cannot view document list/detail/viewer/image routes
- cross-project viewers fail closed
- unauthorized users cannot retry extraction
- researcher/reviewer/project lead/admin boundaries remain correct across:
  - upload
  - document detail
  - ingest status
  - viewer
  - retry extraction
  - processing-run details

### 6. Performance budgets
Implement or refine explicit budgets and checks for the Phase 1 slice.

At minimum define and enforce budgets for:
- document library initial render
- library filter/sort interaction responsiveness where practical
- first viewer page render
- thumbnail strip readiness
- upload wizard responsiveness under large-file and resumed-upload conditions where practical

Keep the budgets practical, measurable, and CI-friendly.
Do not invent unrealistic numbers or flaky gates.

### 7. Cross-browser stability
Extend the browser regression/gate suite to the Phase 1 ingest/viewer tranche.

Requirements:
- run on the repo's canonical browser test harness
- cover the supported browser set the repo can sustain cleanly
- prefer at least Chromium plus the strongest stable additional browsers the current stack can realistically support
- verify:
  - upload/import route basics
  - document library
  - viewer open/navigation
  - hard-failure state
  - retry state
  - auth/access denial path
- document any browser gap explicitly rather than pretending broader support than the repo can maintain

### 8. Security and no-bypass verification
Harden security test coverage.

Requirements:
- simulated malware sample rejection remains enforced
- rejected uploads do not generate pages
- no raw-download or export bypass appears
- resumable upload path does not weaken server-side type checks, quota checks, or scanning gates
- viewer/image access remains authenticated and project-scoped

### 9. CI integration and artifacts
Wire these feature-level gates into the current pipeline.

Requirements:
- meaningful artifacts on failure
- performance budget failures are actionable
- browser stability failures are actionable
- access-control failures are blocking where they should be
- commands and docs match the repo

### 10. Documentation
Document:
- resumable-upload behavior
- extraction retry lineage semantics
- performance budgets
- supported browser coverage
- access-control coverage
- how later work extends these gates without duplicating them

## Required deliverables

### Backend / workers / contracts
- resumable upload session/assembly path
- retry-extraction endpoint
- processing-runs lineage hardening
- processing-runs list/detail/status endpoints
- tests

### Web
- upload resume UX integration
- retry action integration where the UI already exposes it
- failure/retry state refinements only where needed to support the gates

### Tests / CI
- access-control gates
- performance budgets
- cross-browser ingest/viewer regression coverage
- CI wiring

### Docs
- resumable-upload and retry-extraction doc
- ingest/viewer quality-gate doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/api/**`
- `/workers/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if very small failure/retry/upload-state refinements are required
- test directories and CI/workflow files
- root config/task files
- `README.md`
- `docs/**`
- storage or infra config only where necessary for resumable upload coherence

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- preprocessing features
- viewer feature redesign
- raw original delivery
- public object-store uploads
- a second regression framework
- unrelated later-phase governance/export logic

## Testing and validation
Before finishing:
1. Verify interrupted upload resume succeeds.
2. Verify final checksum validation after chunk assembly.
3. Verify scan rejection still blocks downstream extraction.
4. Verify retry-extraction creates a new extraction attempt with correct lineage.
5. Verify `attempt_number`, `supersedes_processing_run_id`, and `superseded_by_processing_run_id` are preserved correctly.
6. Verify unauthorized users cannot access or invoke protected ingest/viewer paths.
7. Verify no raw-download or export bypass appears.
8. Verify performance budgets execute and report meaningfully.
9. Verify browser coverage is stable on the chosen supported set.
10. Verify docs match actual endpoints, budgets, and browser support.
11. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- interrupted uploads resume from the last acknowledged chunk and complete without duplicate document creation
- extraction retry lineage is real
- processing-run status surfaces are consistent
- access-control gates are real
- performance budgets define numeric thresholds and are enforced by CI checks
- cross-browser tests run on the documented Phase 1 browser matrix and report pass/fail per browser
- the secure controlled no-bypass posture remains intact
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

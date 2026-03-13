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
   - `/phases/phase-04-handwriting-transcription-v1.md`
   - `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` for rescue-sensitive uncertainty handling
3. Then review the current repository generally — transcription results, fallback comparison hooks, triage routes, workspace shells, typed contracts, browser tests, and docs — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second confidence schema, a second triage queue model, or route uncertainty through hidden ad hoc fields.

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
- `/phases` wins for confidence-basis semantics, triage filters, quality metrics, fallback-disagreement usage, and acceptance logic.
- Official docs win only for implementation mechanics.
- Preserve the rule that confidence and reviewer routing are explicit, deterministic where possible, and do not mutate the primary transcript text.

## Objective
Build confidence scoring, triage ranking, and reviewer routing for uncertain text.

This prompt owns:
- line-level confidence calculation and persistence
- agreement-based fallback confidence when model-native confidence is absent
- aggregate quality metrics and triage counts
- triage ranking and hotspot routing
- low-confidence highlighting and reviewer navigation hooks
- triage route implementation
- workspace confidence overlays and “Next low-confidence line” behavior
- deterministic confidence regression coverage

This prompt does not own:
- manual correction persistence
- normalised transcript layers
- broad compare UX
- privacy decisions
- search or export behavior

## Phase alignment you must preserve
From Phase 4 Iteration 4.2:

### Confidence sources
- use model-native confidence or logprob signals when the active VLM provides them
- otherwise derive `conf_line` from fixed internal agreement reads such as `crop-only` versus `crop+context`
- optionally compute fallback-engine disagreement as an additional review signal without mutating the primary VLM output

### Persisted outputs
- aggregate confidence
- validation flags
- compact alignment payloads
- char-box confidence payloads only when the active engine provides them

### Required quality metrics
- percent lines below threshold
- low-confidence page distribution
- segmentation mismatch warnings (line exists, empty text)
- structured-response validation failures
- fallback invocation count

### Triage tab
Columns:
- page number
- low-confidence line count
- min/avg confidence
- issues
- status

Filters:
- low-confidence only
- failed only
- confidence below threshold

### Workspace enhancements
- toggle: highlight low-confidence content
- inspector shows selected line confidence
- per-character confidence visual cues
- keyboard action: `Next low-confidence line`

### Required tests
- validator handles malformed spans or missing anchors safely
- agreement-based confidence yields deterministic `conf_line` for same crop pair
- confidence output populates DB and triage counts
- low-confidence filters and highlights match backend counts

## Implementation scope

### 1. Canonical confidence computation
Implement or refine one canonical confidence pipeline.

Requirements:
- use model-native confidence when available
- use deterministic agreement-based reads when model-native confidence is unavailable
- optionally incorporate fallback disagreement as a review signal without mutating primary text
- persist `conf_line` and `confidence_basis` consistently
- no second confidence field family scattered across tables

### 2. Alignment and char-box payloads
Persist compact alignment payloads.

Requirements:
- compact alignment payloads are stored and typed
- char-box confidence payloads are stored only when the active engine provides them
- line results remain queryable without requiring char-box presence
- malformed spans or missing anchors are handled safely and visibly

### 3. Aggregate quality metrics
Implement or refine aggregate transcription quality metrics.

Requirements:
- percent lines below threshold
- low-confidence page distribution
- segmentation mismatch warnings
- structured-response validation failure counts
- fallback invocation count
- metrics remain deterministic and explainable
- no fake monolithic “quality score”

### 4. Triage ranking and reviewer routing
Implement deterministic routing toward high-risk content first.

Requirements:
- triage results order pages by useful review priority
- ranking uses explicit factors such as low-confidence count, min confidence, failure status, and validation warnings
- ordering is typed, explainable, and stable
- no opaque magic ranking with no inspectable rationale
- if a small explicit priority field helps and suits the repository, add it through the canonical schema or computed API path

### 5. Triage route and APIs
Implement or refine:
- `GET /projects/{projectId}/documents/{documentId}/transcription/triage?status={status}&confidenceBelow={threshold}&page={pageNumber}`

Requirements:
- typed contract
- table-first triage surface
- filter support exactly aligned with the phase
- calm empty/loading/error/no-results states
- route-safe URL-state behavior
- no fake confidence rows when run output does not exist

### 6. Workspace confidence integration
Refine the workspace for uncertainty review.

Requirements:
- low-confidence highlight toggle
- inspector shows selected line confidence
- per-character confidence cues when available
- keyboard action `Next low-confidence line`
- no noisy heatmap theatrics
- line highlighting stays bounded and calm
- unavailable char-box detail is handled explicitly

### 7. Audit and regression
Use the canonical audit path where the repo already supports it and add regression coverage.

At minimum cover:
- malformed span handling
- deterministic agreement-based `conf_line`
- triage counts matching backend metrics
- low-confidence filters matching backend counts
- fallback disagreement inclusion without mutating primary text
- workspace next-low-confidence navigation consistency

### 8. Documentation
Document:
- confidence-basis rules
- triage ranking logic
- filters and reviewer-routing semantics
- char-box optionality
- what later work uses from confidence outputs during human correction and fallback comparison

## Required deliverables
### Backend / contracts
- canonical confidence computation
- aggregate quality metrics
- triage ranking and typed triage API
- tests

### Web
- triage tab
- confidence filter UI
- low-confidence highlighting
- selected-line confidence and next-low-confidence navigation

### Docs
- transcription confidence and triage doc
- reviewer routing and hotspot ranking doc
- any README updates required for developer usage

## Allowed touch points
You may modify:
- `/workers/**`
- `/api/**`
- `/web/**`
- `/packages/contracts/**`
- `/packages/ui/**` only if small triage/highlight/inspector refinements are needed
- root config/task files
- test directories and CI/workflow files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- correction persistence UI
- normalised-layer UI
- privacy/search/export logic
- a second confidence system
- opaque unexplained ranking behavior

## Testing and validation
Before finishing:
1. Verify malformed spans or missing anchors are handled safely.
2. Verify agreement-based confidence yields deterministic `conf_line`.
3. Verify aggregate metrics populate correctly.
4. Verify triage counts match backend metrics.
5. Verify triage filters behave correctly.
6. Verify low-confidence highlighting and selected-line confidence render correctly.
7. Verify `Next low-confidence line` navigation works consistently.
8. Verify fallback disagreement does not mutate primary text.
9. Verify docs match the implemented confidence and triage behavior.
10. Confirm `/phases/**` is untouched.

## Acceptance criteria
This prompt is complete only if all are true:
- confidence scoring persists numeric scores and confidence bands using a documented typed scoring contract
- triage ranking APIs return deterministic ordered results and reviewer-routing actions persist assignment changes
- aggregate quality metrics are computed from persisted scores and exposed through typed metrics endpoints
- triage UI renders ranked items with score, rationale, and deep-link targets from typed API responses
- workspace confidence cues map only to defined persisted score bands and render no undefined cue states
- uncertainty hotspots are exposed via typed filters and deep links consumable by correction workflows
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks

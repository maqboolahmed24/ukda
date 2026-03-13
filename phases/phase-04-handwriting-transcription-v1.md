# Phase 4: Handwriting Transcription v1 (VLM-First Diplomatic Transcript + Confidence) - Voices from Ink

> Status: ACTIVE
> Web Root: /web
> Active Phase Ceiling: 11
> Execution Policy: Phase 0 through Phase 11 are ACTIVE for this prompt program.
> Web Translation Overlay (ACTIVE): preserve existing workflow intent and phase semantics while translating any legacy desktop or WinUI terms into equivalent browser-native routes, layouts, and interaction patterns under /web.

## Phase Objective
Convert layout-aligned page structures into trustworthy diplomatic transcripts with explicit uncertainty signals and reviewer-first workflows, using an internal layout-aware VLM as the primary read path and audited fallback engines for validation and recovery.

## Entry Criteria
Start Phase 4 only when all are true:
- Successful Phase 2 preprocessing and Phase 3 layout outputs exist for the same document scope.
- PAGE-XML and overlay anchors are stable enough to support line-level transcription review.
- Phase 3 recall checks and rescue-candidate generation are available so missed-text risk is explicit.
- Job execution, model packaging, and transcription artefacts remain internal-only; output screening and external release still begin in Phase 8.

## Scope Boundary
Phase 4 ends at transcript generation and transcript correction.

Out of scope for this phase:
- privacy review and redaction decisions (Phase 5)
- manifests, evidence ledgers, and advanced policy authoring (Phases 6 and 7)
- export governance and external release (Phase 8)

## Phase 4 Non-Negotiables
- Secure web application is the active delivery target: preserve phase behavior and governance contracts while implementing browser-native interaction, routing, and layout patterns from first principles (no desktop-mechanics carryover).
- All workspace and page surfaces inherit the canonical `Obsidian Folio` experience contract (dark-first Fluent 2 tokens, app-window adaptive states, single-fold defaults, keyboard-first accessibility); see `ui-premium-dark-blueprint-obsidian-folio.md`.
- Recall-first behavior from `UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` is normative when layout-only targeting would miss potential handwriting content.
1. Use run-based transcription architecture for reproducibility and auditability.
2. Use a layout-aware internal VLM as the primary transcription engine in v1.
3. Keep fallback engines pluggable so Kraken remains the required audited baseline and any TrOCR or DAN additions are explicitly allowlisted recovery paths under the same governance contract.
4. Treat confidence as first-class data for triage, heatmaps, and reviewer routing.
5. Transcript correction remains owned by Phase 4 even when later phases consume approved transcript outputs.
6. Persist only structured model output, aggregate confidence, and reviewer-visible suggestions; never persist hidden reasoning or chain-of-thought text.
7. The initial default transcription VLM is `Qwen2.5-VL-3B-Instruct`, but any replacement must satisfy the same structured-output and anchor-alignment contract.
8. Promoted transcription runs must provide token-level anchors (`token_id` + geometry + source link) for downstream search and redaction safety.

## Iteration Model
Build Phase 4 in seven iterations (`4.0` to `4.6`). Each iteration must ship usable capability while preserving provenance and no-egress constraints.

## Approved Starter Defaults

- primary transcription VLM: `Qwen2.5-VL-3B-Instruct`
- constrained assist LLM for reviewer-facing help: `Qwen3-4B`
- fallback HTR baseline: `Kraken`
- optional comparison VLMs may be evaluated later, but they do not replace the role contract or run schema

## Iteration 4.0: Transcription IA + UX Surfaces + Data Model

### Goal
Create dedicated transcription surfaces and run/result schemas before inference implementation.

### Web Client Work
Add a document-scoped `Transcription` section.

#### Routes
- `/projects/:projectId/documents/:documentId/transcription`
  - tabs:
    - `Overview`
    - `Triage`
    - `Runs`
    - `Artefacts` (Controlled-only internal run artefacts)
- `/projects/:projectId/documents/:documentId/transcription/runs/:runId`
- `/projects/:projectId/documents/:documentId/transcription/workspace?page={pageNumber}&runId={runId}&lineId={lineId}&tokenId={tokenId}&sourceKind={sourceKind}&sourceRefId={sourceRefId}`
  - `lineId` is optional and deep-links the workspace to a highlighted line from search or compare surfaces
  - `tokenId` is optional and deep-links to exact token highlight when token anchors are available
  - `sourceKind` and `sourceRefId` are optional deep-link helpers for rescue-candidate or page-window provenance when no stable line anchor exists

#### Information hierarchy
- `Overview`: current state and progress.
- `Triage`: where quality issues are concentrated.
- `Workspace`: focused read/edit verification surface.

### Backend Work
#### Tables
Add `transcription_runs`:

- `id`
- `project_id`
- `document_id`
- `input_preprocess_run_id`
- `input_layout_run_id`
- `input_layout_snapshot_hash`
- `engine` (`VLM_LINE_CONTEXT`, `REVIEW_COMPOSED`, fallback `KRAKEN_LINE`, later `TROCR_LINE`, `DAN_PAGE`)
- `model_id`
- `project_model_assignment_id` (nullable when the run uses a platform-approved model outside a project-scoped assignment)
- `prompt_template_id` (nullable for non-prompt fallback engines)
- `prompt_template_sha256` (nullable)
- `response_schema_version`
- `confidence_basis` (`MODEL_NATIVE | READ_AGREEMENT | FALLBACK_DISAGREEMENT`)
- `confidence_calibration_version`
- `params_json`
- `pipeline_version`
- `container_digest`
- `attempt_number`
- `supersedes_transcription_run_id` (nullable)
- `superseded_by_transcription_run_id` (nullable)
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `created_by`
- `created_at`
- `started_at`
- `finished_at`
- `canceled_by` (nullable)
- `canceled_at` (nullable)
- `failure_reason` (nullable)

Add `approved_models`:

- `id`
- `model_type` (`VLM | LLM | HTR`)
- `model_role` (`TRANSCRIPTION_PRIMARY | TRANSCRIPTION_FALLBACK | ASSIST`)
- `model_family`
- `model_version`
- `serving_interface` (`OPENAI_CHAT | OPENAI_EMBEDDING | ENGINE_NATIVE | RULES_NATIVE`)
- `engine_family`
- `deployment_unit`
- `artifact_subpath`
- `checksum_sha256`
- `runtime_profile`
- `response_contract_version`
- `metadata_json`
- `status` (`APPROVED | DEPRECATED | ROLLED_BACK`)
- `approved_by` (nullable)
- `approved_at` (nullable)
- `created_at`
- `updated_at`

This is the platform-approved model catalog. It is not project-scoped and is managed through governance controls rather than ad hoc document workflows. Phase 4 reads only the transcription-facing roles from this catalog; privacy, rules, and embedding roles remain governed outside this phase.

Add `page_transcription_results`:

- `run_id`
- `page_id`
- `page_index`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `pagexml_out_key`
- `pagexml_out_sha256`
- `raw_model_response_key` (Controlled-only structured response payload for VLM or fallback output)
- `raw_model_response_sha256`
- `hocr_out_key` (nullable; populated only for fallback engines that emit hOCR)
- `hocr_out_sha256` (nullable)
- `metrics_json`
- `warnings_json`
- `failure_reason` (nullable)
- `created_at`
- `updated_at`

Add `line_transcription_results`:

- `run_id`
- `page_id`
- `line_id`
- `text_diplomatic`
- `conf_line`
- `confidence_basis`
- `confidence_calibration_version`
- `alignment_json_key`
- `char_boxes_key` (nullable when the active engine does not emit char boxes)
- `schema_validation_status` (`VALID | FALLBACK_USED | INVALID`)
- `flags_json`
- `machine_output_sha256`
- `active_transcript_version_id` (nullable until a manual correction exists)
- `version_etag`
- `token_anchor_status` (`CURRENT | STALE | REFRESH_REQUIRED`)
- `created_at`
- `updated_at`

Add `token_transcription_results`:

- `run_id`
- `page_id`
- `line_id` (nullable)
- `token_id`
- `token_index`
- `token_text`
- `token_confidence`
- `bbox_json` (nullable)
- `polygon_json` (nullable)
- `source_kind` (`LINE | RESCUE_CANDIDATE | PAGE_WINDOW`)
- `source_ref_id`
- `projection_basis` (`ENGINE_OUTPUT | REVIEW_CORRECTED`)
- `created_at`
- `updated_at`

Add `transcript_versions`:

- `id`
- `run_id`
- `page_id`
- `line_id`
- `base_version_id` (nullable)
- `superseded_by_version_id` (nullable)
- `version_etag`
- `text_diplomatic`
- `editor_user_id`
- `edit_reason` (nullable)
- `created_at`

Add `document_transcription_projections`:

- `document_id`
- `project_id`
- `active_transcription_run_id` (nullable until a successful run is explicitly promoted)
- `active_layout_run_id` (nullable until a transcription run is first activated)
- `active_layout_snapshot_hash` (nullable until a transcription run is first activated)
- `active_preprocess_run_id` (nullable until a transcription run is first activated)
- `downstream_redaction_state` (`NOT_STARTED | CURRENT | STALE`)
- `downstream_redaction_invalidated_at` (nullable)
- `downstream_redaction_invalidated_reason` (nullable)
- `updated_at`

Rules:
- transcription overview, triage, and workspace-default reads use `document_transcription_projections.active_transcription_run_id` when a caller does not request a specific run
- reruns append a new `transcription_runs` row, increment `attempt_number`, point `supersedes_transcription_run_id` at the replaced attempt, and record the forward lineage link on the replaced row through `superseded_by_transcription_run_id`
- activating a run updates `document_transcription_projections.active_transcription_run_id` plus the linked `active_layout_run_id` and `active_preprocess_run_id` values without mutating historical run rows
- activating a run also pins `active_layout_snapshot_hash` from the consumed layout basis so later privacy, provenance, and search phases can reference an immutable document-wide layout snapshot even after page-level layout edits
- every run launched through a project-scoped assignment persists both the resolved `project_model_assignment_id` and the underlying `model_id`, so later provenance can reconstruct the role assignment as well as the approved model artefact
- activating a transcription run sets `document_layout_projections.downstream_transcription_state = CURRENT` for the consumed active layout generation and resets `downstream_redaction_state` to `NOT_STARTED` until a privacy run is activated against the new transcript basis
- `params_json` must persist versioned thresholds for v1, including `review_confidence_threshold = 0.85` and `fallback_confidence_threshold = 0.72`, unless an approved replacement profile explicitly overrides them
- every surfaced `conf_line` is normalized onto `[0,1]` using the declared `confidence_calibration_version`; triage, fallback, and reviewer-routing thresholds operate only on the normalized value
- activating a transcription run requires token-anchor materialization for every page included in the promoted transcript basis; pages previously marked `NEEDS_MANUAL_REVIEW` must either be manually corrected into tokenized output or keep the run non-activatable for downstream privacy/search work
- any page or line with `token_anchor_status != CURRENT` blocks activation until a refresh step materializes replacement `token_transcription_results`

Add `transcription_output_projections`:

- `run_id`
- `document_id`
- `page_id`
- `corrected_pagexml_key`
- `corrected_pagexml_sha256`
- `corrected_text_sha256`
- `source_pagexml_sha256`
- `updated_at`

Add `transcription_compare_decisions`:

- `id`
- `document_id`
- `base_run_id`
- `candidate_run_id`
- `page_id`
- `line_id` (nullable when the decision applies to a region-level diff)
- `token_id` (nullable when the decision applies at exact-token granularity)
- `decision` (`KEEP_BASE | PROMOTE_CANDIDATE`)
- `decision_etag`
- `decided_by`
- `decided_at`
- `decision_reason` (nullable)

Compare-decision rule:

- at most one current `transcription_compare_decisions` row may exist per `(document_id, base_run_id, candidate_run_id, page_id, line_id, token_id)` tuple; later changes for the same diff target update the current projection only through `decision_etag`-guarded writes while the full chronology remains in `transcription_compare_decision_events`

Add `transcription_compare_decision_events`:

- `id`
- `document_id`
- `base_run_id`
- `candidate_run_id`
- `page_id`
- `line_id` (nullable when the decision applies to a region-level diff)
- `token_id` (nullable when the decision applies at exact-token granularity)
- `from_decision` (nullable)
- `to_decision`
- `actor_user_id`
- `reason` (nullable)
- `created_at`

Add `transcript_variant_layers`:

- `id`
- `run_id`
- `page_id`
- `variant_kind` (`NORMALISED`)
- `status` (`QUEUED | READY | FAILED`)
- `base_transcript_version_id` (nullable when the layer is derived from more than one line version)
- `base_version_set_sha256`
- `base_projection_sha256`
- `variant_text_key`
- `variant_text_sha256`
- `created_by`
- `created_at`
- `updated_at`

Add `transcript_variant_suggestions`:

- `id`
- `variant_layer_id`
- `page_id`
- `line_id`
- `suggestion_text`
- `confidence`
- `status` (`PENDING | ACCEPTED | REJECTED`)
- `decided_by` (nullable)
- `decided_at` (nullable)
- `decision_reason` (nullable)
- `created_at`

Add `transcript_variant_suggestion_events`:

- `id`
- `suggestion_id`
- `from_status` (nullable)
- `to_status`
- `actor_user_id`
- `reason` (nullable)
- `created_at`

#### APIs
- `GET /projects/{projectId}/documents/{documentId}/transcription/overview`
- `GET /projects/{projectId}/documents/{documentId}/transcription/triage?status={status}&confidenceBelow={threshold}&page={pageNumber}`
- `POST /projects/{projectId}/documents/{documentId}/transcription-runs`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/active`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/status`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages`
- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/activate`
  - allowed only for `SUCCEEDED` runs and updates `document_transcription_projections.active_transcription_run_id`, `active_layout_run_id`, and `active_preprocess_run_id` without mutating historical run rows
- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/cancel`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/lines`
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/tokens`
- `PATCH /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/lines/{lineId}`
  - requires the caller's current `version_etag`, appends a new `transcript_versions` row, leaves engine output immutable, and returns the newly active version
  - rejects stale `version_etag` values instead of overwriting a newer transcript correction

### Tests and Gates (Iteration 4.0)
- RBAC: only `PROJECT_LEAD`, `RESEARCHER`, or `REVIEWER` can view transcription surfaces; run, cancel, and edit actions are limited to `PROJECT_LEAD`, `REVIEWER`, or `ADMIN`.
- Rerun lineage: new transcription attempts increment `attempt_number` and persist both `supersedes_transcription_run_id` and `superseded_by_transcription_run_id`.
- Overview, triage, and workspace defaults resolve through the activated transcription projection, and in-flight progress polls the dedicated run-status endpoint instead of repeatedly fetching full run detail.
- Audit events: `TRANSCRIPTION_OVERVIEW_VIEWED`, `TRANSCRIPTION_TRIAGE_VIEWED`, `TRANSCRIPTION_RUN_CREATED`, `TRANSCRIPTION_RUN_STARTED`, `TRANSCRIPTION_RUN_FINISHED`, `TRANSCRIPTION_RUN_FAILED`, `TRANSCRIPTION_RUN_CANCELED`, `TRANSCRIPTION_RUN_VIEWED`, `TRANSCRIPTION_RUN_STATUS_VIEWED`, `TRANSCRIPTION_ACTIVE_RUN_VIEWED`, and `TRANSCRIPTION_RUN_ACTIVATED` when applicable.
- Accessibility and visual regression for Overview/Triage/Runs screens.
- No-egress regression: worker external calls hard fail and are audited, and transcription workers may call only the approved internal transcription service or fallback adapter resolved through the model service map.
- token-anchor gate: promoted runs expose stable token IDs with geometry and source links suitable for search highlight and redaction attachment.
- activation persists the consumed `input_layout_snapshot_hash`, and runs with any `token_anchor_status != CURRENT` are rejected for activation
- line-correction writes reject stale `version_etag` values instead of silently overwriting newer reviewer edits

### Exit Criteria (Iteration 4.0)
Transcription area and run plumbing are production-ready for inference rollout.

## Iteration 4.1: Primary VLM Inference v1 (Line Context + Structured Output)

### Goal
Generate diplomatic line-level transcripts aligned to Phase 3 layout lines through a layout-aware VLM served by the approved internal transcription service.

### Backend Work
#### Jobs
- `TRANSCRIBE_DOCUMENT(run_id)`
- `TRANSCRIBE_PAGE(run_id, page_id)`
- `FINALIZE_TRANSCRIPTION_RUN(run_id)`

#### Per-page flow
1. Load preprocessed page image and layout PAGE-XML.
2. Load Phase 3 line crops, optional region crops, page thumbnail, per-line context-window artefacts, and approved rescue candidates.
3. Call the approved internal transcription service with a fixed structured prompt for each target line, rescue candidate, or page-window segment.
4. Validate the structured response against the configured response schema and existing `line_id` or rescue source anchors.
5. Emit PAGE-XML as canonical transcript output and persist the raw structured response in Controlled storage.
6. Materialize token-level anchors (`token_id`, geometry, source link) for downstream search and redaction.
7. Mark consumed Phase 3 rescue candidates `RESOLVED` only after their accepted input has been transcribed successfully and anchored into the output basis.
8. Route schema or anchor-validation failures to fallback handling instead of silently persisting invalid text.
9. Persist outputs and SHA-256 hashes.

#### Storage
- `controlled/derived/{project_id}/{document_id}/transcription/{run_id}/page/{page_index}.xml`
- `controlled/derived/{project_id}/{document_id}/transcription/{run_id}/page/{page_index}.response.json`
- `controlled/derived/{project_id}/{document_id}/transcription/{run_id}/page/{page_index}.hocr` (fallback-only when emitted)

### Web Client Work
- `Runs` tab: launch run and view status progress.
- `Overview` tab: summary cards for pages/lines/failures.
- Workspace (read-only): transcription panel in reading order; line click highlights geometry.

### Tests and Gates (Iteration 4.1)
#### Backend
- Determinism: same input/model/prompt template/params gives the same structured output hash in the same container.
- Idempotency: retry page job does not duplicate result rows.
- Format sanity: PAGE-XML parse success with expected `TextLine/TextEquiv` content.
- Structured output sanity: every persisted line maps back to a valid `line_id` from the active layout version.
- Replacement safety: a candidate VLM cannot be promoted unless it passes the same response-contract and anchor-alignment test pack as the current approved model.
- token-anchor integrity: persisted tokens carry stable `token_id` plus valid geometry and source references.
- activation is blocked when any page in the promoted transcript basis lacks token anchors, including pages that previously entered from `NEEDS_MANUAL_REVIEW` state.

#### web-surface
- E2E: run transcription and verify multi-page transcript rendering.

### Exit Criteria (Iteration 4.1)
Full document VLM transcription runs reliably, produces schema-valid outputs, and is visible in workspace.

## Iteration 4.2: Confidence + Alignment v1

### Goal
Quantify uncertainty from VLM output and direct reviewers to high-risk lines first.

### Backend Work
- Use model-native confidence or logprob signals when the active VLM provides them.
- Otherwise derive `conf_line` from fixed internal agreement reads such as `crop-only` versus `crop+context`.
- Optionally compute fallback-engine disagreement as an additional review signal without mutating the primary VLM output.
- Persist aggregate confidence, validation flags, and compact alignment payloads.
- Persist char-box confidence payloads only when the active engine provides them.
- Calibration contract:
  - `MODEL_NATIVE` scores must be mapped through a versioned per-model monotonic calibration table before they populate `conf_line`
  - `READ_AGREEMENT` scores must be derived from deterministic string-agreement features and then mapped through the same style of versioned calibration table
  - `FALLBACK_DISAGREEMENT` may contribute to reviewer routing, but it must still be normalized through the declared calibration version before it is compared with other `conf_line` values

#### Quality metrics
- percent lines below threshold
- low-confidence page distribution
- segmentation mismatch warnings (line exists, empty text)
- structured-response validation failures
- fallback invocation count

### Web Client Work
#### Triage tab
- columns:
  - page number
  - low-confidence line count
  - min/avg confidence
  - issues
  - status
- filters:
  - low-confidence only
  - failed only
  - confidence below threshold

#### Workspace enhancements
- toggle: highlight low-confidence content
- inspector shows selected line confidence
- per-character confidence visual cues
- keyboard action: `Next low-confidence line`

### Tests and Gates (Iteration 4.2)
- Unit: structured-response validator handles malformed spans or missing anchors safely.
- Unit: agreement-based confidence yields deterministic `conf_line` for the same crop pair.
- Unit: basis-specific confidence calibrators map raw model-native, agreement, and fallback-disagreement signals onto the same normalized `[0,1]` scale.
- Integration: confidence output populates DB and triage counts.
- E2E: low-confidence filters and highlights match backend counts.

### Exit Criteria (Iteration 4.2)
Reviewers can navigate directly to uncertainty hotspots.

## Iteration 4.3: Human Review and Correction Workspace v1

### Goal
Deliver an editor-grade correction workspace with append-only provenance.

### Web Client Work
#### Workspace layout
- left rail: page filmstrip
- center canvas: image with overlays
- right panel: transcript editor

#### Editor capabilities
- mode switch:
  - `Reading order`
  - `As on page`
- virtualized line list
- inline line editing
- line crop preview for precise verification

#### Toolbar and ergonomics
- save status indicator
- next/previous line
- next issue navigation
- keyboard-first controls:
  - `Enter`: save and next
  - `Ctrl/Cmd+S`: save
  - `Up/Down`: line navigation
- local undo/redo
- per-line edited indicator

### Backend Work
- Append-only versioning for all edits.
- Never overwrite model output directly.
- Optimistic concurrency with `version_etag` conflict handling.
- Each correction appends a new `transcript_versions` row, updates `line_transcription_results.active_transcript_version_id`, and marks the previous active version as superseded through `transcript_versions.superseded_by_version_id`.
- line-level correction writes require the caller's current `version_etag`; stale correction attempts are rejected instead of silently replacing a newer reviewer edit
- Update canonical PAGE-XML `TextEquiv` with approved diplomatic text and refresh `transcription_output_projections` so later phases consume a stable corrected projection instead of rebuilding from edit history ad hoc.
- Corrections that change token boundaries, token text, or token geometry must append refreshed `token_transcription_results` rows for the affected line or page with `projection_basis = REVIEW_CORRECTED`, or else mark `line_transcription_results.token_anchor_status = REFRESH_REQUIRED` and block downstream activation until refreshed token projections exist.
- `POST /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/refresh-token-anchors`
  - available to `PROJECT_LEAD`, `REVIEWER`, or `ADMIN`
  - regenerates token projections for edited pages or lines and clears `token_anchor_status` back to `CURRENT` only after replacement anchors are persisted
- if the edited transcript belongs to the active transcription run, set `document_transcription_projections.downstream_redaction_state = STALE` and persist `downstream_redaction_invalidated_at` plus a reason so Phase 5 and later governance/export flows cannot silently keep using stale privacy outputs
- Never persist chain-of-thought or other hidden reasoning text from assist models; keep only structured output, confidence, and reviewer-visible suggestions.
- Only `REVIEWER`, `PROJECT_LEAD`, or `ADMIN` can save transcript corrections.
- Audit events:
  - `TRANSCRIPT_LINE_CORRECTED`
  - `TRANSCRIPT_EDIT_CONFLICT_DETECTED`
  - `TRANSCRIPT_TOKEN_ANCHORS_REFRESHED`
  - `TRANSCRIPT_DOWNSTREAM_INVALIDATED` when an edit makes the active privacy basis stale

### Tests and Gates (Iteration 4.3)
- Unit: edit operations generate version records and accurate diffs.
- Integration: concurrent edit conflicts detected and surfaced.
- Integration: editing the active transcription run marks downstream redaction state as `STALE` until Phase 5 activates a new privacy run against the corrected transcript basis.
- Integration: `refresh-token-anchors` regenerates replacement token projections and clears `token_anchor_status` so blocked runs can become activatable again.
- E2E: edit persists after refresh; audit trail records actor and change.

### Exit Criteria (Iteration 4.3)
`PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can correct transcripts at scale with reliable provenance.

## Iteration 4.4: Model Registry + Training Loop Foundations

### Goal
Introduce safe transcription-model assignment and training-dataset management on top of the platform-approved model catalog.

### Backend Work
- Add `project_model_assignments`:
  - `id`
  - `project_id`
  - `model_role` (`TRANSCRIPTION_PRIMARY | TRANSCRIPTION_FALLBACK | ASSIST`)
  - `approved_model_id`
  - `status` (`DRAFT | ACTIVE | RETIRED`)
  - `supersedes_assignment_id` (nullable)
  - `superseded_by_assignment_id` (nullable)
  - `assignment_reason` (nullable)
  - `created_by`
  - `created_at`
  - `activated_by` (nullable)
  - `activated_at` (nullable)
  - `retired_by` (nullable)
  - `retired_at` (nullable)
- Project assignments may reference only rows from `approved_models`.
- Project assignments may reference only `approved_models` rows whose current `status = APPROVED`; `DEPRECATED` and `ROLLED_BACK` rows remain valid historical lineage for old runs but cannot be newly assigned or re-activated.
- at most one `ACTIVE` `project_model_assignments` row may exist per `(project_id, model_role)`; activating a new assignment for a role must retire or supersede the previous active row in that same role, record `supersedes_assignment_id` on the new row when supersession is used, and write the forward link on the replaced row through `superseded_by_assignment_id`
- Add `training_datasets`:
  - `id`
  - `project_id`
  - `source_approved_model_id` (nullable)
  - `project_model_assignment_id` (nullable)
  - `dataset_kind` (`TRANSCRIPTION_TRAINING`)
  - `page_count`
  - `storage_key`
  - `dataset_sha256`
  - `created_by`
  - `created_at`
- Internal dataset packaging pipeline for training subsets:
  - PAGE-XML + corresponding images + line or context artefacts required by the active engine family

### Web Client Work
- project-scoped routes:
  - `/projects/:projectId/model-assignments`
  - `/projects/:projectId/model-assignments/:assignmentId`
  - `/projects/:projectId/model-assignments/:assignmentId/datasets`
- Minimal Models screen (`PROJECT_LEAD`, `REVIEWER`, and `ADMIN` can read; mutate actions stay limited to `PROJECT_LEAD` and `ADMIN`):
  - list approved models by role and current project assignment
  - show run usage links
  - explicit activate and retire actions for eligible approved-model assignments
  - dataset lineage links for approved training subsets

APIs:
- `GET /projects/{projectId}/model-assignments`
- `POST /projects/{projectId}/model-assignments`
- `GET /projects/{projectId}/model-assignments/{assignmentId}`
- `GET /projects/{projectId}/model-assignments/{assignmentId}/datasets`
- `POST /projects/{projectId}/model-assignments/{assignmentId}/activate`
- `POST /projects/{projectId}/model-assignments/{assignmentId}/retire`

### Tests and Gates (Iteration 4.4)
- Registry integrity checksums match stored model artefacts.
- Approved models can only be assigned into compatible transcription roles such as `TRANSCRIPTION_PRIMARY`, `TRANSCRIPTION_FALLBACK`, or `ASSIST`.
- project assignment creation and activation reject `approved_models` rows whose `status != APPROVED`
- RBAC allows assignment-list and assignment-detail reads for `PROJECT_LEAD`, `REVIEWER`, and `ADMIN`, while restricting add, activate, or retire actions to `PROJECT_LEAD` and `ADMIN`.
- Run records include `project_model_assignment_id` when applicable, plus model checksum and container digest.
- Role-map updates cannot change workflow routes or run-table semantics; they only switch the approved deployment behind a stable role.
- activating a project model assignment retires or supersedes any previous `ACTIVE` assignment in the same `(project_id, model_role)` scope
- assignment supersession lineage persists through `supersedes_assignment_id` and `superseded_by_assignment_id` when a new active assignment replaces an older one
- Audit events emitted:
  - `PROJECT_MODEL_ASSIGNMENT_CREATED`
  - `MODEL_ASSIGNMENT_LIST_VIEWED`
  - `MODEL_ASSIGNMENT_DETAIL_VIEWED`
  - `TRAINING_DATASET_VIEWED`
  - `PROJECT_MODEL_ACTIVATED`
  - `PROJECT_MODEL_RETIRED`

### Exit Criteria (Iteration 4.4)
Multiple transcription models can be managed and audited safely.

## Iteration 4.5: Fallback + Comparison Engines (Kraken, TrOCR, DAN)

### Goal
Support hard cases with audited fallback and comparison engines while preserving the VLM-first workflow and controlled review.

### Backend Work
- Fallback invocation rules:
  - invoke `KRAKEN_LINE` when structured-response validation fails, anchors cannot be resolved, or normalized `conf_line < params_json.fallback_confidence_threshold`
  - preserve the original VLM output as immutable source data even when the fallback path is invoked
- Plug-in engine interface for:
  - `KRAKEN_LINE`
  - optional `TROCR_LINE`
  - optional `DAN_PAGE`
- `TROCR_LINE` and `DAN_PAGE` remain disabled until each engine is added to the environment-approved catalog, mapped through the stable `TRANSCRIPTION_FALLBACK` role contract, and assigned through the same Phase 4 transcription-model governance path.
- Ensure outputs are normalised into existing run/result schema.
- Comparison API:
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`
  - returns line-level or token-level diffs, changed-confidence summaries, and engine metadata
  - rejects compare or finalize requests unless `baseRunId` and `candidateRunId` share the same `input_preprocess_run_id`, `input_layout_run_id`, and `input_layout_snapshot_hash`, so reviewed diffs stay within one page/line anchor space
  - `POST /projects/{projectId}/documents/{documentId}/transcription-runs/compare/decisions`
    - requires the current `decision_etag`, records explicit keep-or-promote decisions in `transcription_compare_decisions`, appends `transcription_compare_decision_events`, and rejects stale compare writes instead of silently overwriting a newer reviewed decision
  - `POST /projects/{projectId}/documents/{documentId}/transcription-runs/compare/finalize`
    - creates a new `REVIEW_COMPOSED` transcription run whose `params_json` captures `baseRunId`, `candidateRunId`, the compare-decision snapshot hash, and any page scope; the finalized run rebuilds PAGE-XML and token anchors from the approved decisions instead of mutating either source run in place
    - finalization reads the append-only `transcription_compare_decision_events` stream plus the current projection so the approved decision set remains reproducible
- Compare surfaces are readable by `PROJECT_LEAD`, `REVIEWER`, and `ADMIN`; any explicit accept or promote action remains limited to `PROJECT_LEAD`, `REVIEWER`, or `ADMIN`.
- Audit event:
  - `TRANSCRIPTION_RUN_COMPARE_VIEWED`
  - `TRANSCRIPTION_COMPARE_DECISION_RECORDED`
  - `TRANSCRIPTION_COMPARE_FINALIZED`

### Web Client Work
- compare route:
  - `/projects/:projectId/documents/:documentId/transcription/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}&page={pageNumber}&lineId={lineId}&tokenId={tokenId}`
- Workspace compare mode:
  - run A vs run B or engine A vs engine B
  - line-level or token-level diff
  - explicit user acceptance per line, token, or region
- No automatic merge or silent promotion.

### Tests and Gates (Iteration 4.5)
- ML regression must not degrade the baseline gold set.
- Fallback tests verify Kraken can be invoked on schema failure, validation failure, or confidence below threshold without mutating the original VLM output path.
- Safety gate: outputs from new engine paths require user confirmation.
- Compare finalization tests verify that approved promote decisions materialize a new `REVIEW_COMPOSED` run with fresh PAGE-XML and token anchors, while the source runs remain immutable.
- compare decisions append `transcription_compare_decision_events`, and stale `decision_etag` writes are rejected instead of silently overwriting a reviewed decision
- compare and finalize requests are rejected when the base and candidate runs do not share the same preprocess and layout basis

### Exit Criteria (Iteration 4.5)
System can escalate to stronger engines on difficult pages without uncontrolled changes.

## Iteration 4.6: Constrained Assist + Normalised View (Optional)

### Goal
Improve consistency through reviewer-controlled suggestions while preserving diplomatic record integrity.

### Backend Work
- Suggestion-only assist layer triggered by:
  - low-confidence spans
  - known systematic error patterns
- Must run from internal rules or models only; no external AI API path.
- Enforce explicit accept/reject workflow.
- Keep diplomatic transcript primary.
- Reuse the existing `transcript_variant_layers` table and link `NORMALISED` output explicitly to `transcript_versions` so it remains separate from diplomatic text.
- Store normalised variant as separate layer, never overwrite diplomatic baseline.
- Persist only reviewer-visible suggestion text, confidence, and audit metadata; never persist hidden reasoning text.
- every `transcript_variant_layer` must point at the exact source basis it was derived from: use `base_transcript_version_id` for single-line layers and `base_version_set_sha256` for page-level or multi-line layers; regenerated normalised layers append a new row instead of rebinding an existing layer to a newer diplomatic correction
- APIs:
  - `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/variant-layers`
  - `POST /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/variant-layers/{variantKind}/suggestions/{suggestionId}/decision`
    - appends a `transcript_variant_suggestion_events` row, updates the matching `transcript_variant_suggestions` projection, and never mutates the diplomatic base text
- Audit events:
  - `TRANSCRIPT_VARIANT_LAYER_VIEWED` when a non-diplomatic layer is opened
  - `TRANSCRIPT_ASSIST_DECISION_RECORDED` when a suggestion is accepted or rejected

### Web Client Work
- Collapsed Assist panel with suggestion list and reasons.
- Per-suggestion accept/reject controls.
- `Diplomatic` vs `Normalised` view toggle.

### Tests and Gates (Iteration 4.6)
- Assist cannot auto-apply any change.
- Assist cannot modify high-confidence lines unless user explicitly opts in.
- Audit every suggestion and decision.
- normalised layers remain pinned to `base_transcript_version_id` for single-line layers or `base_version_set_sha256` for page-level layers, so later diplomatic corrections do not silently rewrite or relabel earlier assist outputs

### Exit Criteria (Iteration 4.6)
Assist provides consistency gains without compromising auditability or research integrity.

## Handoff to Later Phases
- Phase 5 uses `document_transcription_projections.active_transcription_run_id` plus token-level anchors and layout links as the basis for privacy review.
- Later phases may consume transcript versions as inputs, but transcript correction remains owned by Phase 4.

## Phase 4 Definition of Done
Move to Phase 5 only when all are true:

1. Transcription runs produce canonical line-level PAGE-XML outputs.
2. Confidence and alignment signals are captured and surfaced (line-level minimum, char-level preferred).
3. Workspace supports professional correction with versioning and audit trails.
4. VLM primary-path and fallback-engine plumbing coexist even if a single approved VLM is the default active engine.
5. Optional assist mode is reviewer-controlled and fully auditable.
6. Token-level anchors are persisted with stable IDs and geometry suitable for exact downstream highlight and masking.

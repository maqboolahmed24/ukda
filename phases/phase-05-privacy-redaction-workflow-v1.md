# Phase 5: Privacy and Redaction Review Workflow v1 - The Masking

> Status: ACTIVE
> Web Root: /web
> Active Phase Ceiling: 11
> Execution Policy: Phase 0 through Phase 11 are ACTIVE for this prompt program.
> Web Translation Overlay (ACTIVE): preserve existing workflow intent and phase semantics while translating any legacy desktop or WinUI terms into equivalent browser-native routes, layouts, and interaction patterns under /web.

## Phase Objective
Turn Phase 4 transcripts into reviewable safeguarded previews by detecting direct identifiers with rules plus local NER, applying baseline policy-snapshot masking decisions, and giving reviewers a fast, auditable workspace for privacy decisions.

## Entry Criteria
Start Phase 5 only when all are true:
- corrected Phase 4 transcript outputs exist for the target document
- transcript correction for the working run is complete enough for privacy review
- line, layout, or token anchors needed for span highlighting are available
- a non-editable baseline privacy policy snapshot exists for the project so Phase 5 can pin deterministic masking defaults before Phase 7 policy authoring begins

## Scope Boundary
Phase 5 stops at reviewed safeguarded preview generation.

Out of scope for this phase:
- manifest generation and Controlled-only evidence ledgers (Phase 6)
- advanced policy authoring, pseudonym registries, and indirect-identifier generalisation (Phase 7)
- external disclosure review and egress (Phase 8)

## Phase 5 Non-Negotiables
- Secure web application is the active delivery target: preserve phase behavior and governance contracts while implementing browser-native interaction, routing, and layout patterns from first principles (no desktop-mechanics carryover).
- All workspace and page surfaces inherit the canonical `Obsidian Folio` experience contract (dark-first Fluent 2 tokens, app-window adaptive states, single-fold defaults, keyboard-first accessibility); see `ui-premium-dark-blueprint-obsidian-folio.md`.
- Recall-first behavior from `UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` is normative for token-linked redaction and conservative area-mask fallback.
1. Privacy decisions are run-based and reproducible.
2. The safeguarded preview never becomes an uncontrolled export path.
3. Reviewer decisions are append-only and auditable.
4. Phase 5 handles direct identifiers first; broader disclosure-control policy comes later.
5. Any local LLM assistance in Phase 5 is conservative, reviewer-facing, and never a silent auto-release decision path.
6. The starter privacy stack is role-separated: `Presidio` rules remain authoritative, `GLiNER` provides local NER support, and `Qwen3-4B` may assist only with bounded reviewer-facing explanation.
7. Findings must attach to token anchors when available; unreadable sensitive handwriting may use audited conservative area masks.

## Iteration Model
Build Phase 5 in four iterations (`5.0` to `5.3`). Each iteration must ship a working privacy-review slice without taking ownership of Phase 6 through Phase 8 deliverables.

## Approved Starter Defaults

- privacy rules engine: `Presidio`
- privacy NER model: `GLiNER-small-v2.1` or `GLiNER-medium-v2.1`
- optional bounded assist model: `Qwen3-4B`
- all three remain replaceable by role if the policy contract and review workflow stay unchanged

## Iteration 5.0: Privacy IA + Run Model + Read-Only Surfaces

### Goal
Create a dedicated privacy area, a clean run model, and enough UI structure to support reviewer workflows before detector logic goes live.

### Web Client Work
#### Routes
- `/projects/:projectId/documents/:documentId/privacy`
  - tabs:
    - `Overview`
    - `Triage`
    - `Runs`
- `/projects/:projectId/documents/:documentId/privacy/runs/:runId`
- `/projects/:projectId/documents/:documentId/privacy/runs/:runId/events`
- `/projects/:projectId/documents/:documentId/privacy/workspace?page={pageNumber}&runId={runId}&findingId={findingId}&lineId={lineId}&tokenId={tokenId}`
  - `findingId`, `lineId`, and `tokenId` are optional deep-link helpers for triage and compare surfaces
- `/projects/:projectId/documents/:documentId/privacy/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}&page={pageNumber}&findingId={findingId}&lineId={lineId}&tokenId={tokenId}`
  - `page`, `findingId`, `lineId`, and `tokenId` are optional deep-link helpers for compare reviews

#### Overview
- summary cards for the active run:
  - findings by category
  - unresolved findings
  - pages blocked for review
  - safeguarded-preview readiness
- primary CTA: `Create privacy review run`
- overflow actions: `Compare runs`, `Open active workspace`, `Complete review`
- overview cards and `Open active workspace` resolve through the explicit active-run projection rather than inferring a latest run from history
- run detail and review-status pages read from `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}`, `/review`, and `/events`

#### Triage
- table-first design
- columns:
  - page number
  - findings
  - unresolved items
  - review status
  - last reviewed by
- filters:
  - category
  - unresolved only
  - direct identifiers only
- row selection opens a details drawer:
  - page preview
  - top findings
  - `Open in workspace`

#### Workspace shell
- Inherits the Phase 1 Pattern D single-fold workspace contract with adaptive states (`Expanded | Balanced | Compact | Focus`).
- left rail: page thumbnails and review status
- center canvas: page image with line or span highlight overlay
- right panel: transcript and findings list
- top toolbar:
  - previous or next page
  - `Next unresolved`
  - show or hide highlights
  - `Show safeguarded preview`

### Backend Work
#### Tables
Add `redaction_runs`:
- `id`
- `project_id`
- `document_id`
- `input_transcription_run_id`
- `input_layout_run_id` (nullable if line geometry already materialised elsewhere)
- `run_kind` (`BASELINE | POLICY_RERUN`)
- `supersedes_redaction_run_id` (nullable)
- `superseded_by_redaction_run_id` (nullable)
- `policy_snapshot_id`
- `policy_snapshot_json`
- `policy_snapshot_hash`
- `policy_id` (nullable until explicit Phase 7 policy lineage exists)
- `policy_family_id` (nullable until explicit Phase 7 policy lineage exists)
- `policy_version` (nullable until explicit Phase 7 policy lineage exists)
- policy snapshot fields are captured once at run creation and never mutated in place
- `detectors_version`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `created_by`
- `created_at`
- `started_at`
- `finished_at`
- `failure_reason` (nullable)

Add `redaction_findings`:
- `id`
- `run_id`
- `page_id`
- `line_id` (nullable when a detection is page-scoped or does not resolve to a single line anchor)
- `category`
- `span_start` (nullable when the finding is geometry-only or page-scoped without canonical text offsets)
- `span_end` (nullable when the finding is geometry-only or page-scoped without canonical text offsets)
- `span_basis_kind` (`LINE_TEXT | PAGE_WINDOW_TEXT | NONE`)
- `span_basis_ref` (nullable; uses `line_id` for `LINE_TEXT` and `source_ref_id` for `PAGE_WINDOW_TEXT`)
- `confidence`
- `basis_primary` (`RULE | NER | HEURISTIC`)
- `basis_secondary_json` (nullable)
- `assist_explanation_key` (nullable; reviewer-visible bounded explanation only)
- `assist_explanation_sha256` (nullable)
- `bbox_refs`
- `token_refs_json` (nullable; token IDs plus optional per-token geometry refs)
- `area_mask_id` (nullable; set when conservative geometry masking is used)
- `decision_status` (`AUTO_APPLIED | NEEDS_REVIEW | APPROVED | OVERRIDDEN | FALSE_POSITIVE`)
- `override_risk_classification` (`STANDARD | HIGH`) (nullable until an override is proposed or applied)
- `override_risk_reason_codes_json` (nullable)
- `decision_by` (nullable until a reviewer or auto-application resolves the finding)
- `decision_at` (nullable until a reviewer or auto-application resolves the finding)
- `decision_reason` (required on override)
- `decision_etag`
- `updated_at`

Add `redaction_area_masks`:
- `id`
- `run_id`
- `page_id`
- `geometry_json`
- `mask_reason`
- `version_etag`
- `supersedes_area_mask_id` (nullable)
- `superseded_by_area_mask_id` (nullable)
- `created_by`
- `created_at`
- `updated_at`

Add `redaction_decision_events`:
- `id`
- `run_id`
- `page_id`
- `finding_id`
- `from_decision_status` (nullable)
- `to_decision_status`
- `action_type` (`MASK`, later `PSEUDONYMIZE` or `GENERALIZE`)
- `area_mask_id` (nullable)
- `actor_user_id`
- `reason` (nullable)
- `created_at`

Add `redaction_page_reviews`:
- `run_id`
- `page_id`
- `review_status` (`NOT_STARTED | IN_REVIEW | APPROVED | CHANGES_REQUESTED`)
- `review_etag`
- `first_reviewed_by`
- `first_reviewed_at`
- `requires_second_review`
- `second_review_status` (`NOT_REQUIRED | PENDING | APPROVED | CHANGES_REQUESTED`)
- `second_reviewed_by`
- `second_reviewed_at`
- `updated_at`

Add `redaction_page_review_events`:
- `id`
- `run_id`
- `page_id`
- `event_type` (`PAGE_OPENED | PAGE_REVIEW_STARTED | PAGE_APPROVED | CHANGES_REQUESTED | SECOND_REVIEW_REQUIRED | SECOND_REVIEW_APPROVED | SECOND_REVIEW_CHANGES_REQUESTED`)
- `actor_user_id`
- `reason` (nullable)
- `created_at`

Add `redaction_run_reviews`:
- `run_id`
- `review_status` (`NOT_READY | IN_REVIEW | APPROVED | CHANGES_REQUESTED`)
- `review_started_by` (nullable)
- `review_started_at` (nullable)
- `approved_by` (nullable)
- `approved_at` (nullable)
- `approved_snapshot_key` (nullable)
- `approved_snapshot_sha256` (nullable)
- `locked_at` (nullable)
- `updated_at`

Run review rules:
- initialize `redaction_run_reviews.review_status` as `NOT_READY`
- move to `IN_REVIEW` only when a reviewer explicitly starts run completion for a run whose pages are all review-eligible
- allow transitions only to `APPROVED` or `CHANGES_REQUESTED` from that active review state
- transitioning to `APPROVED` computes a deterministic snapshot over current finding decisions, area-mask revision refs, page-review projections, and run-level safeguarded output references, persists that immutable snapshot to `approved_snapshot_key` plus `approved_snapshot_sha256`, and locks the run against further decision edits
- once `review_status = APPROVED`, finding decisions, page reviews, and area-mask revisions for that run are immutable; any further reviewer changes require a new successor run instead of mutating the approved decision set in place

Add `document_redaction_projections`:
- `document_id`
- `project_id`
- `active_redaction_run_id` (nullable until an approved run is explicitly activated)
- `active_transcription_run_id`
- `active_layout_run_id`
- `active_policy_snapshot_id`
- `updated_at`

Add `redaction_run_review_events`:
- `id`
- `run_id`
- `event_type` (`RUN_REVIEW_OPENED | RUN_APPROVED | RUN_CHANGES_REQUESTED`)
- `actor_user_id`
- `reason` (nullable)
- `created_at`

Run and page event reads:
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/events` returns an append-only merged timeline over `redaction_decision_events`, `redaction_page_review_events`, and `redaction_run_review_events`; timeline order is defined by `(created_at, source_table_precedence, id)` where precedence is `redaction_decision_events -> redaction_page_review_events -> redaction_run_review_events`, and the endpoint must not reconstruct history from mutable finding or review projection rows alone
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/events` reads only page-scoped `redaction_decision_events` plus `redaction_page_review_events` for that `(run_id, page_id)` tuple; it must not infer page history from the current state of `redaction_findings` or `redaction_page_reviews`
- baseline Phase 5 runs persist `policy_id`, `policy_family_id`, and `policy_version` as null while pinning `policy_snapshot_id` and `policy_snapshot_hash`; Phase 7 policy reruns must populate all three explicit policy-lineage fields in addition to preserving the snapshot hash that was executed

Add `redaction_outputs`:
- `run_id`
- `page_id`
- `status` (`PENDING | READY | FAILED | CANCELED`)
- `safeguarded_preview_key`
- `preview_sha256`
- `started_at`
- `generated_at` (nullable)
- `canceled_by` (nullable)
- `canceled_at` (nullable)
- `failure_reason` (nullable)
- `created_at`
- `updated_at`

Add `redaction_run_outputs`:
- `run_id`
- `status` (`PENDING | READY | FAILED | CANCELED`)
- `output_manifest_key`
- `output_manifest_sha256`
- `page_count`
- `started_at`
- `generated_at` (nullable)
- `canceled_by` (nullable)
- `canceled_at` (nullable)
- `failure_reason` (nullable)
- `created_at`
- `updated_at`

Run-output rules:
- `redaction_outputs` remains the per-page preview projection, while `redaction_run_outputs` is the immutable run-level manifest over the safeguarded preview artefacts for that run
- Phase 6 and Phase 8 candidate registration must reference `redaction_run_outputs.output_manifest_key` or `output_manifest_sha256` for `source_artifact_kind = REDACTION_RUN_OUTPUT` instead of reconstructing a candidate ad hoc from mutable page-output state
- `GET /redaction-runs/{runId}/output` and `GET /redaction-runs/{runId}/output/status` are the read surfaces for this run-level manifest and readiness projection; later phases must not infer run-level output readiness only from per-page preview rows

#### APIs
- `GET /projects/{projectId}/documents/{documentId}/privacy/overview`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/active`
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/status`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/review`
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/start-review`
  - moves `redaction_run_reviews.review_status` to `IN_REVIEW` only when all page-level review requirements are satisfied enough to begin run completion
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/events`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/compare?baseRunId={baseRunId}&candidateRunId={candidateRunId}`
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/cancel`
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/activate`
  - allowed only when `redaction_run_reviews.review_status = APPROVED`, all page preview projections are `READY`, and `redaction_run_outputs.status = READY`; updates `document_redaction_projections.active_redaction_run_id` without mutating historical run rows
  - also sets `document_transcription_projections.downstream_redaction_state = CURRENT` for the activated transcription basis consumed by that run
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/findings`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/review`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/events`
- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/findings/{findingId}`
  - requires the caller's current `decision_etag`, rejects the request when `redaction_run_reviews.review_status = APPROVED`, appends a `redaction_decision_events` row with the finding's `page_id`, and updates the current finding projection only when the etag still matches
- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/review`
  - requires the caller's current `review_etag`, rejects the request when `redaction_run_reviews.review_status = APPROVED`, appends a `redaction_page_review_events` row and updates the current page review projection only when the etag still matches
- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/complete-review`
  - appends `redaction_run_review_events` and updates `redaction_run_reviews` only when all pages meet page-level approval and second-review requirements; `APPROVED` completion must persist `approved_snapshot_key`, `approved_snapshot_sha256`, and `locked_at`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/preview-status`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/preview`
  - streams authenticated internal preview bytes and never returns raw object-store URLs
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/output`
- `GET /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/output/status`
- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/area-masks/{maskId}`
  - requires the caller's current area-mask `version_etag`, and when the request also repoints a finding it must include that finding's current `decision_etag`
  - rejects the request when `redaction_run_reviews.review_status = APPROVED`; otherwise appends a new `redaction_area_masks` revision with `supersedes_area_mask_id = {maskId}`, updates the finding projection to point at the new mask only when the supplied etags still match, appends a `redaction_decision_events` row with the replacement `area_mask_id`, and exposes no raw object-store URLs

### Tests and Gates (Iteration 5.0)
#### Backend
- RBAC: `PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, and `ADMIN` can view runs; `PROJECT_LEAD`, `REVIEWER`, or `ADMIN` are required to create, cancel, activate, or resolve findings.
- run and page timeline endpoints read append-only event rows in stable merged order instead of reconstructing history from mutable review projections
- merged timelines use the documented `(created_at, source_table_precedence, id)` order so identical timestamps still render deterministically
- page-scoped decision events persist `page_id`, so `GET /pages/{pageId}/events` does not depend on joining through the current `redaction_findings` projection to recover scope
- findings produced from token-capable transcript runs prefer `token_refs_json`; conservative `area_mask_id` is allowed when token decoding is incomplete but sensitivity risk is reviewer-confirmed
- page-review writes reject stale `review_etag` values instead of silently overwriting a newer review decision, and transitions into `review_status = IN_REVIEW` append `PAGE_REVIEW_STARTED`
- area-mask revision writes reject stale `version_etag` or linked finding `decision_etag` values instead of silently forking mask lineage under concurrent review edits
- approved runs reject later finding, page-review, and area-mask mutations and retain the same `approved_snapshot_key` plus `approved_snapshot_sha256` for downstream governance generation
- approved run snapshots persist immutable bytes for the exact reviewed decision set, so later governance and export phases can load the approved basis without reconstructing it from mutable live tables
- `redaction_run_outputs` persists the run-level safeguarded output manifest used by later candidate registration and does not require downstream phases to infer a singular run artifact from page rows alone
- Audit events:
  - `REDACTION_RUN_CREATED`
  - `REDACTION_RUN_STARTED`
  - `REDACTION_RUN_FINISHED`
  - `REDACTION_RUN_FAILED`
  - `REDACTION_RUN_CANCELED` when applicable
  - `REDACTION_ACTIVE_RUN_VIEWED`
  - `REDACTION_RUN_ACTIVATED`
  - `PRIVACY_TRIAGE_VIEWED`
  - `PRIVACY_WORKSPACE_VIEWED`
  - `REDACTION_FINDING_DECISION_CHANGED` when a finding status or action changes
  - `REDACTION_PAGE_REVIEW_UPDATED` when a page review state changes
  - `REDACTION_PAGE_REVIEW_VIEWED` when a page review surface is opened
  - `REDACTION_PAGE_EVENTS_VIEWED` when a page review timeline is opened
  - `REDACTION_RUN_REVIEW_OPENED` when run completion review begins
  - `REDACTION_RUN_REVIEW_CHANGES_REQUESTED` when run-level completion is rejected back to page review
  - `REDACTION_RUN_REVIEW_COMPLETED` when a run becomes review-complete and Phase 6-eligible
  - `PRIVACY_OVERVIEW_VIEWED` when the privacy overview route is opened
  - `PRIVACY_RUN_VIEWED` when a run detail route is opened
  - `REDACTION_RUN_STATUS_VIEWED` when a run status surface is opened
  - `REDACTION_RUN_REVIEW_VIEWED` when the run review surface is opened
  - `REDACTION_RUN_EVENTS_VIEWED` when a run timeline is opened
  - `REDACTION_COMPARE_VIEWED` when a compare route is opened
  - `SAFEGUARDED_PREVIEW_REGENERATED` when a preview hash changes after a decision update
  - `SAFEGUARDED_PREVIEW_STATUS_VIEWED` when page preview readiness is read
  - `SAFEGUARDED_PREVIEW_ACCESSED` when preview bytes are read through the preview endpoint
  - `SAFEGUARDED_PREVIEW_VIEWED` when a preview route is opened

#### web-surface
- visual regression for Overview, Triage, and Workspace shell states (`Expanded`, `Balanced`, `Compact`, `Focus`)
- accessibility scans for Overview, Triage, and Workspace shell

### Exit Criteria (Iteration 5.0)
Privacy surfaces, run tables, and routing exist without leaking later-phase scope into this phase.

## Iteration 5.1: Detection v1 (Direct Identifiers First)

### Goal
Detect direct identifiers conservatively and route uncertainty to reviewers.

### Backend Work
Implement detector pipeline:
- rule-based detectors:
  - `Presidio` email
  - `Presidio` phone
  - `Presidio` postcode
  - `Presidio` ID-like patterns
  - `Presidio` URLs
- local NER detectors for:
  - `GLiNER` names
  - `GLiNER` places
  - `GLiNER` organisations
- optional local LLM assistance for ambiguous cases:
  - `Qwen3-4B` bounded assist mode only
  - explain why a finding was routed to review
  - summarize special-category or context cues for the reviewer
  - never auto-apply a decision without corroborating rule or NER evidence
- geometry linking to page and line references

Fusion rules:

- normalize every detector output onto canonical token/span offsets before merge
- exact-pattern `RULE` matches win as `basis_primary` for structured identifiers such as email, phone, postcode, URL, and ID-like values
- same-category overlaps from multiple detectors merge into one finding, keep the highest-confidence authoritative detector as `basis_primary`, and preserve the corroborating detectors in `basis_secondary_json`
- cross-category overlaps, partial overlaps with conflicting spans, or `RULE`/`NER` disagreements default to `NEEDS_REVIEW` instead of silent auto-application
- optional assist output may explain a routed conflict, but it cannot resolve a detector disagreement by itself

Output rules:
- populate `redaction_findings`
- auto-apply only when `basis_primary` evidence is above the pinned baseline policy-snapshot threshold
- optional assist output may enrich `basis_secondary_json` or `assist_explanation_key`, but it can never become the sole basis for `AUTO_APPLIED`
- default low-confidence findings to `NEEDS_REVIEW`
- when `line_id` is present, `span_basis_kind = LINE_TEXT` and `span_start`/`span_end` are relative to that line's diplomatic text
- when `line_id` is null but the detector resolved a text-bearing page window, `span_basis_kind = PAGE_WINDOW_TEXT` and `span_basis_ref = source_ref_id`
- findings that are purely geometry-driven or unreadable-sensitive use `span_basis_kind = NONE`, keep `span_start`/`span_end` null, and must use conservative masking rather than text-span replacement

### Web Client Work
Workspace and triage updates:
- highlight detected spans with category chips
- show confidence and basis
- allow reviewers to filter by category and review status

### Tests and Gates (Iteration 5.1)
#### Unit
- deterministic span extraction with no off-by-one errors
- UK-format detector validation
- NER wrapper timeout and empty-output handling
- local LLM assistance timeout falls back cleanly to rules plus NER only

#### Integration
- run detection and verify findings, counts, and page linkage
- local LLM assistance cannot create an `AUTO_APPLIED` finding without corroborating detector evidence
- local LLM assistance can populate reviewer-visible explanation artefacts only in `assist_explanation_key` and secondary-basis metadata, never in `basis_primary`
- conflicting detector overlaps resolve according to the pinned fusion rules and route unresolved conflicts to `NEEDS_REVIEW`

#### Privacy Gate
- synthetic PII pack must maintain near-100% recall for direct identifiers
- build fails if recall regresses below the pinned `DIRECT_IDENTIFIER_RECALL_FLOOR` defined by the synthetic PII gold set

### Exit Criteria (Iteration 5.1)
Direct identifiers are detected reliably enough to support reviewer triage.

## Iteration 5.2: Decision Engine v1 (Mask) + Safeguarded Preview

### Goal
Apply reviewer-confirmed masking decisions and generate a deterministic safeguarded preview.

### Backend Work
#### Decision engine
- apply span-safe replacements
- preserve punctuation and whitespace integrity
- resolve overlapping spans deterministically
- persist every decision as an append-only `redaction_decision_events` row and treat `redaction_findings` as the current projection
- apply token-linked masks first when token refs exist; apply conservative area masks when unreadable-but-sensitive handwriting is reviewer-confirmed
- area-mask edits never mutate geometry in place; every mask change appends a new `redaction_area_masks` revision and moves the finding's active `area_mask_id` pointer
- text-span overlap precedence in v1 is pinned as: lower `span_start` first, then longer span on the same start, then token-linked span over non-token span, then stricter action precedence `MASK > PSEUDONYMIZE > GENERALIZE`; area masks never replace a token-linked text decision and are allowed only when token refs are absent or intentionally conservative

#### Preview rules
- keep dual layers:
  - Controlled transcript source
  - safeguarded preview text
- recompute preview hash whenever a decision changes
- persist `redaction_outputs.status` as `PENDING -> READY | FAILED | CANCELED` so Phase 6 can gate on an explicit preview projection without treating canceled preview generation as an implicit failure
- never store raw original text inside preview artefacts or later release artefacts

### Web Client Work
- workspace mode switch:
  - `Controlled view` (`PROJECT_LEAD`, `RESEARCHER`, `REVIEWER`, `ADMIN`)
  - `Safeguarded preview`
- triage breakdown:
  - auto-applied
  - needs review
  - overridden

### Tests and Gates (Iteration 5.2)
#### Unit
- deterministic overlap resolution for redaction spans
- safeguarded invariant: masked values cannot leak raw originals
- preview hash changes only when resolved decisions change
- overlap precedence follows the pinned `(span_start, longer_span_first, token_linked_first, action_precedence)` rule and never lets an area mask replace a token-linked text decision

#### Integration
- detection -> decision -> preview generation -> UI retrieval
- token-linked findings and area-mask fallback both render correctly in preview and event history
- area-mask edits append a new mask revision and do not mutate prior geometry in place
- high-risk override classification is deterministic from decision type, conservative area-mask use, category policy, and detector-disagreement markers
- run-level safeguarded output manifests are regenerated deterministically from the current approved page previews and expose a stable `output_manifest_sha256` for later candidate registration

#### E2E
- toggle safeguarded preview and verify replacements and highlights

### Exit Criteria (Iteration 5.2)
System produces a baseline-policy safeguarded preview suitable for review but not yet for export.

## Iteration 5.3: Review Workspace v1 (Approve, Override, Dual Control)

### Goal
Make privacy review fast, trustworthy, and auditable through a dedicated workspace.

### Web Client Work
#### Workspace goals
1. Find the next unresolved item quickly.
2. Confirm, reject, or override with minimal friction.
3. See immediate effect in Controlled and safeguarded-preview modes.
4. Capture reason, reviewer identity, and timestamps for every non-trivial decision.
5. Approve a page only when review rules are satisfied.
6. Surface conservative reviewer explanations for ambiguous findings without turning them into authoritative decisions.

#### Required deep links
- `Open next unresolved` opens the first unresolved finding on the correct page.
- `Open finding` uses `?page={pageNumber}&runId={runId}&findingId={findingId}`.
- `Open line` uses `?page={pageNumber}&runId={runId}&lineId={lineId}`.
- `Open token` uses `?page={pageNumber}&runId={runId}&tokenId={tokenId}` when token-linked highlighting is available.

#### Interaction rules
- toolbar uses roving focus and remains a single tab stop
- modal dialogs trap focus and return it correctly
- `Approve page` stays disabled until unresolved count is `0`
- `Complete review` stays disabled until every page is approved, every required second review is complete, and all page previews are `READY`
- overrides require a reason
- high-risk overrides require second review when any of the following are true:
  - the override changes a finding to `FALSE_POSITIVE`
  - the override introduces or replaces a conservative `area_mask_id`
  - the finding category is marked dual-review-required by the pinned policy snapshot
  - the finding had detector disagreement or ambiguous overlap recorded in `basis_secondary_json`
- required second review must be performed by a user different from `first_reviewed_by`; same-user second-review attempts are rejected
- `REVIEWER`, `PROJECT_LEAD`, or `ADMIN` can approve pages and apply overrides; `AUDITOR` does not participate in Phase 5 review actions

### Backend Work
- append-only decision history for every finding change comes from `redaction_decision_events`
- page approval and second-review history append `redaction_page_review_events`
- run completion history appends `redaction_run_review_events` and advances `redaction_run_reviews`
- dual-control eligibility rules on `redaction_page_reviews`
- whenever `requires_second_review = true`, the second reviewer must differ from `first_reviewed_by`
- optimistic concurrency on reviewer decisions uses the current finding `decision_etag` and rejects stale writes instead of silently overwriting a newer reviewer action

### Tests and Gates (Iteration 5.3)
#### Unit
- override requires reason
- dual-control blocks single-reviewer completion when enabled
- same-user first and second review actions are rejected when `requires_second_review = true`
- page approval eligibility is deterministic

#### Integration
- decisions propagate to triage counts, preview hashes, and page review state
- approval transitions respect second-review requirements
- page second-review transitions reject a reviewer whose user ID matches `first_reviewed_by`
- run completion is blocked until every page is approved and any required second review has completed
- page-review writes reject stale `review_etag` values, and transitions into `IN_REVIEW` append `PAGE_REVIEW_STARTED`

#### E2E
- reviewer resolves findings and approves a page end-to-end
- reviewer completes run review only after page approvals and ready previews satisfy the run gate
- deep links open and focus the expected target
- false-positive decisions update history and unresolved counts

#### Accessibility and UI gates
- WCAG 2.2 AA target for workspace interactions
- visual regression for default, selected-finding, override, and modal states
- keyboard navigation tests for toolbar, transcript, findings list, and dialogs
- reflow and zoom scenarios use controlled scrolling in bounded regions instead of clipped content or obscured focus

### Exit Criteria (Iteration 5.3)
Privacy review is production-grade for direct-identifier masking and safeguarded preview generation.

## Handoff to Later Phases
- Phase 6 adds manifest generation and Controlled-only evidence ledgers for approved Phase 5 runs.
- Phase 7 adds advanced policy authoring, pseudonymisation, and indirect-identifier handling.
- Phase 8 adds disclosure review, export requests, and the only allowed external egress path.

## Phase 5 Definition of Done
Move to Phase 6 only when all are true:
1. Redaction runs are reproducible with pinned detector and policy snapshots.
2. Direct identifiers are detected conservatively and uncertain cases route to review.
3. Safeguarded previews are deterministic and do not leak raw originals.
4. Reviewer decisions are append-only, audited, and preserve explicit second-review state whenever `requires_second_review` is true.
5. Phase-complete runs reach `redaction_run_reviews.review_status = APPROVED` only after every page meets the review rules.
6. The document's current privacy basis is an explicitly activated approved run, not an implicit latest-successful run.
7. No Phase 5 UI or API introduces a bypass around later manifest or export-governance phases.
8. Findings are anchored to tokens when available, with conservative area-mask fallback available for unreadable sensitive handwriting.

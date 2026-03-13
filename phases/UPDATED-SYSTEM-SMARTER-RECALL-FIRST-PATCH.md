# Updated System: Smarter Recall-First Patch (Normative Override)

> Status: ACTIVE NORMATIVE PATCH
> Scope: Phase 3, Phase 4, Phase 5, and Phase 10 contracts
> Precedence: This patch overrides older phase text where conflicts exist

## Why This Patch Exists
The base phase set has strong building blocks (line coverage checks, stable line IDs, line crops, optional char boxes, `bbox_refs`), but still permits a layout-first failure mode:

- missed handwriting may never become a transcription target
- missed transcription cannot be searched or redacted later
- word-level coordinates are not guaranteed consistently enough for exact highlight or masking

This patch changes the governing logic to recall-first behavior.

## Core Override
`find text -> check for missed text -> rescue missed text -> anchor every word/token -> then permit search/redaction`

## Normative Rules
### 1) Recall-First, Not Layout-First
- Layout output is no longer treated as complete by itself.
- Every page must run a second-stage missed-text check after layout generation.

### 2) Rescue Path for Missed Text
- Suspicious faint, noisy, or irregular writing areas become `rescue candidates`.
- Rescue candidates are transcribed through widened line crops or page-window rescue paths.
- Rescue flow is part of normal processing, not only manual exception handling.

### 3) No-Silent-Drop Page Status
Every page must resolve to one explicit completion class:

- `COMPLETE`
- `NEEDS_RESCUE`
- `NEEDS_MANUAL_REVIEW`

No downstream activation may treat a page as fully complete when it still indicates missing-text risk.

### 4) Guaranteed Token-Level Anchors
Every persisted transcribed token/word must include:

- stable `token_id`
- `page_id`
- source link (`line_id` when available, otherwise rescue candidate/page-window source)
- geometry (`bbox` and/or `polygon`)
- provenance to transcription run and version

Line-level anchoring remains useful but is insufficient alone for downstream guarantees.

### 5) Search and Redaction Must Anchor to Tokens
- Controlled search indexes are built from token anchors, not only line blobs.
- Redaction findings must attach to token references when possible.
- When tokenization cannot be trusted for a sensitive handwritten area, conservative area masking is allowed with explicit geometry and rationale.

### 6) Conservative Mask Fallback
- Reviewer-observed sensitive but unreadable regions may be masked as area geometry before final decoding is perfect.
- This fallback must be auditable and reversible only within Controlled evidence boundaries.

## Data Model Additions (Normative)
### Phase 3 (Layout)
- `page_layout_results.page_recall_status` (`COMPLETE | NEEDS_RESCUE | NEEDS_MANUAL_REVIEW`)
- `layout_recall_checks` (per-page recall-check metrics and missed-text signals)
- `layout_rescue_candidates` (candidate geometry, confidence, and extraction context)

### Phase 4 (Transcription)
- `token_transcription_results`
  - `run_id`
  - `page_id`
  - `line_id` (nullable)
  - `token_id`
  - `token_text`
  - `token_confidence`
  - `bbox_json` (nullable)
  - `polygon_json` (nullable)
  - `source_kind` (`LINE | RESCUE_CANDIDATE | PAGE_WINDOW`)
  - `source_ref_id`
  - `created_at`

### Phase 5 (Privacy/Redaction)
- `redaction_findings` extended to support token-level linkage (`token_refs_json`)
- `redaction_area_masks` for conservative geometry masks when token decoding is incomplete

### Phase 10 (Search)
- `search_documents` and/or companion token table must store token-level anchors
- search hit payloads must include `token_id` (or explicit area geometry fallback) when available

## API Contract Additions (Normative)
### Phase 3
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/recall-status`
- `GET /projects/{projectId}/documents/{documentId}/layout-runs/{runId}/pages/{pageId}/rescue-candidates`

### Phase 4
- `GET /projects/{projectId}/documents/{documentId}/transcription-runs/{runId}/pages/{pageId}/tokens`

### Phase 5
- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/area-masks/{maskId}`

### Phase 10
- `GET /projects/{projectId}/search` responses include token-level anchor payloads when available

## Gating Overrides
### No-Silent-Drop Gate
- A run cannot be promoted if any page lacks explicit recall-status resolution.

### Recall Quality Gate
- Missed-text recall check metrics are mandatory and versioned.
- Regression tests must fail when recall drops below pinned floor for the handwritten gold set.

### Token Anchor Gate
- Token geometry coverage and anchor validity must pass before search index activation.

### Privacy Coverage Gate
- Synthetic sensitive samples in faint/irregular handwriting must be detectable via token refs or conservative area masks.

## Cross-Phase Behavior
- Phase 3 owns recall-check and rescue candidate generation.
- Phase 4 owns token anchor materialization from normal + rescue inputs.
- Phase 5 owns token-linked and area-mask fallback decisions.
- Phase 10 search must preserve token provenance to workspace deep links.

## Compatibility and Migration
- Existing line-level contracts remain valid.
- This patch is additive and tightening: line-only outputs may continue for historical runs, but new promoted runs must satisfy recall and token-anchor gates.

## Implementation Note
This is intentionally a normative patch document to keep review scope clear and avoid risky line-by-line rewrites across all phase files in one change.

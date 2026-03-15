# Privacy Finding Geometry And Area-Mask Fallback Contract

Status: Established in Prompt 61  
Scope: Token-linked finding geometry, conservative area-mask fallback, append-only area-mask revision lineage, and workspace-facing read contracts.

## Canonical finding geometry

`redaction_findings` remains the single finding model and now carries canonical geometry truth via:

- `token_refs_json` for token-linked findings
- `bbox_refs` for bounded geometry references
- `area_mask_id` when conservative fallback masking is used

All page-finding reads include a typed `geometry` payload with:

- `anchorKind`: `TOKEN_LINKED | AREA_MASK_BACKED | BBOX_ONLY | NONE`
- `lineId`
- `tokenIds`
- `boxes` (`x`, `y`, `width`, `height`, `source`)
- `polygons` (`points`, `source`)

This payload is computed server-side so workspace clients do not need ad hoc geometry recomputation.

## Validation rules

On finding materialization:

- token refs must reference valid token IDs for the run input transcription
- bbox and polygon values must be finite and page-bounded
- empty/invalid geometry is rejected explicitly
- contradictory duplicated token geometry refs are rejected
- conflicting `bboxRefs.tokenBboxes` vs `tokenRefsJson[*].bboxJson` is rejected

For area masks:

- `maskReason` is required
- geometry must include bounded `bbox` and/or `polygon`
- no NaN/Inf or out-of-bounds coordinates are accepted

## Conservative area-mask fallback

When text is unreadable or tokenization is incomplete, reviewers can create a conservative area mask:

- `POST /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/pages/{pageId}/area-masks`
- optional finding linkage updates the finding to `OVERRIDDEN` and points `area_mask_id` to the created mask

No synthetic token refs are fabricated for unreadable content.

## Append-only revision lineage

Area-mask edits are append-only:

- `PATCH /projects/{projectId}/documents/{documentId}/redaction-runs/{runId}/area-masks/{areaMaskId}`
- a new mask revision row is created on every edit
- previous row receives `superseded_by_area_mask_id`
- new row receives `supersedes_area_mask_id`
- linked finding pointer moves to the new active mask revision

The legacy page-scoped patch route remains available for compatibility, but revision semantics are identical.

## Workspace behavior contract

Workspace highlights consume the canonical finding `geometry` payload:

- token-linked findings render token geometry overlays
- area-mask-backed findings render conservative area overlays
- the UI always exposes anchor provenance (`anchorKind`) so exact token masking is not implied when only area masks exist

## Prompt 62 handoff

Prompt 62 consumes this contract directly:

- decision/masking engines can apply either token-linked geometry or conservative area masks without schema churn
- run/page decision layers can rely on stable `geometry` payloads and active `area_mask_id` lineage
- safeguarded preview generation can remain truthful about token-linked vs area-mask-backed masking basis

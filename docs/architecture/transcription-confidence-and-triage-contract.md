# Transcription Confidence And Triage Contract

## Scope
This contract defines confidence scoring, confidence-band persistence, and triage metrics for Phase 4 transcription runs.

## Canonical Confidence Resolution
For each persisted `line_transcription_results` row:

1. `MODEL_NATIVE` path
- If the engine response provides native confidence/logprob-derived confidence in `[0,1]`, the worker calibrates it through the declared `confidence_calibration_version`.

2. `READ_AGREEMENT` path
- If native confidence is absent, the worker computes deterministic agreement confidence from two fixed reads of the same crop target:
  - crop+context read
  - crop-only read
- Agreement confidence is calibrated to the same normalized `[0,1]` scale.

3. `FALLBACK_DISAGREEMENT` signal
- When enabled by run basis or params, fallback disagreement can adjust confidence as a review signal.
- This signal never mutates primary transcript text.

## Persisted Fields
Each line persists:
- `conf_line`
- `confidence_basis`
- `confidence_band` (`HIGH | MEDIUM | LOW | UNKNOWN`)
- `alignment_json_key` (optional)
- `char_boxes_key` (optional)

`confidence_band` derives from normalized `conf_line` and run thresholds:
- `HIGH`: `conf_line >= review_confidence_threshold`
- `MEDIUM`: `fallback_confidence_threshold <= conf_line < review_confidence_threshold`
- `LOW`: `conf_line < fallback_confidence_threshold`
- `UNKNOWN`: confidence unavailable

## Alignment And Char-Box Payloads
- Compact alignment payloads are persisted when alignment spans are emitted.
- Malformed spans or anchor mismatches are recorded as non-fatal validation warnings in `flags_json` and page warnings/metrics.
- Char-box payloads are persisted only when provided by the active engine.
- Missing char boxes are explicit and do not block line queryability.

## Aggregate Metrics Endpoint
`GET /projects/{projectId}/documents/{documentId}/transcription/metrics`

Returns typed, explainable metrics:
- `percentLinesBelowThreshold`
- `lowConfidencePageDistribution`
- `segmentationMismatchWarningCount`
- `structuredValidationFailureCount`
- `fallbackInvocationCount`
- `confidenceBands`

No monolithic "quality score" is produced.

## Triage Endpoint
`GET /projects/{projectId}/documents/{documentId}/transcription/triage`

Supports:
- `status`
- `confidenceBelow`
- `page`
- cursor pagination

Rows are deterministically ordered by explicit ranking factors and return per-page rationale.

# Preprocessing Engine v1 Determinism Contract

> Status: Active Prompt 38 baseline
> Scope: Deterministic grayscale preprocessing execution, job flow, metrics, warnings, and manifest provenance

## Canonical Job Flow

Preprocessing execution is queued through the existing jobs framework using:

- `PREPROCESS_DOCUMENT`
- `PREPROCESS_PAGE`
- `FINALIZE_PREPROCESS_RUN`

Execution sequence:

1. `PREPROCESS_DOCUMENT` moves a run into `RUNNING`, enqueues page jobs, and enqueues finalization.
2. `PREPROCESS_PAGE` processes one page deterministically and persists gray output + optional binary output + metrics.
3. `FINALIZE_PREPROCESS_RUN` rolls run state to terminal and writes the run manifest.

No parallel queue or second worker system is introduced.

## Storage Layout

Inputs:

- `controlled/derived/{project_id}/{document_id}/pages/{page_index}.png`

Outputs:

- `controlled/derived/{project_id}/{document_id}/preprocess/{run_id}/gray/{page_index}.png`
- `controlled/derived/{project_id}/{document_id}/preprocess/{run_id}/bin/{page_index}.png` (profile-gated, optional)
- `controlled/derived/{project_id}/{document_id}/preprocess/{run_id}/metrics/{page_index}.json`
- `controlled/derived/{project_id}/{document_id}/preprocess/{run_id}/manifest.json`

All writes stay inside the controlled-derived prefix and are idempotent for retry safety.

## Deterministic Parameter Contract

- Profiles: `BALANCED`, `CONSERVATIVE`, `AGGRESSIVE`, `BLEED_THROUGH`
- `BALANCED` is the canonical pinned v1 baseline.
- Advanced profiles are explicit and never default:
  - `AGGRESSIVE` (strong cleanup + optional adaptive binarization)
  - `BLEED_THROUGH` (paired recto/verso preferred, conservative single-image fallback)
- Each run stores expanded concrete params in `params_json`.
- Canonical serialization uses sorted keys and stable numeric normalization.
- `params_hash` is `SHA-256(canonical_params_json)`.

Same semantic parameter object must produce the same hash.

## Algorithm Order (v1)

1. decode input image and normalize to 8-bit grayscale
2. resolve/estimate DPI
3. measure skew and deskew
4. perform background normalization
5. apply conservative median denoise
6. apply deterministic local contrast equalization
7. write grayscale PNG and hash

## Metrics And Warning Semantics

Per-page metrics:

- `skew_angle_deg`
- `dpi_estimate`
- `blur_score`
- `background_variance`
- `contrast_score`
- `noise_score`
- `processing_time_ms`
- `binary_output_enabled`
- `bleed_through_mode`
- `bleed_through_pair_available`
- `bleed_through_pair_used`
- `warnings`

Warning codes:

- `LOW_DPI`
- `HIGH_SKEW`
- `HIGH_BLUR`
- `LOW_CONTRAST`
- `BLEED_PAIR_UNAVAILABLE`

Quality gate mapping:

- `BLOCKED` when DPI `< 150`
- `REVIEW_REQUIRED` when DPI unknown or in `[150, 200)`
- `PASS` otherwise

## Finalization And Provenance

- Finalization computes terminal run status from per-page states.
- Manifest records run identity, profile, params hash, pipeline/container provenance, and per-page outputs.
- Historical run rows remain immutable; projections are activated separately.

## Gold-Set Drift Gate

- Canonical fixture pack: `api/tests/fixtures/preprocessing-gold-set/fixture-pack.v1.json`
- Canonical baseline manifest: `api/tests/fixtures/preprocessing-gold-set/baseline-manifest.v1.json`
- Canonical regression harness: `api/tests/test_preprocessing_gold_set.py`

Rules:

- canonical `BALANCED` output remains hash-gated
- advanced-profile records may use approved `SSIM` exceptions only when explicitly documented in the baseline manifest
- CI fails on unapproved drift and uploads preprocessing drift artifacts for review
- baseline refresh requires explicit approval metadata through `scripts/update_preprocessing_gold_set_baseline.py`

## No-Egress Posture

- Preprocessing pipeline execution is local and storage-backed only.
- Outbound allowlist policy remains active for runtime.
- No external model or web call path is part of preprocessing v1 execution.

## Advanced Risk Gating

- Advanced full-document reruns require explicit confirmation.
- Confirmation is accepted only for `REVIEWER`, `PROJECT_LEAD`, and `ADMIN`.
- Confirmation posture is persisted in run params metadata (`profile_risk_posture`, `advanced_risk_confirmation_required`, `advanced_risk_confirmation`).

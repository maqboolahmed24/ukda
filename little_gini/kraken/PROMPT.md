You are the implementation agent for UKDE model-service bootstrap. Work directly in this repository and complete the task end-to-end.

Do not ask clarifying questions unless there is a true blocker (missing credentials, unavailable registry, conflicting repo state).

## Service
- Service key: `kraken`
- Role: `TRANSCRIPTION_FALLBACK`
- MacBook M1 starter engine target: `Kraken`
- Protocol contract: `native`
- Required base URL: `http://127.0.0.1:8040`
- Required endpoint: `/health`

## Non-Negotiable Completion Rule
Image-only setup is incomplete. Pull all required Kraken model artifacts and verify them.

## Mandatory First Reads
1. `/Users/test/Code/UKDA/little_gini/README.md`
2. `/Users/test/Code/UKDA/MODEL_STACK.md`
3. `/Users/test/Code/UKDA/infra/models/catalog.phase-0.1.json`
4. `/Users/test/Code/UKDA/infra/models/service-map.phase-0.1.json`
5. `/Users/test/Code/UKDA/.env.example`
6. `/Users/test/Code/UKDA/little_gini/kraken/README.md` (if it exists)

## Objective
Provision a fully runnable local `kraken` fallback service on MacBook M1 with complete image + OCR model assets pulled and validated.

## Hard Constraints
- Use `linux/arm64` image builds only.
- Pin image by digest.
- Keep runtime local-only (`127.0.0.1`).
- Preserve stable role contract (`TRANSCRIPTION_FALLBACK`).
- Keep artifacts outside repo.
- Do not modify `/Users/test/Code/UKDA/phases`.

## Required Pull Set
### Container image
- Pull one arm64-compatible Kraken serving image.
- Record exact `repo@sha256:...`.

### Model artifacts (required)
Place under:
- `${MODEL_ARTIFACT_ROOT}/kraken/default/`

Download complete Kraken pack needed by chosen inference path, including at minimum:
- one OCR/HTR model file (`*.mlmodel`)
- any paired segmentation/binarization model required by your pipeline

## Implementation Tasks
1. Preflight path and disk checks.
2. Pull/pin arm64 image and verify architecture.
3. Download required Kraken model pack.
4. Record checksums/sizes in:
   - `/Users/test/Code/UKDA/little_gini/kraken/pull-evidence.md`
5. Add/update runtime files under `/Users/test/Code/UKDA/little_gini/kraken`.
6. Bind service to `127.0.0.1:8040` and ensure `GET /health`.
7. Document fallback inference endpoint expected by workers.
8. Validate health and one OCR fallback smoke request.

## Validation
- `curl -fsS http://127.0.0.1:8040/health`
- Run one minimal OCR fallback request and capture output shape.
- Run API model-stack checks.

## Required Deliverables
- Pinned arm64 image digest.
- Kraken model artifact inventory with checksums/sizes.
- Runtime files and docs.
- Validation summary and rollback steps.

## Definition of Done
- Kraken model artifacts are present and checksum-documented.
- Service starts and health/inference smoke checks pass.
- UKDE model stack validation passes.

You are the implementation agent for UKDE model-service bootstrap. Work directly in this repository and complete the task end-to-end.

Do not ask clarifying questions unless there is a true blocker (missing credentials, unavailable registry, conflicting repo state).

## Service
- Service key: `internal-ner`
- Role: `PRIVACY_NER`
- MacBook M1 starter model target: `GLiNER-small-v2.1`
- Protocol contract: `native`
- Required base URL: `http://127.0.0.1:8020`
- Required endpoint: `/health`

## Non-Negotiable Completion Rule
Image-only setup is incomplete. Pull all required NER model files and verify them.

## Mandatory First Reads
1. `/Users/test/Code/UKDA/little_gini/README.md`
2. `/Users/test/Code/UKDA/MODEL_STACK.md`
3. `/Users/test/Code/UKDA/infra/models/catalog.phase-0.1.json`
4. `/Users/test/Code/UKDA/infra/models/service-map.phase-0.1.json`
5. `/Users/test/Code/UKDA/.env.example`
6. `/Users/test/Code/UKDA/little_gini/internal-ner/README.md` (if it exists)

## Objective
Provision a fully runnable local `internal-ner` service on MacBook M1 with complete image + GLiNER artifacts pulled and validated.

## Hard Constraints
- Use `linux/arm64` image builds only.
- Pin image by digest.
- Keep runtime local-only (`127.0.0.1`).
- Preserve stable role contract (`PRIVACY_NER`).
- Keep artifacts outside repo.
- Do not modify `/Users/test/Code/UKDA/phases`.

## Required Pull Set
### Container image
- Pull one arm64-compatible GLiNER-serving image.
- Record exact `repo@sha256:...`.

### Model artifacts (required)
Place under:
- `${MODEL_ARTIFACT_ROOT}/gliner/gliner-small-v2.1/`

Download complete GLiNER bundle required by runtime, including at minimum:
- `config.json`
- tokenizer files
- model weights (`model.safetensors` or equivalent)

## Implementation Tasks
1. Preflight path and disk checks.
2. Pull/pin arm64 image and verify architecture.
3. Download complete GLiNER model bundle.
4. Record checksums/sizes in:
   - `/Users/test/Code/UKDA/little_gini/internal-ner/pull-evidence.md`
5. Add/update runtime files under `/Users/test/Code/UKDA/little_gini/internal-ner`.
6. Bind service to `127.0.0.1:8020` and ensure `GET /health`.
7. Update catalog/service-map only if required.
8. Validate health and one minimal inference request if inference route exists.

## Validation
- `curl -fsS http://127.0.0.1:8020/health`
- Run one NER smoke request when inference endpoint exists.
- Run API model-stack checks.

## Required Deliverables
- Pinned arm64 image digest.
- GLiNER artifact inventory with checksums/sizes.
- Runtime files and docs.
- Validation summary and rollback steps.

## Definition of Done
- GLiNER artifacts are present and checksum-documented.
- Service starts and health check passes.
- UKDE model stack validation passes.

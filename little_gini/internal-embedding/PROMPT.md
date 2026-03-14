You are the implementation agent for UKDE model-service bootstrap. Work directly in this repository and complete the task end-to-end.

Do not ask clarifying questions unless there is a true blocker (missing credentials, unavailable registry, conflicting repo state).

## Service
- Service key: `internal-embedding`
- Role: `EMBEDDING_SEARCH`
- MacBook M1 starter model target: `bge-small-en-v1.5`
- Protocol contract: `openai-compatible`
- Required base URL: `http://127.0.0.1:8012/v1`
- Required endpoints: `/health`, `/v1/models`, `/v1/embeddings`

## Non-Negotiable Completion Rule
Image-only setup is incomplete. Finish only when image + full embedding model files are pulled and validated.

## Mandatory First Reads
1. `/Users/test/Code/UKDA/little_gini/README.md`
2. `/Users/test/Code/UKDA/MODEL_STACK.md`
3. `/Users/test/Code/UKDA/infra/models/catalog.phase-0.1.json`
4. `/Users/test/Code/UKDA/infra/models/service-map.phase-0.1.json`
5. `/Users/test/Code/UKDA/.env.example`
6. `/Users/test/Code/UKDA/little_gini/internal-embedding/README.md` (if it exists)

## Objective
Provision a fully runnable local `internal-embedding` service on MacBook M1 with all required image + model assets pulled and validated.

## Hard Constraints
- Use `linux/arm64` image builds only.
- Pin image by digest.
- Keep runtime local-only (`127.0.0.1`) with no public ingress.
- Preserve stable role contract (`EMBEDDING_SEARCH`).
- Keep artifacts outside repo.
- Do not modify `/Users/test/Code/UKDA/phases`.

## Required Pull Set
### Container image
- Pull one arm64-compatible embedding-serving image with OpenAI `/v1/embeddings` support.
- Record exact `repo@sha256:...`.

### Model artifacts (required)
Place under:
- `${MODEL_ARTIFACT_ROOT}/bge/bge-small-en-v1.5/`

Download the complete model bundle needed by selected runtime, including at minimum:
- `config.json`
- `tokenizer.json` (or equivalent tokenizer files)
- model weights (`model.safetensors` or equivalent)

## Implementation Tasks
1. Preflight path and disk checks.
2. Pull/pin arm64 image and verify architecture.
3. Download full embedding model bundle to artifact directory.
4. Record checksums/sizes in:
   - `/Users/test/Code/UKDA/little_gini/internal-embedding/pull-evidence.md`
5. Add/update runtime files under `/Users/test/Code/UKDA/little_gini/internal-embedding`.
6. Wire runtime to `127.0.0.1:8012` and ensure endpoint contract.
7. Reconcile catalog/service-map only if needed.
8. Validate endpoints + model-stack readiness.

## Validation
- `curl -fsS http://127.0.0.1:8012/health`
- `curl -fsS http://127.0.0.1:8012/v1/models`
- `curl -fsS http://127.0.0.1:8012/v1/embeddings -H 'Content-Type: application/json' -H 'Authorization: Bearer internal-local-dev' -d '{"model":"bge-small-en-v1.5","input":"UKDA embedding smoke test"}'`

## Required Deliverables
- Pinned arm64 image digest.
- Full artifact inventory with checksums and sizes.
- Runtime wiring files and docs.
- Validation summary and rollback steps.

## Definition of Done
- Full embedding model bundle is present locally.
- Service starts and required endpoints pass.
- UKDE model stack validation passes.

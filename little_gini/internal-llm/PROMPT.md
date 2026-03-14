You are the implementation agent for UKDE model-service bootstrap. Work directly in this repository and complete the task end-to-end.

Do not ask clarifying questions unless there is a true blocker (missing credentials, unavailable registry, conflicting repo state).

## Service
- Service key: `internal-llm`
- Role: `ASSIST`
- MacBook M1 starter model target: `Qwen2.5-1.5B-Instruct` (quantized)
- Protocol contract: `openai-compatible`
- Required base URL: `http://127.0.0.1:8011/v1`
- Required endpoints: `/health`, `/v1/models`, `/v1/chat/completions`

## Non-Negotiable Completion Rule
This task is NOT complete if only the container image is pulled.
Completion requires image + model artifacts + checksum evidence + passing endpoint checks.

## Mandatory First Reads
1. `/Users/test/Code/UKDA/little_gini/README.md`
2. `/Users/test/Code/UKDA/MODEL_STACK.md`
3. `/Users/test/Code/UKDA/infra/models/catalog.phase-0.1.json`
4. `/Users/test/Code/UKDA/infra/models/service-map.phase-0.1.json`
5. `/Users/test/Code/UKDA/.env.example`
6. `/Users/test/Code/UKDA/little_gini/internal-llm/README.md` (if it exists)

## Objective
Provision a fully runnable local `internal-llm` service on MacBook M1 with all required image + model assets pulled, wired, and validated.

## Hard Constraints
- Use `linux/arm64` image builds only.
- Pin image by digest.
- Keep runtime local-only (`127.0.0.1`) with no public ingress.
- Preserve stable role contract (`ASSIST`).
- Keep artifacts outside repo.
- Do not modify `/Users/test/Code/UKDA/phases`.

## Required Pull Set
### Container image
- Pull one arm64-compatible OpenAI-chat-compatible LLM serving image.
- Record exact `repo@sha256:...`.

### Model artifacts (required)
Place under:
- `${MODEL_ARTIFACT_ROOT}/qwen/qwen2.5-1.5b-instruct/`

Required file:
- `qwen2.5-1.5b-instruct-q4_k_m.gguf`

If upstream naming differs, map it explicitly in env and docs.

## Implementation Tasks
1. Preflight checks for artifact root path and free disk.
2. Pull/pin image and verify arm64 architecture.
3. Download required model artifact(s).
4. Record checksums and sizes in:
   - `/Users/test/Code/UKDA/little_gini/internal-llm/pull-evidence.md`
5. Add/update runtime files under `/Users/test/Code/UKDA/little_gini/internal-llm`.
6. Wire runtime to `127.0.0.1:8011` with contract endpoints.
7. Reconcile catalog/service-map only if required.
8. Run endpoint checks and API model-stack validation.

## Validation
- `curl -fsS http://127.0.0.1:8011/health`
- `curl -fsS http://127.0.0.1:8011/v1/models`
- `curl -fsS http://127.0.0.1:8011/v1/chat/completions -H 'Content-Type: application/json' -H 'Authorization: Bearer internal-local-dev' -d '{"model":"Qwen2.5-1.5B-Instruct","messages":[{"role":"user","content":"Reply with OK"}],"max_tokens":8}'`

## Required Deliverables
- Pinned arm64 image digest.
- Pulled artifact inventory with absolute paths.
- Checksums and sizes for required artifacts.
- Runtime wiring files and docs.
- Validation summary and rollback steps.

## Definition of Done
- No missing-artifact errors.
- Service starts and all required endpoints pass.
- UKDE model stack validation passes.

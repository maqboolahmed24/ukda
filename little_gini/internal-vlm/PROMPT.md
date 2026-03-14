You are the implementation agent for UKDE model-service bootstrap. Work directly in this repository and complete the task end-to-end.

Do not ask clarifying questions unless there is a true blocker (missing credentials, unavailable registry, conflicting repo state).

## Service
- Service key: `internal-vlm`
- Role: `TRANSCRIPTION_PRIMARY`
- MacBook M1 starter model target: `Qwen2.5-VL-3B-Instruct` (quantized)
- Protocol contract: `openai-compatible`
- Required base URL: `http://127.0.0.1:8010/v1`
- Required endpoints: `/health`, `/v1/models`, `/v1/chat/completions`

## Non-Negotiable Completion Rule
This task is NOT complete if only the container image is pulled.
Completion requires ALL of the following:
1. Arm64 service image is pulled and pinned by digest.
2. Required model artifacts are downloaded locally under `MODEL_ARTIFACT_ROOT`.
3. Artifact checksums are recorded and verified.
4. Service boots and endpoint checks pass.

## Mandatory First Reads
1. `/Users/test/Code/UKDA/little_gini/README.md`
2. `/Users/test/Code/UKDA/MODEL_STACK.md`
3. `/Users/test/Code/UKDA/infra/models/catalog.phase-0.1.json`
4. `/Users/test/Code/UKDA/infra/models/service-map.phase-0.1.json`
5. `/Users/test/Code/UKDA/.env.example`
6. `/Users/test/Code/UKDA/little_gini/internal-vlm/README.md` (if it exists)

## Objective
Provision a fully runnable local `internal-vlm` service on MacBook M1 with all required image + model assets pulled, wired, and validated against UKDE contracts.

## Hard Constraints
- Use `linux/arm64` image builds only.
- Pin image by digest (not floating tags).
- Keep runtime local-only (`127.0.0.1`) with no public ingress.
- Preserve stable role contract (`TRANSCRIPTION_PRIMARY`); do not invent roles.
- Keep artifacts outside repo (`MODEL_ARTIFACT_ROOT` / `MODEL_DEPLOYMENT_ROOT`).
- Do not modify anything under `/Users/test/Code/UKDA/phases`.

## Required Pull Set
### Container image
- Pull one arm64-compatible OpenAI-chat-compatible VLM serving image.
- Record exact reference: `repo@sha256:...`.

### Model artifacts (required)
Place under:
- `${MODEL_ARTIFACT_ROOT}/qwen/qwen2.5-vl-3b-instruct/`

Required files:
- `qwen2.5-vl-3b-instruct-q4_k_m.gguf`
- `mmproj-qwen2.5-vl-3b-instruct-f16.gguf`

If upstream uses different names, map them explicitly in `.env.internal-vlm` and document the mapping.

## Implementation Tasks
1. Preflight checks
- Ensure `MODEL_ARTIFACT_ROOT` is absolute and outside repo.
- Ensure destination directory exists.
- Verify sufficient free disk before downloads.

2. Pull and pin image
- Pull arm64 image.
- Confirm architecture via `docker image inspect`.
- Record digest in `README.md` and env example.

3. Pull model artifacts
- Download all required files (resumable download preferred).
- Store only in required artifact directory.
- Do not leave setup in partial state.

4. Verify artifact integrity
- Generate `sha256sum` for each downloaded file.
- Save evidence file: `/Users/test/Code/UKDA/little_gini/internal-vlm/pull-evidence.md`
- Include: image digest, artifact names, sizes, checksums, and source URLs.

5. Runtime files under `/Users/test/Code/UKDA/little_gini/internal-vlm`
- `docker-compose.internal-vlm.yml`
- `.env.internal-vlm.example`
- `run-internal-vlm.sh`
- `README.md`

6. Runtime wiring
- Mount artifacts read-only.
- Bind to `127.0.0.1:8010`.
- Ensure endpoint contract works; add local gateway adapter if `/health` is missing.

7. Connect UKDE contracts
- Update `/Users/test/Code/UKDA/infra/models/catalog.phase-0.1.json` only if model label/artifact path changed.
- Keep service key `internal-vlm`.
- Update `/Users/test/Code/UKDA/infra/models/service-map.phase-0.1.json` only if topology changed.

8. Validation
- `curl -fsS http://127.0.0.1:8010/health`
- `curl -fsS http://127.0.0.1:8010/v1/models`
- `curl -fsS http://127.0.0.1:8010/v1/chat/completions -H 'Content-Type: application/json' -H 'Authorization: Bearer internal-local-dev' -d '{"model":"Qwen2.5-VL-3B-Instruct","messages":[{"role":"user","content":"Reply with OK"}],"max_tokens":8}'`
- Run API model-stack validation and confirm readiness remains healthy.

## Required Deliverables
- Pinned arm64 image digest and inspect output (`os/arch`).
- Downloaded artifact list with absolute paths.
- `sha256sum` and byte sizes for each required artifact.
- Runtime files and any catalog/service-map updates.
- Validation summary (pass/fail per check).
- Rollback steps.

## Definition of Done
- No missing-artifact errors during startup.
- All required artifacts exist on disk and are checksum-documented.
- Service boots and contract endpoints pass.
- UKDE model-stack validation passes.

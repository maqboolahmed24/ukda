# little_gini

This folder documents the local external-service requirements for running UKDA with internal model services.

## Scope

- All AI/model services run locally on `127.0.0.1`.
- No public AI API calls are required.
- Service wiring is defined by:
  - `/Users/test/Code/UKDA/infra/models/catalog.phase-0.1.json`
  - `/Users/test/Code/UKDA/infra/models/service-map.phase-0.1.json`

## Required Local Services

| Service | Role(s) | Protocol | Default Base URL | Required Endpoint(s) |
| --- | --- | --- | --- | --- |
| `internal-vlm` | `TRANSCRIPTION_PRIMARY` | `openai-compatible` | `http://127.0.0.1:8010/v1` | `/health`, `/v1/models`, `/v1/chat/completions` |
| `internal-llm` | `ASSIST` | `openai-compatible` | `http://127.0.0.1:8011/v1` | `/health`, `/v1/models`, `/v1/chat/completions` |
| `internal-embedding` | `EMBEDDING_SEARCH` | `openai-compatible` | `http://127.0.0.1:8012/v1` | `/health`, `/v1/models`, `/v1/embeddings` |
| `internal-ner` | `PRIVACY_NER` | `native` | `http://127.0.0.1:8020` | `/health` |
| `privacy-rules` | `PRIVACY_RULES` | `rules-native` | `http://127.0.0.1:8030` | `/health` |
| `kraken` | `TRANSCRIPTION_FALLBACK` | `native` | `http://127.0.0.1:8040` | `/health` |

## Model Roles (MacBook M1 Starter Mapping)

- `TRANSCRIPTION_PRIMARY` -> `Qwen2.5-VL-3B-Instruct` (run quantized, e.g. 4-bit)
- `ASSIST` -> `Qwen2.5-1.5B-Instruct` (quantized)
- `PRIVACY_NER` -> `GLiNER-small-v2.1`
- `PRIVACY_RULES` -> `Presidio`
- `TRANSCRIPTION_FALLBACK` -> `Kraken`
- `EMBEDDING_SEARCH` -> `bge-small-en-v1.5`

## Environment Requirements

- `MODEL_CATALOG_PATH` must point to the model catalog JSON.
- `MODEL_SERVICE_MAP_PATH` must point to the service-map JSON.
- `MODEL_DEPLOYMENT_ROOT` and `MODEL_ARTIFACT_ROOT` must be absolute paths outside this repository.
- Every model `artifact_path` must exist under deployment/artifact roots before startup.

## Quick Health Checks

```bash
curl -fsS http://127.0.0.1:8010/health
curl -fsS http://127.0.0.1:8011/health
curl -fsS http://127.0.0.1:8012/health
curl -fsS http://127.0.0.1:8020/health
curl -fsS http://127.0.0.1:8030/health
curl -fsS http://127.0.0.1:8040/health
```

If all endpoints return success, local model dependencies are ready for UKDA runtime.

## Full Wiring Verification

Run one consolidated contract check:

```bash
cd /Users/test/Code/UKDA
./little_gini/verify-model-stack.sh
```

This validates health, role-level functional smokes, API readiness, and model-stack configuration status.

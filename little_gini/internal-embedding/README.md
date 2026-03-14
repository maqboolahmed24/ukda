# internal-embedding setup (MacBook M1)

This service hosts the `EMBEDDING_SEARCH` role for UKDE with a local OpenAI-compatible endpoint.

## Image choice

- Pinned arm64 base image: `python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b`
- Built runtime image tag: `ukda/internal-embedding:arm64`
- Why: runs natively on `linux/arm64` and serves a local FastAPI OpenAI-compatible `/v1/embeddings` API over `sentence-transformers`.

Pulled base image reference:

```bash
docker pull --platform linux/arm64 python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b
docker image inspect python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b \
  --format 'os={{.Os}} arch={{.Architecture}} digest={{index .RepoDigests 0}}'
```

## Files in this folder

- `Dockerfile.internal-embedding`: pinned arm64 runtime image build
- `requirements.internal-embedding.txt`: API/runtime dependencies
- `embedding_api.py`: local OpenAI-compatible embeddings API
- `docker-compose.internal-embedding.yml`: service runtime
- `.env.internal-embedding.example`: local configuration template
- `run-internal-embedding.sh`: startup + health validation
- `pull-evidence.md`: image and artifact download evidence

## Artifact layout

`MODEL_ARTIFACT_ROOT` must be outside the repository and include:

```text
${MODEL_ARTIFACT_ROOT}/bge/bge-small-en-v1.5/
  config.json
  tokenizer.json
  model.safetensors
  ... (supporting tokenizer/sentence-transformer files)
```

Default source: `BAAI/bge-small-en-v1.5`.

## Start

```bash
cd /Users/test/Code/UKDA/little_gini/internal-embedding
cp -n .env.internal-embedding.example .env.internal-embedding
./run-internal-embedding.sh
```

## Stop

```bash
cd /Users/test/Code/UKDA/little_gini/internal-embedding
docker compose --env-file .env.internal-embedding -f docker-compose.internal-embedding.yml down
```

## UKDE wiring

Catalog role should map:
- `EMBEDDING_SEARCH -> internal-embedding -> bge-small-en-v1.5`

Service map base URL should stay:
- `http://127.0.0.1:8012/v1`

## Validation

```bash
curl -fsS http://127.0.0.1:8012/health
curl -fsS http://127.0.0.1:8012/v1/models
curl -fsS http://127.0.0.1:8012/v1/embeddings \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer internal-local-dev' \
  -d '{
    "model": "bge-small-en-v1.5",
    "input": "UKDA embedding smoke test"
  }'
```

## Troubleshooting

- If startup fails, inspect logs:
  - `docker compose --env-file .env.internal-embedding -f docker-compose.internal-embedding.yml logs -f internal-embedding-engine`
- If model load fails, verify files under `MODEL_ARTIFACT_ROOT/bge/bge-small-en-v1.5`.

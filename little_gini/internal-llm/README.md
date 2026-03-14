# internal-llm setup (MacBook M1)

This service hosts the `ASSIST` role for UKDE with a local OpenAI-compatible endpoint.

## Image choice

- Base image: `ghcr.io/ggml-org/llama.cpp`
- Pinned arm64 digest: `sha256:93b95b367a10b6e417abc1974f2e1f376df3ff6fc8723f90080daa160f60d9a5`
- Why: publishes `linux/arm64`, supports Qwen2.5 GGUF text models, and provides OpenAI-compatible server endpoints.

Pulled image reference:

```bash
docker pull ghcr.io/ggml-org/llama.cpp@sha256:93b95b367a10b6e417abc1974f2e1f376df3ff6fc8723f90080daa160f60d9a5
docker image inspect ghcr.io/ggml-org/llama.cpp@sha256:93b95b367a10b6e417abc1974f2e1f376df3ff6fc8723f90080daa160f60d9a5 \
  --format 'os={{.Os}} arch={{.Architecture}} digest={{index .RepoDigests 0}}'
```

## Files in this folder

- `docker-compose.internal-llm.yml`: engine + gateway stack
- `nginx.internal-llm.conf`: exposes UKDE contract routes at `127.0.0.1:8011`
- `.env.internal-llm.example`: local configuration template
- `run-internal-llm.sh`: startup + engine health + functional smoke
- `pull-evidence.md`: image and artifact download evidence

## Artifact layout

`MODEL_ARTIFACT_ROOT` must be outside the repository and include:

```text
${MODEL_ARTIFACT_ROOT}/qwen/qwen2.5-1.5b-instruct/
  qwen2.5-1.5b-instruct-q4_k_m.gguf
```

The default source for this file is `Qwen/Qwen2.5-1.5B-Instruct-GGUF`.

## Start

```bash
cd /Users/test/Code/UKDA/little_gini/internal-llm
cp -n .env.internal-llm.example .env.internal-llm
./run-internal-llm.sh
```

## Stop

```bash
cd /Users/test/Code/UKDA/little_gini/internal-llm
docker compose --env-file .env.internal-llm -f docker-compose.internal-llm.yml down
```

## UKDE wiring

Catalog role should map:
- `ASSIST -> internal-llm -> Qwen2.5-1.5B-Instruct`

Service map base URL should stay:
- `http://127.0.0.1:8011/v1`

## Validation

```bash
curl -fsS http://127.0.0.1:8011/health
curl -fsS http://127.0.0.1:8011/v1/models
curl -fsS http://127.0.0.1:8011/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer internal-local-dev' \
  -d '{
    "model": "Qwen2.5-1.5B-Instruct",
    "messages": [{"role": "user", "content": "Reply with OK"}],
    "max_tokens": 8
  }'
```

## Troubleshooting

- If `/health` fails, inspect logs:
  - `docker compose --env-file .env.internal-llm -f docker-compose.internal-llm.yml logs -f internal-llm-engine`
- If model load fails, verify `.env.internal-llm` model file path.
- If engine health is not `healthy`, verify compose healthcheck target:
  - `http://localhost:8000/v1/models` inside `internal-llm-engine`.

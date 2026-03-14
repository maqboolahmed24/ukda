# internal-ner setup (MacBook M1)

This service hosts the `PRIVACY_NER` role for UKDE with a local native endpoint.

## Image choice

- Pinned arm64 base image: `python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b`
- Built runtime image tag: `ukda/internal-ner:arm64`
- Why: runs natively on `linux/arm64` and serves local GLiNER inference without external API calls.

Pulled base image reference:

```bash
docker pull --platform linux/arm64 python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b
docker image inspect python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b \
  --format 'os={{.Os}} arch={{.Architecture}} digest={{index .RepoDigests 0}}'
```

## Files in this folder

- `Dockerfile.internal-ner`: pinned arm64 runtime image build
- `requirements.internal-ner.txt`: API/runtime dependencies
- `ner_api.py`: local native GLiNER API (`/health`, `/analyze`)
- `docker-compose.internal-ner.yml`: service runtime
- `.env.internal-ner.example`: local configuration template
- `run-internal-ner.sh`: startup + health validation
- `pull-evidence.md`: image and artifact download evidence

## Artifact layout

`MODEL_ARTIFACT_ROOT` must be outside the repository and include:

```text
${MODEL_ARTIFACT_ROOT}/gliner/gliner-small-v2.1/
  gliner_config.json
  pytorch_model.bin
  config.json
  tokenizer_config.json
  spm.model
  encoder/config.json
```

Source repos:
- `urchade/gliner_small-v2.1`
- `microsoft/deberta-v3-small` (tokenizer/config files for offline local runtime)

## Start

```bash
cd /Users/test/Code/UKDA/little_gini/internal-ner
cp -n .env.internal-ner.example .env.internal-ner
./run-internal-ner.sh
```

## Stop

```bash
cd /Users/test/Code/UKDA/little_gini/internal-ner
docker compose --env-file .env.internal-ner -f docker-compose.internal-ner.yml down
```

## UKDE wiring

Catalog role remains:
- `PRIVACY_NER -> internal-ner -> GLiNER-small-v2.1`

Service map base URL remains:
- `http://127.0.0.1:8020`

## Validation

```bash
curl -fsS http://127.0.0.1:8020/health
curl -fsS http://127.0.0.1:8020/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "John Doe sent an email to jane@example.com in London",
    "labels": ["person", "email", "location"],
    "threshold": 0.3
  }'
```

## Troubleshooting

- If startup fails, inspect logs:
  - `docker compose --env-file .env.internal-ner -f docker-compose.internal-ner.yml logs -f internal-ner-engine`
- If model load fails, verify files under `MODEL_ARTIFACT_ROOT/gliner/gliner-small-v2.1`.

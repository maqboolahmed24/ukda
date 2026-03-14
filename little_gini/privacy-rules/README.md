# privacy-rules setup (MacBook M1)

This service hosts the `PRIVACY_RULES` role for UKDE with a local Presidio analyzer endpoint.

## Image choice

- Pinned arm64 base image: `python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b`
- Built runtime image tag: `ukda/privacy-rules:arm64`
- Why: runs natively on `linux/arm64` and serves local Presidio analysis with persistent spaCy assets.

Pulled base image reference:

```bash
docker pull --platform linux/arm64 python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b
docker image inspect python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b \
  --format 'os={{.Os}} arch={{.Architecture}} digest={{index .RepoDigests 0}}'
```

## Files in this folder

- `Dockerfile.privacy-rules`: pinned arm64 runtime image build
- `requirements.privacy-rules.txt`: API/runtime dependencies
- `privacy_rules_api.py`: local Presidio API (`/health`, `/analyze`)
- `docker-compose.privacy-rules.yml`: service runtime
- `.env.privacy-rules.example`: local configuration template
- `run-privacy-rules.sh`: startup + health validation
- `pull-evidence.md`: image and asset download evidence

## Artifact layout

`MODEL_ARTIFACT_ROOT` must be outside the repository and include:

```text
${MODEL_ARTIFACT_ROOT}/presidio/default/
  en_core_web_sm-3.8.0-py3-none-any.whl
  en_core_web_sm/en_core_web_sm-3.8.0/
    meta.json
    config.cfg
    tokenizer
    vocab/strings.json
    ...
```

Source model wheel:
- `en_core_web_sm-3.8.0` from spaCy models releases.

## Start

```bash
cd /Users/test/Code/UKDA/little_gini/privacy-rules
cp -n .env.privacy-rules.example .env.privacy-rules
./run-privacy-rules.sh
```

## Stop

```bash
cd /Users/test/Code/UKDA/little_gini/privacy-rules
docker compose --env-file .env.privacy-rules -f docker-compose.privacy-rules.yml down
```

## UKDE wiring

Catalog role remains:
- `PRIVACY_RULES -> privacy-rules -> Presidio`

Service map base URL remains:
- `http://127.0.0.1:8030`

## Validation

```bash
curl -fsS http://127.0.0.1:8030/health
curl -fsS http://127.0.0.1:8030/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "John Doe email is john@example.com and phone 555-123-9876",
    "language": "en"
  }'
```

## Troubleshooting

- If startup fails, inspect logs:
  - `docker compose --env-file .env.privacy-rules -f docker-compose.privacy-rules.yml logs -f privacy-rules-engine`
- If analyzer fails to load, verify spaCy model files under
  `MODEL_ARTIFACT_ROOT/presidio/default/en_core_web_sm/en_core_web_sm-3.8.0`.

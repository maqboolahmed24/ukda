# internal-vlm setup (MacBook M1)

This service hosts the `TRANSCRIPTION_PRIMARY` role for UKDE with a local OpenAI-compatible endpoint.

## Image choice

- Base image: `ghcr.io/ggml-org/llama.cpp`
- Pinned arm64 digest: `sha256:93b95b367a10b6e417abc1974f2e1f376df3ff6fc8723f90080daa160f60d9a5`
- Why: publishes `linux/arm64`, directly supports `qwen2vl` architecture, and exposes OpenAI-compatible server routes.

Pulled image reference:

```bash
docker pull ghcr.io/ggml-org/llama.cpp@sha256:93b95b367a10b6e417abc1974f2e1f376df3ff6fc8723f90080daa160f60d9a5
docker image inspect ghcr.io/ggml-org/llama.cpp@sha256:93b95b367a10b6e417abc1974f2e1f376df3ff6fc8723f90080daa160f60d9a5 \
  --format 'os={{.Os}} arch={{.Architecture}} digest={{index .RepoDigests 0}}'
```

Expected inspect output includes `arch=arm64`.

## Files in this folder

- `docker-compose.internal-vlm.yml`: engine + Python gateway stack
- `Dockerfile.internal-vlm-gateway`: pinned arm64 gateway image build
- `requirements.internal-vlm-gateway.txt`: gateway dependencies
- `vlm_gateway_api.py`: multimodal payload adapter + pass-through proxy
- `.env.internal-vlm.example`: local configuration template
- `run-internal-vlm.sh`: startup + health + functional smokes

## Artifact layout

`MODEL_ARTIFACT_ROOT` must be outside the repository and include:

```text
${MODEL_ARTIFACT_ROOT}/qwen/qwen2.5-vl-3b-instruct/
  Qwen2.5-VL-3B-Instruct-q4_k_m.gguf
  Qwen2.5-VL-3B-Instruct-mmproj-f16.gguf
```

These names are defaults from `Mungert/Qwen2.5-VL-3B-Instruct-GGUF` and can be changed in `.env.internal-vlm`.
Download evidence is tracked in `pull-evidence.md`.
The current server path does not require a separate `--mmproj` argument for this model family.

## Gateway behavior

- `GET /health`: dependency-aware; checks both VLM engine and Kraken availability.
- `GET /v1/models`: pass-through to llama.cpp engine.
- `POST /v1/chat/completions`:
  - Text-only payloads pass through unchanged.
  - OpenAI-style multimodal parts with `image_url` are normalized by OCR:
    - Data URLs only (`data:image/...;base64,...`).
    - Remote URLs are rejected with `400`.
    - Each image becomes `[image_n_ocr]\\n<ocr_text>` in the flattened message content.
    - Kraken dependency errors return `503`.

## Start

```bash
cd /Users/test/Code/UKDA/little_gini/internal-vlm
cp -n .env.internal-vlm.example .env.internal-vlm
./run-internal-vlm.sh
```

## Stop

```bash
cd /Users/test/Code/UKDA/little_gini/internal-vlm
docker compose --env-file .env.internal-vlm -f docker-compose.internal-vlm.yml down
```

## UKDE wiring

No catalog or service-key change is required for this service.

- Catalog role remains:
  - `TRANSCRIPTION_PRIMARY -> internal-vlm -> Qwen2.5-VL-3B-Instruct`
- Service map base URL remains:
  - `http://127.0.0.1:8010/v1`

`.env` values should stay:

```bash
OPENAI_BASE_URL=http://127.0.0.1:8010/v1
OPENAI_API_KEY=internal-local-dev
```

This service accepts unauthenticated local requests by default; UKDE can still send
`OPENAI_API_KEY` and remain compatible.

## Validation

```bash
curl -fsS http://127.0.0.1:8010/health
curl -fsS http://127.0.0.1:8010/v1/models
curl -fsS http://127.0.0.1:8010/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer internal-local-dev' \
  -d '{
    "model": "Qwen2.5-VL-3B-Instruct",
    "messages": [{"role": "user", "content": "Reply with OK"}],
    "max_tokens": 8
  }'
```

Image payload smoke:

```bash
python - <<'PY' > /tmp/internal-vlm-image-request.json
import base64
import json
from pathlib import Path

img = Path('/Users/test/Code/UKDA/web/tests/browser/shell-regression.spec.ts-snapshots/login-light-darwin.png').read_bytes()
payload = base64.b64encode(img).decode('ascii')
print(json.dumps({
  "model": "Qwen2.5-VL-3B-Instruct",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "Read the heading text only."},
      {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{payload}"}}
    ]
  }],
  "max_tokens": 64
}))
PY

curl -fsS http://127.0.0.1:8010/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer internal-local-dev' \
  -d @/tmp/internal-vlm-image-request.json
```

For full UKDE readiness check:

```bash
cd /Users/test/Code/UKDA
source .venv/bin/activate
set -a && source .env && set +a
cd api
python -c "from app.core.config import get_settings; from app.core.model_stack import validate_model_stack; print(validate_model_stack(get_settings()))"
```

## Troubleshooting

- First boot rebuilds the FastAPI gateway image and should complete quickly.
- If `/health` fails, check engine logs:
  - `docker compose --env-file .env.internal-vlm -f docker-compose.internal-vlm.yml logs -f internal-vlm-engine`
- If `image_url` requests fail, check gateway logs:
  - `docker compose --env-file .env.internal-vlm -f docker-compose.internal-vlm.yml logs -f internal-vlm-gateway`
- If model load fails, verify file names in `.env.internal-vlm` exactly match artifact files.
- If performance is poor, reduce `INTERNAL_VLM_N_CTX` and tune `INTERNAL_VLM_THREADS`.

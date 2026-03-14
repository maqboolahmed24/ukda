# kraken setup (MacBook M1)

This service hosts the `TRANSCRIPTION_FALLBACK` role for UKDE with a local native OCR endpoint.

## Image choice

- Pinned arm64 base image: `python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b`
- Built runtime image tag: `ukda/kraken:arm64`
- Why: runs natively on `linux/arm64` and supports local Kraken OCR inference with persistent model assets.

Pulled base image reference:

```bash
docker pull --platform linux/arm64 python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b
docker image inspect python:3.11-slim@sha256:d64a1009c676551d50bdd2a0f9a4a5f63423a5f070d9284e00e4cba788953f4b \
  --format 'os={{.Os}} arch={{.Architecture}} digest={{index .RepoDigests 0}}'
```

## Files in this folder

- `Dockerfile.kraken`: pinned arm64 runtime image build
- `requirements.kraken.txt`: API/runtime dependencies
- `kraken_api.py`: local Kraken API (`/health`, `/ocr`, `/transcribe`)
- `docker-compose.kraken.yml`: service runtime
- `.env.kraken.example`: local configuration template
- `run-kraken.sh`: startup + health validation
- `pull-evidence.md`: image and artifact download evidence

## Artifact layout

`MODEL_ARTIFACT_ROOT` must be outside the repository and include:

```text
${MODEL_ARTIFACT_ROOT}/kraken/default/
  catmus-print-fondue-large.mlmodel
  blla.mlmodel
```

Model sources:
- OCR model DOI: `10.5281/zenodo.10592716`
- Segmentation model DOI: `10.5281/zenodo.14602569`

## Start

```bash
cd /Users/test/Code/UKDA/little_gini/kraken
cp -n .env.kraken.example .env.kraken
./run-kraken.sh
```

## Stop

```bash
cd /Users/test/Code/UKDA/little_gini/kraken
docker compose --env-file .env.kraken -f docker-compose.kraken.yml down
```

## UKDE wiring

Catalog role remains:
- `TRANSCRIPTION_FALLBACK -> kraken -> Kraken`

Service map base URL remains:
- `http://127.0.0.1:8040`

Expected fallback inference endpoint (native contract):
- `POST /ocr` (alias: `POST /transcribe`)

Request body shape:

```json
{
  "image_base64": "<base64 encoded image>",
  "reorder": true
}
```

Response shape:

```json
{
  "model": "Kraken",
  "text": "...",
  "elapsed_ms": 1234,
  "meta": {
    "engine": "kraken",
    "recognition_model": "catmus-print-fondue-large.mlmodel",
    "segmentation_model": "blla.mlmodel",
    "device": "cpu",
    "reorder": true,
    "log_excerpt": "..."
  }
}
```

## Validation

```bash
curl -fsS http://127.0.0.1:8040/health
```

Minimal OCR fallback smoke request:

```bash
python - <<'PY' | curl -fsS http://127.0.0.1:8040/ocr -H 'Content-Type: application/json' -d @-
import base64
import io
import json
from PIL import Image, ImageDraw

img = Image.new('RGB', (640, 160), 'white')
draw = ImageDraw.Draw(img)
draw.text((20, 60), 'hi how are you', fill='black')
buf = io.BytesIO()
img.save(buf, format='PNG')
print(json.dumps({'image_base64': base64.b64encode(buf.getvalue()).decode('ascii')}))
PY
```

## Troubleshooting

- If startup fails, inspect logs:
  - `docker compose --env-file .env.kraken -f docker-compose.kraken.yml logs -f kraken-engine`
- If OCR fails, verify both model files under `MODEL_ARTIFACT_ROOT/kraken/default`.
- If OCR latency is high, increase container CPU allocation in Docker Desktop.

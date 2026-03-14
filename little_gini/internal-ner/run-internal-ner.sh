#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.internal-ner"
EXAMPLE_FILE="${SCRIPT_DIR}/.env.internal-ner.example"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.internal-ner.yml"

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${EXAMPLE_FILE}" "${ENV_FILE}"
  echo "Created ${ENV_FILE}. Review and update model paths before first run."
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

if [[ "${MODEL_ARTIFACT_ROOT:-}" != /* ]]; then
  echo "MODEL_ARTIFACT_ROOT must be an absolute path. Current value: '${MODEL_ARTIFACT_ROOT:-}'" >&2
  exit 1
fi

MODEL_DIR="${MODEL_ARTIFACT_ROOT}/${INTERNAL_NER_MODEL_SUBPATH}"
required=(
  "gliner_config.json"
  "config.json"
  "tokenizer_config.json"
  "spm.model"
  "encoder/config.json"
)

for file in "${required[@]}"; do
  if [[ ! -f "${MODEL_DIR}/${file}" ]]; then
    echo "Missing required file: ${MODEL_DIR}/${file}" >&2
    exit 1
  fi
done

if [[ ! -f "${MODEL_DIR}/pytorch_model.bin" && ! -f "${MODEL_DIR}/model.safetensors" ]]; then
  echo "Missing model weights in ${MODEL_DIR}. Expected pytorch_model.bin or model.safetensors" >&2
  exit 1
fi

echo "Starting internal-ner stack..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --build

echo "Waiting for /health..."
for _ in {1..120}; do
  if curl -fsS "http://${INTERNAL_NER_LISTEN_HOST}:${INTERNAL_NER_LISTEN_PORT}/health" >/dev/null; then
    break
  fi
  sleep 2
done

curl -fsS "http://${INTERNAL_NER_LISTEN_HOST}:${INTERNAL_NER_LISTEN_PORT}/health" >/dev/null

echo "internal-ner is up on http://${INTERNAL_NER_LISTEN_HOST}:${INTERNAL_NER_LISTEN_PORT}"
echo "Role PRIVACY_NER model alias: ${INTERNAL_NER_MODEL_ALIAS}"

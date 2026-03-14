#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.internal-embedding"
EXAMPLE_FILE="${SCRIPT_DIR}/.env.internal-embedding.example"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.internal-embedding.yml"

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

MODEL_DIR="${MODEL_ARTIFACT_ROOT}/${INTERNAL_EMBEDDING_MODEL_SUBPATH}"
for required in config.json tokenizer.json model.safetensors; do
  if [[ ! -f "${MODEL_DIR}/${required}" ]]; then
    echo "Missing required file: ${MODEL_DIR}/${required}" >&2
    exit 1
  fi
done

echo "Starting internal-embedding stack..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --build

echo "Waiting for /health..."
for _ in {1..120}; do
  if curl -fsS "http://${INTERNAL_EMBEDDING_LISTEN_HOST}:${INTERNAL_EMBEDDING_LISTEN_PORT}/health" >/dev/null; then
    break
  fi
  sleep 2
done

curl -fsS "http://${INTERNAL_EMBEDDING_LISTEN_HOST}:${INTERNAL_EMBEDDING_LISTEN_PORT}/health" >/dev/null
curl -fsS "http://${INTERNAL_EMBEDDING_LISTEN_HOST}:${INTERNAL_EMBEDDING_LISTEN_PORT}/v1/models" >/dev/null

echo "internal-embedding is up on http://${INTERNAL_EMBEDDING_LISTEN_HOST}:${INTERNAL_EMBEDDING_LISTEN_PORT}"
echo "Role EMBEDDING_SEARCH model alias: ${INTERNAL_EMBEDDING_MODEL_ALIAS}"

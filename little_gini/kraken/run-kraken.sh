#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.kraken"
EXAMPLE_FILE="${SCRIPT_DIR}/.env.kraken.example"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.kraken.yml"

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

MODEL_DIR="${MODEL_ARTIFACT_ROOT}/${KRAKEN_MODEL_SUBPATH}"
required=(
  "${KRAKEN_RECOGNITION_MODEL_FILE}"
  "${KRAKEN_SEGMENTATION_MODEL_FILE}"
)

for file in "${required[@]}"; do
  if [[ ! -f "${MODEL_DIR}/${file}" ]]; then
    echo "Missing required Kraken model file: ${MODEL_DIR}/${file}" >&2
    exit 1
  fi
done

echo "Starting kraken stack..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --build

echo "Waiting for /health..."
for _ in {1..120}; do
  if curl -fsS "http://${KRAKEN_LISTEN_HOST}:${KRAKEN_LISTEN_PORT}/health" >/dev/null; then
    break
  fi
  sleep 2
done

curl -fsS "http://${KRAKEN_LISTEN_HOST}:${KRAKEN_LISTEN_PORT}/health" >/dev/null

echo "kraken is up on http://${KRAKEN_LISTEN_HOST}:${KRAKEN_LISTEN_PORT}"
echo "Role TRANSCRIPTION_FALLBACK model alias: ${KRAKEN_MODEL_ALIAS}"

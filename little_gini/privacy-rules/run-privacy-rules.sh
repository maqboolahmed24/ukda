#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.privacy-rules"
EXAMPLE_FILE="${SCRIPT_DIR}/.env.privacy-rules.example"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.privacy-rules.yml"

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

MODEL_DIR="${MODEL_ARTIFACT_ROOT}/${PRIVACY_RULES_MODEL_SUBPATH}/${PRIVACY_RULES_SPACY_MODEL_REL_PATH}"
required=(
  "meta.json"
  "config.cfg"
  "tokenizer"
  "vocab/strings.json"
)

for file in "${required[@]}"; do
  if [[ ! -e "${MODEL_DIR}/${file}" ]]; then
    echo "Missing required spaCy asset: ${MODEL_DIR}/${file}" >&2
    exit 1
  fi
done

echo "Starting privacy-rules stack..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --build

echo "Waiting for /health..."
for _ in {1..120}; do
  if curl -fsS "http://${PRIVACY_RULES_LISTEN_HOST}:${PRIVACY_RULES_LISTEN_PORT}/health" >/dev/null; then
    break
  fi
  sleep 2
done

curl -fsS "http://${PRIVACY_RULES_LISTEN_HOST}:${PRIVACY_RULES_LISTEN_PORT}/health" >/dev/null

echo "privacy-rules is up on http://${PRIVACY_RULES_LISTEN_HOST}:${PRIVACY_RULES_LISTEN_PORT}"
echo "Role PRIVACY_RULES engine: ${PRIVACY_RULES_SERVICE_NAME}"

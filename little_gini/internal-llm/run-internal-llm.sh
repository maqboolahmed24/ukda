#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.internal-llm"
EXAMPLE_FILE="${SCRIPT_DIR}/.env.internal-llm.example"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.internal-llm.yml"

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

MODEL_PATH="${MODEL_ARTIFACT_ROOT}/${INTERNAL_LLM_MODEL_SUBPATH}/${INTERNAL_LLM_MODEL_FILE}"
if [[ ! -f "${MODEL_PATH}" ]]; then
  echo "Missing model file: ${MODEL_PATH}" >&2
  exit 1
fi

wait_for_engine_health() {
  local engine_container
  engine_container="$(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps -q internal-llm-engine)"
  if [[ -z "${engine_container}" ]]; then
    echo "Unable to resolve internal-llm-engine container id" >&2
    exit 1
  fi

  echo "Waiting for internal-llm-engine health status..."
  local health_status="starting"
  for _ in {1..120}; do
    health_status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${engine_container}")"
    if [[ "${health_status}" == "healthy" ]]; then
      return 0
    fi
    sleep 2
  done

  echo "internal-llm-engine health did not become healthy (last status: ${health_status})" >&2
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" logs --tail 100 internal-llm-engine >&2 || true
  exit 1
}

smoke_text_chat() {
  local response_file
  response_file="$(mktemp)"

  curl -fsS "http://${INTERNAL_LLM_LISTEN_HOST}:${INTERNAL_LLM_LISTEN_PORT}/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -H 'Authorization: Bearer internal-local-dev' \
    -d "{
      \"model\": \"${INTERNAL_LLM_MODEL_ALIAS}\",
      \"messages\": [{\"role\": \"user\", \"content\": \"Reply with OK only.\"}],
      \"max_tokens\": 16
    }" >"${response_file}"

  python3 - "${response_file}" <<'PY'
import json
import sys

payload_path = sys.argv[1]
with open(payload_path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
if not content:
    raise SystemExit("internal-llm text smoke failed: empty assistant response")
print("internal-llm text smoke passed.")
PY
  rm -f "${response_file}"
}

echo "Starting internal-llm stack..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d

wait_for_engine_health

echo "Waiting for /health..."
for _ in {1..90}; do
  if curl -fsS "http://${INTERNAL_LLM_LISTEN_HOST}:${INTERNAL_LLM_LISTEN_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

curl -fsS "http://${INTERNAL_LLM_LISTEN_HOST}:${INTERNAL_LLM_LISTEN_PORT}/health" >/dev/null
curl -fsS "http://${INTERNAL_LLM_LISTEN_HOST}:${INTERNAL_LLM_LISTEN_PORT}/v1/models" >/dev/null
smoke_text_chat

echo "internal-llm is up on http://${INTERNAL_LLM_LISTEN_HOST}:${INTERNAL_LLM_LISTEN_PORT}"
echo "Role ASSIST model alias: ${INTERNAL_LLM_MODEL_ALIAS}"

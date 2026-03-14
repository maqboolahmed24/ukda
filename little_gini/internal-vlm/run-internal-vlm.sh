#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.internal-vlm"
EXAMPLE_FILE="${SCRIPT_DIR}/.env.internal-vlm.example"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.internal-vlm.yml"

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

MODEL_PATH="${MODEL_ARTIFACT_ROOT}/${INTERNAL_VLM_MODEL_SUBPATH}/${INTERNAL_VLM_MODEL_FILE}"
MMPROJ_PATH="${MODEL_ARTIFACT_ROOT}/${INTERNAL_VLM_MODEL_SUBPATH}/${INTERNAL_VLM_MMPROJ_FILE}"

if [[ ! -f "${MODEL_PATH}" ]]; then
  echo "Missing model file: ${MODEL_PATH}" >&2
  exit 1
fi

if [[ ! -f "${MMPROJ_PATH}" ]]; then
  echo "Missing projector file: ${MMPROJ_PATH}" >&2
  exit 1
fi

wait_for_engine_health() {
  local engine_container
  engine_container="$(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps -q internal-vlm-engine)"
  if [[ -z "${engine_container}" ]]; then
    echo "Unable to resolve internal-vlm-engine container id" >&2
    exit 1
  fi

  echo "Waiting for internal-vlm-engine health status..."
  local health_status="starting"
  for _ in {1..120}; do
    health_status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${engine_container}")"
    if [[ "${health_status}" == "healthy" ]]; then
      return 0
    fi
    sleep 2
  done

  echo "internal-vlm-engine health did not become healthy (last status: ${health_status})" >&2
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" logs --tail 100 internal-vlm-engine >&2 || true
  exit 1
}

resolve_smoke_image_path() {
  local candidate="${REPO_ROOT}/web/tests/browser/shell-regression.spec.ts-snapshots/login-light-darwin.png"
  if [[ -n "${INTERNAL_VLM_SMOKE_IMAGE_PATH:-}" ]]; then
    candidate="${INTERNAL_VLM_SMOKE_IMAGE_PATH}"
  fi
  if [[ -f "${candidate}" ]]; then
    echo "${candidate}"
    return 0
  fi

  local fallback
  fallback="$(cd "${REPO_ROOT}" && rg --files web/tests/browser -g '*.png' | head -n1 || true)"
  if [[ -n "${fallback}" && -f "${REPO_ROOT}/${fallback}" ]]; then
    echo "${REPO_ROOT}/${fallback}"
    return 0
  fi

  echo "Unable to locate a PNG sample image for VLM image smoke test" >&2
  exit 1
}

smoke_text_chat() {
  local response_file
  response_file="$(mktemp)"

  curl -fsS "http://${INTERNAL_VLM_LISTEN_HOST}:${INTERNAL_VLM_LISTEN_PORT}/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -H 'Authorization: Bearer internal-local-dev' \
    -d "{
      \"model\": \"${INTERNAL_VLM_MODEL_ALIAS}\",
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
    raise SystemExit("internal-vlm text smoke failed: empty assistant response")
print("internal-vlm text smoke passed.")
PY

  rm -f "${response_file}"
}

smoke_image_chat() {
  local image_path request_file response_file
  image_path="$(resolve_smoke_image_path)"
  request_file="$(mktemp)"
  response_file="$(mktemp)"

  python3 - "${image_path}" "${INTERNAL_VLM_MODEL_ALIAS}" >"${request_file}" <<'PY'
import base64
import json
import sys

image_path = sys.argv[1]
model_alias = sys.argv[2]
with open(image_path, "rb") as handle:
    payload = base64.b64encode(handle.read()).decode("ascii")

request = {
    "model": model_alias,
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Read the first visible heading only."},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{payload}"},
                },
            ],
        }
    ],
    "max_tokens": 64,
}
print(json.dumps(request))
PY

  curl -fsS "http://${INTERNAL_VLM_LISTEN_HOST}:${INTERNAL_VLM_LISTEN_PORT}/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -H 'Authorization: Bearer internal-local-dev' \
    -d @"${request_file}" >"${response_file}"

  python3 - "${response_file}" <<'PY'
import json
import sys

payload_path = sys.argv[1]
with open(payload_path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
if not content:
    raise SystemExit("internal-vlm image smoke failed: empty assistant response")
print("internal-vlm image smoke passed.")
PY

  rm -f "${request_file}" "${response_file}"
}

echo "Starting internal-vlm stack..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --build

wait_for_engine_health

echo "Waiting for /health..."
for _ in {1..60}; do
  if curl -fsS "http://${INTERNAL_VLM_LISTEN_HOST}:${INTERNAL_VLM_LISTEN_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

curl -fsS "http://${INTERNAL_VLM_LISTEN_HOST}:${INTERNAL_VLM_LISTEN_PORT}/health" >/dev/null
curl -fsS "http://${INTERNAL_VLM_LISTEN_HOST}:${INTERNAL_VLM_LISTEN_PORT}/v1/models" >/dev/null
smoke_text_chat
smoke_image_chat

echo "internal-vlm is up on http://${INTERNAL_VLM_LISTEN_HOST}:${INTERNAL_VLM_LISTEN_PORT}"
echo "Use this in UKDE: OPENAI_BASE_URL=http://${INTERNAL_VLM_LISTEN_HOST}:${INTERNAL_VLM_LISTEN_PORT}/v1"

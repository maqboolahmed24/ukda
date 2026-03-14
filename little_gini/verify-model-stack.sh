#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

pass() {
  echo "PASS: $1"
}

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

require_non_empty_chat() {
  local payload_file="$1"
  local response_file="$2"
  local label="$3"
  curl -fsS "http://127.0.0.1:8010/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -H 'Authorization: Bearer internal-local-dev' \
    -d @"${payload_file}" >"${response_file}"

  python3 - "${response_file}" "${label}" <<'PY'
import json
import sys

response_path, label = sys.argv[1], sys.argv[2]
with open(response_path, "r", encoding="utf-8") as handle:
    data = json.load(handle)
content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
if not content:
    raise SystemExit(f"{label} returned empty assistant content")
PY
}

echo "== Health checks =="
for url in \
  http://127.0.0.1:8010/health \
  http://127.0.0.1:8011/health \
  http://127.0.0.1:8012/health \
  http://127.0.0.1:8020/health \
  http://127.0.0.1:8030/health \
  http://127.0.0.1:8040/health
do
  curl -fsS "${url}" >/dev/null || fail "${url}"
  pass "${url}"
done

echo "== Functional role checks =="

llm_response="$(mktemp)"
curl -fsS "http://127.0.0.1:8011/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer internal-local-dev' \
  -d '{
    "model": "Qwen2.5-1.5B-Instruct",
    "messages": [{"role": "user", "content": "Reply with OK only."}],
    "max_tokens": 16
  }' >"${llm_response}"
python3 - "${llm_response}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)
content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
if not content:
    raise SystemExit("internal-llm returned empty assistant content")
PY
rm -f "${llm_response}"
pass "internal-llm /v1/chat/completions text"

vlm_text_request="$(mktemp)"
vlm_text_response="$(mktemp)"
cat >"${vlm_text_request}" <<'JSON'
{
  "model": "Qwen2.5-VL-3B-Instruct",
  "messages": [{"role": "user", "content": "Reply with OK only."}],
  "max_tokens": 16
}
JSON
require_non_empty_chat "${vlm_text_request}" "${vlm_text_response}" "internal-vlm text chat"
rm -f "${vlm_text_request}" "${vlm_text_response}"
pass "internal-vlm /v1/chat/completions text"

sample_image="${REPO_ROOT}/web/tests/browser/shell-regression.spec.ts-snapshots/login-light-darwin.png"
if [[ ! -f "${sample_image}" ]]; then
  fallback="$(cd "${REPO_ROOT}" && rg --files web/tests/browser -g '*.png' | head -n1 || true)"
  [[ -n "${fallback}" ]] || fail "no PNG sample image found for VLM/Kraken image smoke"
  sample_image="${REPO_ROOT}/${fallback}"
fi

vlm_image_request="$(mktemp)"
vlm_image_response="$(mktemp)"
python3 - "${sample_image}" >"${vlm_image_request}" <<'PY'
import base64
import json
import sys

image_path = sys.argv[1]
with open(image_path, "rb") as handle:
    payload = base64.b64encode(handle.read()).decode("ascii")

request = {
    "model": "Qwen2.5-VL-3B-Instruct",
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": "Read the first visible heading only."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{payload}"}}
        ],
    }],
    "max_tokens": 64,
}
print(json.dumps(request))
PY
require_non_empty_chat "${vlm_image_request}" "${vlm_image_response}" "internal-vlm image chat"
rm -f "${vlm_image_request}" "${vlm_image_response}"
pass "internal-vlm /v1/chat/completions image_url"

embed_response="$(mktemp)"
curl -fsS "http://127.0.0.1:8012/v1/embeddings" \
  -H 'Content-Type: application/json' \
  -d '{"model":"bge-small-en-v1.5","input":"hello world"}' >"${embed_response}"
python3 - "${embed_response}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)
embedding = (((data.get("data") or [{}])[0]).get("embedding") or [])
if not embedding:
    raise SystemExit("internal-embedding returned empty embedding")
PY
rm -f "${embed_response}"
pass "internal-embedding /v1/embeddings"

ner_response="$(mktemp)"
curl -fsS "http://127.0.0.1:8020/analyze" \
  -H 'Content-Type: application/json' \
  -d '{"text":"John Doe email is john@example.com in London","labels":["person","email","location"],"threshold":0.3}' >"${ner_response}"
python3 - "${ner_response}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)
entities = data.get("entities") or []
if len(entities) < 1:
    raise SystemExit("internal-ner returned no entities")
PY
rm -f "${ner_response}"
pass "internal-ner /analyze"

privacy_response="$(mktemp)"
curl -fsS "http://127.0.0.1:8030/analyze" \
  -H 'Content-Type: application/json' \
  -d '{"text":"John Doe email is john@example.com and phone 555-123-9876","language":"en"}' >"${privacy_response}"
python3 - "${privacy_response}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)
findings = data.get("findings") or []
if len(findings) < 1:
    raise SystemExit("privacy-rules returned no findings")
PY
rm -f "${privacy_response}"
pass "privacy-rules /analyze"

kraken_request="$(mktemp)"
kraken_response="$(mktemp)"
python3 - "${sample_image}" >"${kraken_request}" <<'PY'
import base64
import json
import sys

with open(sys.argv[1], "rb") as handle:
    payload = base64.b64encode(handle.read()).decode("ascii")
print(json.dumps({"image_base64": payload}))
PY
curl -fsS "http://127.0.0.1:8040/ocr" \
  -H 'Content-Type: application/json' \
  -d @"${kraken_request}" >"${kraken_response}"
python3 - "${kraken_response}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)
text = (data.get("text") or "").strip()
if not text:
    raise SystemExit("kraken returned empty OCR text")
PY
rm -f "${kraken_request}" "${kraken_response}"
pass "kraken /ocr"

echo "== API readiness checks =="
curl -fsS http://127.0.0.1:8000/healthz >/dev/null || fail "api /healthz"
pass "api /healthz"
curl -fsS http://127.0.0.1:8000/readyz >/dev/null || fail "api /readyz"
pass "api /readyz"

echo "== Model stack validation =="
[[ -f "${REPO_ROOT}/.venv/bin/activate" ]] || fail "missing python virtual env at ${REPO_ROOT}/.venv"
[[ -f "${REPO_ROOT}/.env" ]] || fail "missing ${REPO_ROOT}/.env"

# shellcheck disable=SC1091
source "${REPO_ROOT}/.venv/bin/activate"
set -a
# shellcheck disable=SC1090
source "${REPO_ROOT}/.env"
set +a

validation_output="$(cd "${REPO_ROOT}/api" && python - <<'PY'
from app.core.config import get_settings
from app.core.model_stack import validate_model_stack

result = validate_model_stack(get_settings())
print(result.status)
print(result.detail)
PY
)"

validation_status="$(printf '%s\n' "${validation_output}" | sed -n '1p')"
validation_detail="$(printf '%s\n' "${validation_output}" | sed -n '2p')"
[[ "${validation_status}" == "ok" ]] || fail "model stack validation: ${validation_detail}"
pass "model stack validation (${validation_detail})"

echo "All model-stack checks passed."

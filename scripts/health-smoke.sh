#!/usr/bin/env bash
set -euo pipefail

WEB_URL="${1:-http://127.0.0.1:3000/health}"
API_URL="${2:-http://127.0.0.1:8000/healthz}"

echo "Checking API endpoint: ${API_URL}"
api_status="$(curl -sS -o /tmp/ukde-api-health.json -w "%{http_code}" "${API_URL}")"
if [[ "${api_status}" != "200" ]]; then
  echo "API health endpoint failed with status ${api_status}."
  exit 1
fi

echo "Checking web diagnostics route: ${WEB_URL}"
curl -sS "${WEB_URL}" > /tmp/ukde-web-health.html

if ! grep -q "Service status:" /tmp/ukde-web-health.html; then
  echo "Web diagnostics route did not render service status text."
  exit 1
fi

if ! grep -Eq "Liveness( <!-- -->)?OK" /tmp/ukde-web-health.html; then
  echo "Web diagnostics route did not render live liveness data from the API."
  exit 1
fi

echo "Health smoke passed."

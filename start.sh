#!/usr/bin/env bash
set -euo pipefail

if [[ "${OSTYPE:-}" != darwin* ]]; then
  echo "start.sh currently supports macOS (Terminal.app) only." >&2
  exit 1
fi

if ! command -v osascript >/dev/null 2>&1; then
  echo "osascript is required but not available." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="${ROOT_DIR}/web"
WEB_LOCK_FILE="${WEB_DIR}/.next/dev/lock"
WEB_NEXT_DEV_DIR="${WEB_DIR}/.next/dev"
MODEL_ROOT="${HOME}/Library/Application Support/UKDataExtraction/models"
QWEN_LINK="${MODEL_ROOT}/qwen/qwen3-4b"
QWEN_TARGET="${MODEL_ROOT}/qwen/qwen2.5-1.5b-instruct"

log() {
  printf '%s\n' "[start.sh] $*"
}

stop_stale_web_dev() {
  local pid cmd cwd matched
  matched=0
  while IFS= read -r pid; do
    [[ -n "${pid}" ]] || continue
    cmd="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
    cwd="$(lsof -a -p "${pid}" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1)"
    if [[ "${cmd}" == *"${ROOT_DIR}/web/"* ]] || [[ "${cwd}" == "${WEB_DIR}"* ]]; then
      matched=1
      log "Stopping stale web dev process ${pid}"
      kill "${pid}" 2>/dev/null || true
    fi
  done < <(pgrep -f "next dev|next-server" || true)

  if [[ "${matched}" -eq 1 ]]; then
    sleep 1
  fi
}

clear_stale_web_lock() {
  if [[ ! -e "${WEB_LOCK_FILE}" ]]; then
    return
  fi
  if lsof "${WEB_LOCK_FILE}" >/dev/null 2>&1; then
    log "Next lock is currently in use; leaving ${WEB_LOCK_FILE} intact"
    return
  fi
  log "Removing stale Next lock ${WEB_LOCK_FILE}"
  rm -f "${WEB_LOCK_FILE}"
}

reset_web_dev_cache() {
  if [[ -d "${WEB_NEXT_DEV_DIR}" ]]; then
    log "Clearing stale Next dev cache ${WEB_NEXT_DEV_DIR}"
    rm -rf "${WEB_NEXT_DEV_DIR}"
  fi
}

free_web_port_if_stale_next() {
  local pid cmd
  pid="$(lsof -nP -iTCP:3000 -sTCP:LISTEN -t 2>/dev/null | head -n 1 || true)"
  if [[ -z "${pid}" ]]; then
    return
  fi
  cmd="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
  if [[ "${cmd}" == *"next"* ]]; then
    log "Port 3000 held by stale Next process ${pid}; stopping it"
    kill "${pid}" 2>/dev/null || true
    sleep 1
    return
  fi
  log "Port 3000 is in use by non-Next process (${pid}); web may start on a different port"
}

log "Running web startup preflight checks"
stop_stale_web_dev
clear_stale_web_lock
reset_web_dev_cache
free_web_port_if_stale_next

osascript <<APPLESCRIPT
set rootDir to quoted form of "${ROOT_DIR}"
set qwenLink to quoted form of "${QWEN_LINK}"
set qwenTarget to quoted form of "${QWEN_TARGET}"

set modelCmd to "cd " & rootDir & " && make dev-db-up && if [ ! -e " & qwenLink & " ]; then ln -s " & qwenTarget & " " & qwenLink & "; fi && cd little_gini/kraken && ./run-kraken.sh && cd ../internal-llm && ./run-internal-llm.sh && cd ../internal-embedding && ./run-internal-embedding.sh && cd ../internal-ner && ./run-internal-ner.sh && cd ../privacy-rules && ./run-privacy-rules.sh && cd ../internal-vlm && ./run-internal-vlm.sh"
set apiCmd to "cd " & rootDir & " && source .venv/bin/activate && python -m dotenv -f .env run -- python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --app-dir api"
set webCmd to "cd " & rootDir & " && source .venv/bin/activate && python -m dotenv -f .env run -- pnpm --filter @ukde/web dev"
set workerCmd to "cd " & rootDir & " && source .venv/bin/activate && python -m dotenv -f .env run -- ukde-worker run"

tell application "Terminal"
  activate
  do script modelCmd
  do script apiCmd
  do script webCmd
  do script workerCmd
end tell
APPLESCRIPT

echo "Startup launched in Terminal tabs."
echo "Web: http://localhost:3000"
echo "API: http://127.0.0.1:8000/healthz"
echo "Worker: ukde-worker run"

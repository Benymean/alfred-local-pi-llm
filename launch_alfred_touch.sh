#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PORT="${ALFRED_TOUCH_PORT:-8081}"
APP_URL="http://127.0.0.1:${PORT}/"
HEALTH_URL="http://127.0.0.1:${PORT}/api/health"
LOG_FILE="${ROOT_DIR}/.alfred-touch-launcher.log"

pick_browser() {
  if command -v chromium-browser >/dev/null 2>&1; then
    command -v chromium-browser
    return 0
  fi
  if command -v chromium >/dev/null 2>&1; then
    command -v chromium
    return 0
  fi
  return 1
}

wait_for_backend() {
  local attempts="${1:-20}"
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

BROWSER_CMD="$(pick_browser || true)"
if [[ -z "$BROWSER_CMD" ]]; then
  echo "Chromium is not installed. Install chromium-browser or chromium first." >&2
  exit 1
fi

if ! curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
  echo "Alfred touch backend is not running yet. Starting it now..."
  nohup "$ROOT_DIR/start_alfred_touch.sh" >"$LOG_FILE" 2>&1 &
  if ! wait_for_backend 30; then
    echo "Alfred touch backend did not become healthy. Check $LOG_FILE" >&2
    exit 1
  fi
fi

exec "$BROWSER_CMD" \
  --app="$APP_URL" \
  --start-maximized \
  --no-first-run \
  --disable-infobars \
  --overscroll-history-navigation=0 \
  --disable-pinch

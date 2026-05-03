#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

source "$ROOT_DIR/scripts/alfred_touch_env.sh"

echo "Starting Alfred Touch..."

PYTHON_CMD="$(alfred_touch_python_cmd)"

if [[ "${ALFRED_SKIP_BOOTSTRAP:-0}" != "1" ]]; then
  bash "$ROOT_DIR/scripts/bootstrap_alfred_touch.sh"
fi

if ! "$PYTHON_CMD" -c "import fastapi, uvicorn, jinja2, requests, multipart" >/dev/null 2>&1; then
  echo "Missing Alfred touch Python dependencies for $PYTHON_CMD." >&2
  echo "Run ./setup_alfred_touch.sh first." >&2
  exit 1
fi

exec "$PYTHON_CMD" -m uvicorn alfred_touch:app \
  --host "${ALFRED_TOUCH_HOST:-0.0.0.0}" \
  --port "${ALFRED_TOUCH_PORT:-8081}"

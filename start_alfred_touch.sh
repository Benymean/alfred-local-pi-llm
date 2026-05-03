#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "Starting Alfred Touch..."

if [ -x "$ROOT_DIR/venv/bin/python" ]; then
  PYTHON_CMD="$ROOT_DIR/venv/bin/python"
else
  PYTHON_CMD="python3"
fi

# Touch Alfred favors richer spoken replies while staying reasonably responsive.
export ALFRED_LLM_NUM_PREDICT="${ALFRED_LLM_NUM_PREDICT:-112}"
export ALFRED_VOICE_LLM_NUM_PREDICT="${ALFRED_VOICE_LLM_NUM_PREDICT:-80}"
export ALFRED_VOICE_DETAIL_LLM_NUM_PREDICT="${ALFRED_VOICE_DETAIL_LLM_NUM_PREDICT:-128}"
export ALFRED_LLM_NUM_CTX="${ALFRED_LLM_NUM_CTX:-2048}"
export ALFRED_LLM_TEMPERATURE="${ALFRED_LLM_TEMPERATURE:-0.35}"
export ALFRED_VOICE_REPLY_MAX_WORDS="${ALFRED_VOICE_REPLY_MAX_WORDS:-60}"
export ALFRED_VOICE_REPLY_MAX_SENTENCES="${ALFRED_VOICE_REPLY_MAX_SENTENCES:-4}"
export ALFRED_VOICE_DETAIL_MAX_WORDS="${ALFRED_VOICE_DETAIL_MAX_WORDS:-100}"
export ALFRED_VOICE_DETAIL_MAX_SENTENCES="${ALFRED_VOICE_DETAIL_MAX_SENTENCES:-5}"
# These defaults match the working USB mic and speaker devices found during Pi validation.
export ALFRED_ARECORD_DEVICE="${ALFRED_ARECORD_DEVICE:-plughw:3,0}"
export ALFRED_APLAY_DEVICE="${ALFRED_APLAY_DEVICE:-plughw:2,0}"
export ALFRED_WHISPER_MODE="${ALFRED_WHISPER_MODE:-fast}"
export ALFRED_TTS_TEMPO="${ALFRED_TTS_TEMPO:-0.94}"

if ! "$PYTHON_CMD" -c "import fastapi, uvicorn, jinja2, requests, multipart" >/dev/null 2>&1; then
  echo "Missing Alfred touch Python dependencies for $PYTHON_CMD." >&2
  echo "Run ./setup_alfred_touch.sh first." >&2
  exit 1
fi

exec "$PYTHON_CMD" -m uvicorn alfred_touch:app \
  --host "${ALFRED_TOUCH_HOST:-0.0.0.0}" \
  --port "${ALFRED_TOUCH_PORT:-8081}"

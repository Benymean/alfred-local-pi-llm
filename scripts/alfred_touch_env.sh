#!/usr/bin/env bash

if [[ -z "${ROOT_DIR:-}" ]]; then
  ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

export ALFRED_LLM_URL="${ALFRED_LLM_URL:-http://127.0.0.1:8000/api/chat}"
export ALFRED_LLM_MODEL="${ALFRED_LLM_MODEL:-qwen3:1.7b}"

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

alfred_touch_python_cmd() {
  if [[ -x "$ROOT_DIR/venv/bin/python" ]]; then
    printf "%s\n" "$ROOT_DIR/venv/bin/python"
  else
    printf "%s\n" "python3"
  fi
}

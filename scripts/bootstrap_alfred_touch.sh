#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

source "$ROOT_DIR/scripts/alfred_touch_env.sh"

PYTHON_CMD="$(alfred_touch_python_cmd)"
MODEL_SERVER_LOG="${ALFRED_MODEL_SERVER_LOG:-$ROOT_DIR/.alfred-model-server.log}"
SETUP_AUDIO_SCRIPT="$ROOT_DIR/scripts/setup_alfred_audio.sh"
WHISPER_BIN="${ALFRED_WHISPER_CMD:-$ROOT_DIR/whisper.cpp/build/bin/whisper-cli}"
PIPER_BIN="${ALFRED_PIPER_CMD:-$ROOT_DIR/piper/piper}"
PIPER_MODEL="${ALFRED_PIPER_MODEL:-$ROOT_DIR/piper/bmo.onnx}"
WHISPER_MODEL="${ALFRED_WHISPER_MODEL:-$ROOT_DIR/models/ggml-base.en.bin}"
WHISPER_FAST_MODEL="${ALFRED_WHISPER_FAST_MODEL:-$ROOT_DIR/models/ggml-tiny.en.bin}"
AUTO_PULL_MODEL="${ALFRED_AUTO_PULL_MODEL:-0}"

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

log() {
  printf "[%s] [alfred-bootstrap] %s\n" "$(timestamp)" "$*"
}

fail() {
  log "ERROR: $*" >&2
  exit 1
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Required command '$1' is not installed."
  fi
}

ensure_python_deps() {
  if ! "$PYTHON_CMD" -c "import fastapi, uvicorn, jinja2, requests, multipart" >/dev/null 2>&1; then
    fail "Missing Alfred Touch Python dependencies for $PYTHON_CMD. Run ./setup_alfred_touch.sh first."
  fi
}

audio_runtime_needs_repair() {
  if [[ ! -x "$PIPER_BIN" || ! -f "$PIPER_MODEL" ]]; then
    return 0
  fi
  if [[ ! -x "$WHISPER_BIN" || ! -f "$WHISPER_MODEL" ]]; then
    return 0
  fi
  if [[ "$ALFRED_WHISPER_MODE" == "fast" && ! -f "$WHISPER_FAST_MODEL" ]]; then
    return 0
  fi
  if ! "$WHISPER_BIN" -h >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

ensure_audio_runtime() {
  if audio_runtime_needs_repair; then
    log "Repairing local speech/runtime assets."
    rm -rf "$ROOT_DIR/whisper.cpp/build"
    chmod +x "$SETUP_AUDIO_SCRIPT"
    "$SETUP_AUDIO_SCRIPT"
    if ! "$WHISPER_BIN" -h >/dev/null 2>&1; then
      fail "Whisper is still not runnable after repair."
    fi
  fi
}

llm_tags_url() {
  "$PYTHON_CMD" - <<'PY'
from urllib.parse import urlsplit, urlunsplit
import os

url = os.environ.get("ALFRED_LLM_URL", "http://127.0.0.1:8000/api/chat")
parts = urlsplit(url)
path = parts.path or ""
if path.endswith("/api/chat"):
    path = path[:-len("/api/chat")]
elif "/api/" in path:
    path = path.split("/api/", 1)[0]
tags = urlunsplit((parts.scheme, parts.netloc, f"{path.rstrip('/')}/api/tags", "", ""))
print(tags)
PY
}

llm_is_local() {
  [[ "$ALFRED_LLM_URL" == http://127.0.0.1:* || "$ALFRED_LLM_URL" == http://localhost:* ]]
}

pick_model_server_cmd() {
  if [[ -n "${ALFRED_MODEL_SERVER_CMD:-}" ]]; then
    printf "%s\n" "$ALFRED_MODEL_SERVER_CMD"
    return 0
  fi
  if command -v hailo-ollama >/dev/null 2>&1; then
    command -v hailo-ollama
    return 0
  fi
  if command -v ollama >/dev/null 2>&1; then
    command -v ollama
    return 0
  fi
  return 1
}

wait_for_http() {
  local url="$1"
  local attempts="${2:-40}"
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

ensure_model_present() {
  local tags_url="$1"
  local model_server_cmd="${2:-}"
  local tags_json

  tags_json="$(curl -fsS "$tags_url" 2>/dev/null || true)"
  if [[ "$tags_json" == *"$ALFRED_LLM_MODEL"* ]]; then
    return 0
  fi

  if [[ "$AUTO_PULL_MODEL" == "1" ]]; then
    if [[ -z "$model_server_cmd" ]]; then
      fail "Model ${ALFRED_LLM_MODEL} is missing and ALFRED_AUTO_PULL_MODEL=1 was requested, but no local model server command is available."
    fi
    log "Model ${ALFRED_LLM_MODEL} is missing. Pulling it automatically."
    "$model_server_cmd" pull "$ALFRED_LLM_MODEL" >>"$MODEL_SERVER_LOG" 2>&1
    tags_json="$(curl -fsS "$tags_url" 2>/dev/null || true)"
    if [[ "$tags_json" == *"$ALFRED_LLM_MODEL"* ]]; then
      return 0
    fi
  fi

  fail "Model ${ALFRED_LLM_MODEL} is not available from the local model server."
}

ensure_model_server() {
  local tags_url
  local model_server_cmd

  if ! llm_is_local; then
    log "Skipping local model server bootstrap because ALFRED_LLM_URL is not a localhost endpoint."
    return 0
  fi

  tags_url="$(llm_tags_url)"
  if curl -fsS "$tags_url" >/dev/null 2>&1; then
    model_server_cmd="$(pick_model_server_cmd || true)"
    ensure_model_present "$tags_url" "$model_server_cmd"
    return 0
  fi

  model_server_cmd="$(pick_model_server_cmd || true)"
  if [[ -z "$model_server_cmd" ]]; then
    fail "No local model server command was found. Install hailo-ollama or ollama, or set ALFRED_MODEL_SERVER_CMD."
  fi

  log "Starting local model server with: $model_server_cmd serve"
  nohup "$model_server_cmd" serve >>"$MODEL_SERVER_LOG" 2>&1 &

  if ! wait_for_http "$tags_url" 60; then
    fail "Local model server did not become ready at $tags_url. Check $MODEL_SERVER_LOG"
  fi

  ensure_model_present "$tags_url" "$model_server_cmd"
}

main() {
  need_cmd curl
  ensure_python_deps
  ensure_audio_runtime
  ensure_model_server
  log "Bootstrap complete."
}

main "$@"

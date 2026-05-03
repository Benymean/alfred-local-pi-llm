#!/usr/bin/env bash
set -u
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

RUN_LIVE_AUTO=1
RUN_LIVE_FORCE=0
RUN_STT_TEST=1
RUN_TTS_TEST=1
MOCK_PORT="${ALFRED_TOUCH_MOCK_PORT:-18081}"
LIVE_PORT="${ALFRED_TOUCH_LIVE_PORT:-18082}"

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

SERVER_PID=""
SERVER_LOG=""
MOCK_MEMORY=""
LIVE_MEMORY=""

if [[ -t 1 ]]; then
  C_RESET="$(printf '\033[0m')"
  C_PASS="$(printf '\033[32m')"
  C_WARN="$(printf '\033[33m')"
  C_FAIL="$(printf '\033[31m')"
  C_INFO="$(printf '\033[36m')"
  C_HEAD="$(printf '\033[1m')"
else
  C_RESET=""
  C_PASS=""
  C_WARN=""
  C_FAIL=""
  C_INFO=""
  C_HEAD=""
fi

usage() {
  cat <<'EOF'
Usage:
  ./healthcheck_alfred_software.sh [options]

Options:
  --mock-only       Skip the live-model smoke test even if the model server is online.
  --live            Force the live-model smoke test; fail if the model server is offline.
  --skip-stt        Skip the STT upload probe.
  --skip-tts        Skip the TTS file-generation probe.
  --mock-port N     Port to use for the mock backend (default: 18081).
  --live-port N     Port to use for the live backend (default: 18082).
  -h, --help        Show this help.

What it tests:
  - Python environment and Alfred touch dependency imports
  - Runtime command dependencies like ffmpeg and curl
  - Required touch UI files
  - Piper / Whisper assets
  - Browser and local model runtime availability
  - Starts Alfred touch in mock mode and hits real HTTP routes
  - Mock chat round trip
  - TTS file generation route (optional)
  - STT upload route using a bundled sample WAV (optional)
  - Live backend chat smoke test if the local model server is reachable
EOF
}

section() {
  printf "\n%s== %s ==%s\n" "$C_HEAD" "$1" "$C_RESET"
}

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf "%s[PASS]%s %s\n" "$C_PASS" "$C_RESET" "$1"
}

warn() {
  WARN_COUNT=$((WARN_COUNT + 1))
  printf "%s[WARN]%s %s\n" "$C_WARN" "$C_RESET" "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf "%s[FAIL]%s %s\n" "$C_FAIL" "$C_RESET" "$1"
}

info() {
  printf "%s[INFO]%s %s\n" "$C_INFO" "$C_RESET" "$1"
}

cleanup() {
  if declare -F stop_server >/dev/null 2>&1; then
    stop_server
  fi
  if [[ -n "$MOCK_MEMORY" && -f "$MOCK_MEMORY" ]]; then
    rm -f "$MOCK_MEMORY"
  fi
  if [[ -n "$LIVE_MEMORY" && -f "$LIVE_MEMORY" ]]; then
    rm -f "$LIVE_MEMORY"
  fi
}

trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mock-only)
      RUN_LIVE_AUTO=0
      ;;
    --live)
      RUN_LIVE_FORCE=1
      ;;
    --skip-stt)
      RUN_STT_TEST=0
      ;;
    --skip-tts)
      RUN_TTS_TEST=0
      ;;
    --mock-port)
      shift
      if [[ $# -eq 0 || ! "$1" =~ ^[0-9]+$ ]]; then
        echo "Expected a port number after --mock-port" >&2
        exit 2
      fi
      MOCK_PORT="$1"
      ;;
    --live-port)
      shift
      if [[ $# -eq 0 || ! "$1" =~ ^[0-9]+$ ]]; then
        echo "Expected a port number after --live-port" >&2
        exit 2
      fi
      LIVE_PORT="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ -x "$ROOT_DIR/venv/bin/python" ]]; then
  PYTHON_CMD="$ROOT_DIR/venv/bin/python"
else
  PYTHON_CMD="python3"
fi

json_extract_stdin() {
  local key="$1"
  "$PYTHON_CMD" -c '
import json
import sys

key = sys.argv[1]
payload = json.load(sys.stdin)
value = payload.get(key, "")
if isinstance(value, bool):
    print("true" if value else "false")
elif value is None:
    print("")
else:
    print(value)
' "$key"
}

check_file() {
  local path="$1"
  local label="$2"
  if [[ -e "$path" ]]; then
    pass "$label found at $path"
  else
    fail "$label is missing at $path"
  fi
}

check_executable() {
  local path="$1"
  local label="$2"
  if [[ -x "$path" ]]; then
    pass "$label is executable at $path"
  elif [[ -e "$path" ]]; then
    fail "$label exists at $path but is not executable."
  else
    fail "$label is missing at $path"
  fi
}

check_command() {
  local name="$1"
  local label="$2"
  if command -v "$name" >/dev/null 2>&1; then
    pass "$label is installed at $(command -v "$name")"
  else
    fail "$label is not installed or not in PATH."
  fi
}

check_optional_command() {
  local name="$1"
  local label="$2"
  if command -v "$name" >/dev/null 2>&1; then
    pass "$label is installed at $(command -v "$name")"
  else
    warn "$label is not installed or not in PATH."
  fi
}

check_python_import() {
  local import_name="$1"
  local package_label="$2"
  if "$PYTHON_CMD" -c "import ${import_name}" >/dev/null 2>&1; then
    pass "Python package '${package_label}' imports successfully."
  else
    fail "Python package '${package_label}' is missing for $PYTHON_CMD."
  fi
}

stop_server() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
    SERVER_PID=""
  fi
}

start_server() {
  local backend="$1"
  local port="$2"
  local memory_path="$3"

  stop_server
  SERVER_LOG="$(mktemp "/tmp/alfred-touch-${backend}.XXXX.log")"
  info "Starting Alfred touch backend=${backend} on port ${port}"

  ALFRED_TOUCH_BACKEND="$backend" \
  ALFRED_TOUCH_HOST="127.0.0.1" \
  ALFRED_TOUCH_PORT="$port" \
  ALFRED_MEMORY_PATH="$memory_path" \
  "$PYTHON_CMD" -m uvicorn alfred_touch:app --host 127.0.0.1 --port "$port" >"$SERVER_LOG" 2>&1 &
  SERVER_PID=$!

  for _ in $(seq 1 40); do
    if curl -fsS "http://127.0.0.1:${port}/api/health" >/dev/null 2>&1; then
      pass "Backend ${backend} started successfully on port ${port}"
      return 0
    fi
    sleep 0.5
  done

  fail "Backend ${backend} did not start cleanly on port ${port}"
  if [[ -f "$SERVER_LOG" ]]; then
    printf "    Recent log output:\n"
    tail -n 40 "$SERVER_LOG" | sed 's/^/    /'
  fi
  return 1
}

http_expect_contains() {
  local url="$1"
  local needle="$2"
  local label="$3"
  local response
  response="$(curl -fsS "$url" 2>/dev/null || true)"
  if [[ "$response" == *"$needle"* ]]; then
    pass "$label"
  else
    fail "$label"
  fi
}

http_expect_any_contains() {
  local url="$1"
  local label="$2"
  shift 2

  local response
  response="$(curl -fsS "$url" 2>/dev/null || true)"
  if [[ -z "$response" ]]; then
    fail "$label"
    printf "    No response body was returned from %s\n" "$url"
    return 1
  fi

  local needle
  for needle in "$@"; do
    if [[ "$response" == *"$needle"* ]]; then
      pass "$label"
      return 0
    fi
  done

  fail "$label"
  printf "    Looked for any of these markers:\n"
  for needle in "$@"; do
    printf "      - %s\n" "$needle"
  done
  printf "    First response bytes:\n"
  printf "%s" "$response" | head -c 240 | sed 's/^/    /'
  printf "\n"
  return 1
}

http_post_json() {
  local url="$1"
  local payload="$2"
  curl -fsS "$url" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

section "Runtime Dependencies"

if command -v "$PYTHON_CMD" >/dev/null 2>&1; then
  pass "Using Python interpreter: $PYTHON_CMD"
else
  fail "Python interpreter $PYTHON_CMD is not available."
fi

if [[ -x "$ROOT_DIR/venv/bin/python" ]]; then
  pass "Virtual environment Python is present at $ROOT_DIR/venv/bin/python"
else
  warn "Virtual environment is missing. Alfred touch can still use system Python, but the recommended setup is ./setup_alfred_touch.sh"
fi

check_file "$ROOT_DIR/requirements.txt" "Alfred touch requirements file"

check_python_import fastapi fastapi
check_python_import uvicorn uvicorn
check_python_import jinja2 jinja2
check_python_import requests requests
check_python_import multipart python-multipart

section "Command Dependencies"

check_command curl "curl"
check_command ffmpeg "ffmpeg"
check_optional_command hailo-ollama "hailo-ollama"
if command -v chromium-browser >/dev/null 2>&1; then
  pass "Chromium browser is installed at $(command -v chromium-browser)"
elif command -v chromium >/dev/null 2>&1; then
  pass "Chromium browser is installed at $(command -v chromium)"
else
  warn "Chromium browser is not installed or not in PATH."
fi

section "Project Files"

check_file "$ROOT_DIR/alfred_touch.py" "Alfred touch backend"
check_file "$ROOT_DIR/start_alfred_touch.sh" "Alfred touch launcher"
check_file "$ROOT_DIR/alfred_touch_app/templates/alfred_touch.html" "Touch HTML template"
check_file "$ROOT_DIR/alfred_touch_app/static/alfred_touch.css" "Touch CSS"
check_file "$ROOT_DIR/alfred_touch_app/static/alfred_touch.js" "Touch JS"
check_file "$ROOT_DIR/alfred_touch_app/assets/favicon.png" "Favicon"

section "Speech Assets"

PIPER_BIN="${ALFRED_PIPER_CMD:-$ROOT_DIR/piper/piper}"
PIPER_MODEL="${ALFRED_PIPER_MODEL:-$ROOT_DIR/piper/bmo.onnx}"
WHISPER_BIN="${ALFRED_WHISPER_CMD:-$ROOT_DIR/whisper.cpp/build/bin/whisper-cli}"
WHISPER_MODE="${ALFRED_WHISPER_MODE:-auto}"
WHISPER_MODEL="${ALFRED_WHISPER_MODEL:-$ROOT_DIR/models/ggml-base.en.bin}"
WHISPER_FAST_MODEL="${ALFRED_WHISPER_FAST_MODEL:-$ROOT_DIR/models/ggml-tiny.en.bin}"

check_executable "$PIPER_BIN" "Piper binary"
check_file "$PIPER_MODEL" "Piper model"
check_executable "$WHISPER_BIN" "Whisper binary"

if [[ -f "$WHISPER_MODEL" ]]; then
  pass "Whisper accurate model found at $WHISPER_MODEL"
else
  fail "Whisper accurate model is missing at $WHISPER_MODEL"
fi

if [[ -f "$WHISPER_FAST_MODEL" ]]; then
  pass "Whisper fast model found at $WHISPER_FAST_MODEL"
else
  warn "Whisper fast model is missing at $WHISPER_FAST_MODEL. Run ./scripts/setup_alfred_audio.sh on the Pi to install it."
fi

ACTIVE_WHISPER_MODEL="$WHISPER_MODEL"
ACTIVE_WHISPER_MODE="accurate-auto"
if [[ "$WHISPER_MODE" == "fast" ]]; then
  if [[ -f "$WHISPER_FAST_MODEL" ]]; then
    ACTIVE_WHISPER_MODEL="$WHISPER_FAST_MODEL"
    ACTIVE_WHISPER_MODE="fast"
  else
    ACTIVE_WHISPER_MODE="accurate-fallback"
  fi
elif [[ "$WHISPER_MODE" == "accurate" ]]; then
  ACTIVE_WHISPER_MODE="accurate"
elif [[ -f "$WHISPER_FAST_MODEL" ]]; then
  ACTIVE_WHISPER_MODEL="$WHISPER_FAST_MODEL"
  ACTIVE_WHISPER_MODE="fast-auto"
fi

if [[ -f "$ACTIVE_WHISPER_MODEL" ]]; then
  pass "Active Whisper mode resolves to ${ACTIVE_WHISPER_MODE} using $ACTIVE_WHISPER_MODEL"
else
  fail "Active Whisper mode ${ACTIVE_WHISPER_MODE} could not find a model at $ACTIVE_WHISPER_MODEL"
fi

section "Model Server"

MODEL_TAGS="$(curl -fsS http://127.0.0.1:8000/api/tags 2>/dev/null || true)"
if [[ -n "$MODEL_TAGS" ]]; then
  pass "Local model server responded on http://127.0.0.1:8000/api/tags"
  if [[ "$MODEL_TAGS" == *"qwen3:1.7b"* ]]; then
    pass "qwen3:1.7b appears in the local model list."
  else
    warn "Local model server is up, but qwen3:1.7b was not found in /api/tags output."
  fi
else
  if [[ "$RUN_LIVE_FORCE" -eq 1 ]]; then
    fail "Live backend was requested, but the model server is offline."
  else
    warn "Local model server did not respond on http://127.0.0.1:8000/api/tags"
  fi
fi

section "Mock Backend"

MOCK_MEMORY="$(mktemp /tmp/alfred-touch-mock-memory.XXXX.json)"
if start_server "mock" "$MOCK_PORT" "$MOCK_MEMORY"; then
  http_expect_any_contains "http://127.0.0.1:${MOCK_PORT}/" "Root page renders Alfred touch UI" \
    "Touchscreen Alfred is ready" \
    "Chat with Alfred" \
    "id=\"mic-button\"" \
    "data-assistant-name="
  http_expect_contains "http://127.0.0.1:${MOCK_PORT}/static/alfred_touch.css" ":root" "Touch CSS is being served"
  http_expect_contains "http://127.0.0.1:${MOCK_PORT}/api/bootstrap" "\"assistant_name\"" "Bootstrap endpoint responds with JSON"

  HEALTH_JSON="$(curl -fsS "http://127.0.0.1:${MOCK_PORT}/api/health" 2>/dev/null || true)"
  if [[ "$HEALTH_JSON" == *"\"assistant_name\""* && "$HEALTH_JSON" == *"\"llm_status\""* ]]; then
    pass "Health endpoint responds with Alfred touch status JSON."
  else
    fail "Health endpoint did not return the expected JSON shape."
  fi

  MOCK_CHAT_JSON="$(http_post_json "http://127.0.0.1:${MOCK_PORT}/api/chat" '{"message":"Hello Alfred from the software health check.","synthesize_audio":false}' 2>/dev/null || true)"
  MOCK_RESPONSE="$(printf "%s" "$MOCK_CHAT_JSON" | json_extract_stdin response 2>/dev/null || true)"
  if [[ -n "$MOCK_RESPONSE" ]]; then
    pass "Mock chat endpoint returned a non-empty response."
  else
    fail "Mock chat endpoint did not return a usable response."
  fi

  if [[ "$RUN_TTS_TEST" -eq 1 ]]; then
    MOCK_TTS_JSON="$(http_post_json "http://127.0.0.1:${MOCK_PORT}/api/chat" '{"message":"Please say hello.","synthesize_audio":true}' 2>/dev/null || true)"
    AUDIO_URL="$(printf "%s" "$MOCK_TTS_JSON" | json_extract_stdin audio_url 2>/dev/null || true)"
    if [[ -n "$AUDIO_URL" ]]; then
      pass "Mock chat generated a browser-playable TTS file."
      if curl -fsS "http://127.0.0.1:${MOCK_PORT}${AUDIO_URL}" >/dev/null 2>&1; then
        pass "Generated TTS file can be fetched over HTTP."
      else
        fail "Generated TTS file URL was returned but could not be fetched."
      fi
    else
      warn "TTS file was not generated during the mock chat probe."
    fi
  else
    info "Skipping TTS file generation probe."
  fi

  if [[ "$RUN_STT_TEST" -eq 1 ]]; then
    SAMPLE_AUDIO="/usr/share/sounds/alsa/Front_Center.wav"
    if [[ -f "$SAMPLE_AUDIO" ]]; then
      STT_JSON="$(curl -fsS -F "audio=@${SAMPLE_AUDIO}" "http://127.0.0.1:${MOCK_PORT}/api/transcribe" 2>/dev/null || true)"
      STT_TEXT="$(printf "%s" "$STT_JSON" | json_extract_stdin text 2>/dev/null || true)"
      if [[ -n "$STT_TEXT" ]]; then
        pass "STT upload endpoint returned a non-empty transcript from the sample WAV."
      else
        warn "STT upload endpoint responded, but the transcript was empty."
      fi
    else
      warn "Sample WAV for STT probe is missing at $SAMPLE_AUDIO."
    fi
  else
    info "Skipping STT upload probe."
  fi
fi

if [[ "$RUN_LIVE_FORCE" -eq 1 || ( "$RUN_LIVE_AUTO" -eq 1 && -n "$MODEL_TAGS" ) ]]; then
  section "Live Backend"
  LIVE_MEMORY="$(mktemp /tmp/alfred-touch-live-memory.XXXX.json)"
  if start_server "live" "$LIVE_PORT" "$LIVE_MEMORY"; then
    LIVE_CHAT_JSON="$(http_post_json "http://127.0.0.1:${LIVE_PORT}/api/chat" '{"message":"Say one short sentence to confirm the live model is working.","synthesize_audio":false}' 2>/dev/null || true)"
    LIVE_RESPONSE="$(printf "%s" "$LIVE_CHAT_JSON" | json_extract_stdin response 2>/dev/null || true)"
    if [[ -n "$LIVE_RESPONSE" ]]; then
      pass "Live backend returned a non-empty chat response."
    else
      fail "Live backend did not return a usable chat response."
    fi
  fi
else
  info "Skipping live backend smoke test."
fi

section "Summary"

printf "%sPass:%s %s\n" "$C_PASS" "$C_RESET" "$PASS_COUNT"
printf "%sWarn:%s %s\n" "$C_WARN" "$C_RESET" "$WARN_COUNT"
printf "%sFail:%s %s\n" "$C_FAIL" "$C_RESET" "$FAIL_COUNT"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi

exit 0

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PIPER_RELEASE_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz"
WHISPER_REPO_URL="https://github.com/ggerganov/whisper.cpp.git"
WHISPER_MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"
WHISPER_FAST_MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin"
ALFRED_VOICE_URL="https://github.com/brenpoly/be-more-agent/releases/download/v1.0-voice"

echo "Setting up Alfred audio dependencies in: $ROOT_DIR"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

need_cmd uname
need_cmd mkdir
need_cmd tar
need_cmd wget
need_cmd git
need_cmd cmake

ARCH="$(uname -m)"
if [[ "$ARCH" != "aarch64" ]]; then
  echo "This script currently targets Raspberry Pi 64-bit / aarch64. Detected: $ARCH" >&2
  exit 1
fi

mkdir -p piper models

echo
echo "[1/4] Installing Piper runtime..."
if [[ ! -f "piper/piper" ]]; then
  tmp_tar="$(mktemp /tmp/alfred-piper.XXXXXX.tar.gz)"
  wget -O "$tmp_tar" "$PIPER_RELEASE_URL"
  tar -xf "$tmp_tar" -C piper --strip-components=1
  rm -f "$tmp_tar"
else
  echo "Piper runtime already present."
fi

echo
echo "[2/4] Ensuring Alfred voice model exists..."
if [[ ! -f "piper/bmo.onnx" ]]; then
  wget -O piper/bmo.onnx "$ALFRED_VOICE_URL/bmo.onnx"
fi
if [[ ! -f "piper/bmo.onnx.json" ]]; then
  wget -O piper/bmo.onnx.json "$ALFRED_VOICE_URL/bmo.onnx.json"
fi

echo
echo "[3/4] Building whisper.cpp..."
if [[ ! -d "whisper.cpp" ]]; then
  git clone --depth 1 "$WHISPER_REPO_URL" whisper.cpp
fi
cmake -B whisper.cpp/build -S whisper.cpp -DCMAKE_BUILD_TYPE=Release
cmake --build whisper.cpp/build --config Release -j"$(nproc)"

echo
echo "[4/4] Ensuring Whisper models exist..."
if [[ ! -f "models/ggml-base.en.bin" ]]; then
  wget -O models/ggml-base.en.bin "$WHISPER_MODEL_URL"
else
  echo "Whisper base.en model already present."
fi

if [[ ! -f "models/ggml-tiny.en.bin" ]]; then
  wget -O models/ggml-tiny.en.bin "$WHISPER_FAST_MODEL_URL"
else
  echo "Whisper tiny.en model already present."
fi

echo
echo "Alfred audio dependencies are ready."
echo "Recommended Pi devices for your current stack:"
echo "  Mic:    ALFRED_ARECORD_DEVICE=plughw:3,0"
echo "  Speaker: ALFRED_APLAY_DEVICE=plughw:2,0"
echo
echo "Touch performance note:"
echo "  Alfred Touch prefers ALFRED_WHISPER_MODE=fast when models/ggml-tiny.en.bin exists."

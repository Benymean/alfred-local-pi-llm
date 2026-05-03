#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

REQ_FILE="$ROOT_DIR/requirements.txt"
VENV_DIR="$ROOT_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python"

echo "Setting up Alfred Touch..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is not installed." >&2
  exit 1
fi

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required for installing system packages." >&2
  exit 1
fi

echo
echo "[1/5] Installing system packages..."
sudo apt-get update
sudo apt-get install -y python3-venv ffmpeg git wget cmake build-essential curl

echo
echo "[2/5] Creating virtual environment..."
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
else
  echo "Virtual environment already exists at $VENV_DIR"
fi

echo
echo "[3/5] Installing Alfred touch Python dependencies..."
"$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel
"$VENV_PYTHON" -m pip install -r "$REQ_FILE"

echo
echo "[4/5] Installing local speech/runtime assets..."
chmod +x "$ROOT_DIR/scripts/alfred_touch_env.sh"
chmod +x "$ROOT_DIR/scripts/bootstrap_alfred_touch.sh"
chmod +x "$ROOT_DIR/scripts/setup_alfred_audio.sh"
"$ROOT_DIR/scripts/setup_alfred_audio.sh"

echo
echo "[5/5] Finalizing scripts..."
chmod +x \
  "$ROOT_DIR/start_alfred_touch.sh" \
  "$ROOT_DIR/launch_alfred_touch.sh" \
  "$ROOT_DIR/install_alfred_touch_launcher.sh" \
  "$ROOT_DIR/healthcheck_alfred_touch.sh" \
  "$ROOT_DIR/healthcheck_alfred_software.sh" \
  "$ROOT_DIR/scripts/bootstrap_alfred_touch.sh" \
  "$ROOT_DIR/scripts/alfred_touch_env.sh"

echo "Installing Alfred Touch desktop launcher..."
"$ROOT_DIR/install_alfred_touch_launcher.sh"

echo
echo "Alfred touch setup is complete."
echo "Next steps:"
  echo "  1. ./healthcheck_alfred_touch.sh --audio-test"
  echo "  2. ./healthcheck_alfred_software.sh --mock-only"
  echo "  3. ./healthcheck_alfred_software.sh --live"
  echo "  4. Tap the 'Alfred Touch' desktop icon"

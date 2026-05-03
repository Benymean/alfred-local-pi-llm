#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="${HOME}/Desktop"
APPLICATIONS_DIR="${HOME}/.local/share/applications"
AUTOSTART_DIR="${HOME}/.config/autostart"
DESKTOP_FILE_NAME="Alfred Touch.desktop"
DESKTOP_FILE_PATH="${DESKTOP_DIR}/${DESKTOP_FILE_NAME}"
APPLICATION_FILE_PATH="${APPLICATIONS_DIR}/alfred-touch.desktop"
AUTOSTART_FILE_PATH="${AUTOSTART_DIR}/alfred-touch.desktop"
ENABLE_AUTOSTART=0

usage() {
  cat <<'EOF'
Usage:
  ./install_alfred_touch_launcher.sh [--autostart]

What it does:
  - creates a visible Alfred Touch launcher on the Pi desktop
  - adds Alfred Touch to the application menu
  - optionally adds Alfred Touch to desktop autostart
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --autostart)
      ENABLE_AUTOSTART=1
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

mkdir -p "$DESKTOP_DIR" "$APPLICATIONS_DIR"
if [[ "$ENABLE_AUTOSTART" -eq 1 ]]; then
  mkdir -p "$AUTOSTART_DIR"
fi

write_desktop_file() {
  local target="$1"
  cat >"$target" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Alfred Touch
Comment=Launch Alfred touchscreen AI companion
Exec=${ROOT_DIR}/launch_alfred_touch.sh
Icon=${ROOT_DIR}/alfred_touch_app/assets/favicon.png
Path=${ROOT_DIR}
Terminal=false
Categories=Utility;
StartupNotify=true
EOF
  chmod +x "$target"
  if command -v gio >/dev/null 2>&1; then
    gio set "$target" metadata::trusted true >/dev/null 2>&1 || true
  fi
}

write_desktop_file "$DESKTOP_FILE_PATH"
write_desktop_file "$APPLICATION_FILE_PATH"

if [[ "$ENABLE_AUTOSTART" -eq 1 ]]; then
  write_desktop_file "$AUTOSTART_FILE_PATH"
fi

echo "Installed Alfred Touch launcher:"
echo "  Desktop: $DESKTOP_FILE_PATH"
echo "  App menu: $APPLICATION_FILE_PATH"
if [[ "$ENABLE_AUTOSTART" -eq 1 ]]; then
  echo "  Autostart: $AUTOSTART_FILE_PATH"
fi
echo
echo "If the desktop does not refresh immediately, log out and back in or restart the Pi desktop session."

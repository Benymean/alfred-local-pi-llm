#!/usr/bin/env bash
set -u
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PLAYBACK_TEST=0
RECORD_TEST=0
RECORD_SECONDS=3
TEMP_AUDIO_FILE=""

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

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
  ./healthcheck_alfred_touch.sh [options]

Options:
  --audio-test       Run both playback and microphone capture probes.
  --playback-test    Play a short ALSA test sample through the configured speaker.
  --record-test      Record a short WAV file from the configured microphone.
  --record-seconds N Set record probe duration in seconds (default: 3).
  -h, --help         Show this help.

Notes:
  - Safe by default: no speaker sound and no recording unless you opt in.
  - Honors ALFRED_ARECORD_DEVICE and ALFRED_APLAY_DEVICE if set.
EOF
}

cleanup() {
  if [[ -n "$TEMP_AUDIO_FILE" && -f "$TEMP_AUDIO_FILE" ]]; then
    rm -f "$TEMP_AUDIO_FILE"
  fi
}

trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --audio-test)
      PLAYBACK_TEST=1
      RECORD_TEST=1
      ;;
    --playback-test)
      PLAYBACK_TEST=1
      ;;
    --record-test)
      RECORD_TEST=1
      ;;
    --record-seconds)
      shift
      if [[ $# -eq 0 || ! "$1" =~ ^[0-9]+$ || "$1" -lt 1 ]]; then
        echo "Expected a positive integer after --record-seconds" >&2
        exit 2
      fi
      RECORD_SECONDS="$1"
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

show_command_output() {
  local label="$1"
  shift
  local output
  output="$("$@" 2>&1 || true)"
  if [[ -n "$output" ]]; then
    printf "%s\n" "$output" | sed "s/^/    /"
  else
    info "$label returned no output."
  fi
}

check_command() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "Found command '$cmd' at $(command -v "$cmd")"
  else
    warn "Command '$cmd' is missing."
  fi
}

hailo_device_nodes() {
  local nodes=()
  shopt -s nullglob
  nodes=(/dev/h1x-* /dev/hailo*)
  shopt -u nullglob
  printf "%s\n" "${nodes[@]}"
}

section "System"

MODEL="Unknown"
if [[ -r /proc/device-tree/model ]]; then
  MODEL="$(tr -d '\0' < /proc/device-tree/model)"
fi
info "Model: $MODEL"
info "Kernel: $(uname -srmo)"

if [[ "$(uname -m)" == "aarch64" ]]; then
  pass "OS architecture is aarch64, which matches the expected Pi 5 64-bit setup."
else
  warn "Architecture is $(uname -m); the Alfred audio setup expects aarch64."
fi

if [[ "$MODEL" == *"Raspberry Pi 5"* ]]; then
  pass "Detected Raspberry Pi 5 hardware."
else
  warn "This does not look like a Raspberry Pi 5 from /proc/device-tree/model."
fi

if command -v vcgencmd >/dev/null 2>&1; then
  temp_line="$(vcgencmd measure_temp 2>/dev/null || true)"
  temp_c="$(printf "%s" "$temp_line" | sed -n "s/.*temp=\([0-9.]*\).*/\1/p")"
  if [[ -n "$temp_c" ]]; then
    info "CPU temperature: ${temp_c}C"
    if awk "BEGIN {exit !($temp_c >= 80.0)}"; then
      fail "Temperature is high (${temp_c}C)."
    elif awk "BEGIN {exit !($temp_c >= 70.0)}"; then
      warn "Temperature is elevated (${temp_c}C)."
    else
      pass "Temperature looks healthy (${temp_c}C)."
    fi
  else
    warn "Could not parse vcgencmd temperature output: $temp_line"
  fi

  throttle_line="$(vcgencmd get_throttled 2>/dev/null || true)"
  throttled_value="${throttle_line#*=}"
  if [[ -n "$throttled_value" && "$throttled_value" != "0x0" ]]; then
    warn "Pi reports throttling history or current limits: $throttle_line"
  elif [[ -n "$throttled_value" ]]; then
    pass "Pi reports no throttling flags."
  else
    warn "Could not read throttling status via vcgencmd."
  fi
else
  warn "vcgencmd is unavailable, so temperature and throttling checks are limited."
fi

FAN_SENSOR=""
shopt -s nullglob
for candidate in \
  /sys/class/hwmon/hwmon*/fan1_input \
  /sys/devices/platform/cooling_fan/hwmon/hwmon*/fan1_input
do
  if [[ -r "$candidate" ]]; then
    FAN_SENSOR="$candidate"
    break
  fi
done
shopt -u nullglob

if [[ -n "$FAN_SENSOR" ]]; then
  FAN_RPM="$(cat "$FAN_SENSOR" 2>/dev/null || true)"
  if [[ "$FAN_RPM" =~ ^[0-9]+$ && "$FAN_RPM" -gt 0 ]]; then
    pass "Fan tachometer is available and spinning at ${FAN_RPM} RPM."
  elif [[ "$FAN_RPM" =~ ^[0-9]+$ ]]; then
    warn "Fan tachometer is available but currently reads 0 RPM. That can be normal if the system is cool."
  else
    warn "Fan tachometer path exists but RPM could not be read from $FAN_SENSOR."
  fi
else
  warn "No readable fan RPM sensor was found. Fan health will need to be inferred from temperature under load."
fi

section "Display"

CONNECTED_DISPLAYS=0
shopt -s nullglob
for status_file in /sys/class/drm/card*-*/status; do
  connector_dir="$(dirname "$status_file")"
  connector_name="$(basename "$connector_dir")"
  status="$(cat "$status_file" 2>/dev/null || echo unknown)"
  modes_file="$connector_dir/modes"
  first_mode=""
  if [[ -r "$modes_file" ]]; then
    first_mode="$(head -n 1 "$modes_file" 2>/dev/null || true)"
  fi
  if [[ "$status" == "connected" ]]; then
    CONNECTED_DISPLAYS=$((CONNECTED_DISPLAYS + 1))
    pass "Display connector $connector_name is connected${first_mode:+ at $first_mode}."
  else
    info "Display connector $connector_name status: $status"
  fi
done
shopt -u nullglob

if [[ "$CONNECTED_DISPLAYS" -eq 0 ]]; then
  fail "No connected DRM display was detected."
fi

if command -v xrandr >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  info "xrandr output for the current desktop session:"
  show_command_output "xrandr" xrandr --query
else
  info "Skipping xrandr desktop query because xrandr or DISPLAY is unavailable."
fi

section "Touch Input"

TOUCH_FOUND=0
if command -v libinput >/dev/null 2>&1; then
  touch_blocks="$(libinput list-devices 2>/dev/null | awk 'BEGIN{RS="";IGNORECASE=1}/touch|goodix|ft5|ilitek|edt-ft5x06|raspberrypi-ts/{print}')"
  if [[ -n "$touch_blocks" ]]; then
    TOUCH_FOUND=1
    pass "Found at least one likely touch input device via libinput."
    printf "%s\n" "$touch_blocks" | sed "s/^/    /"
  fi
fi

if [[ "$TOUCH_FOUND" -eq 0 && -r /proc/bus/input/devices ]]; then
  touch_blocks="$(awk 'BEGIN{RS="";IGNORECASE=1}/touch|goodix|ft5|ilitek|edt-ft5x06|raspberrypi-ts/{print}' /proc/bus/input/devices)"
  if [[ -n "$touch_blocks" ]]; then
    TOUCH_FOUND=1
    pass "Found at least one likely touch input device via /proc/bus/input/devices."
    printf "%s\n" "$touch_blocks" | sed "s/^/    /"
  fi
fi

if [[ "$TOUCH_FOUND" -eq 0 ]]; then
  warn "No obvious touch controller was detected."
fi

section "Hailo AI HAT"

HAILO_NODES="$(hailo_device_nodes | sed '/^$/d')"
if [[ -n "$HAILO_NODES" ]]; then
  pass "Found Hailo device node(s): $(printf "%s" "$HAILO_NODES" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
else
  fail "No Hailo device node was found under /dev/h1x-* or /dev/hailo*."
fi

if command -v lsmod >/dev/null 2>&1; then
  hailo_modules="$(lsmod | grep -E 'hailo1x_pci|hailo_pci' || true)"
  if [[ "$hailo_modules" == *"hailo1x_pci"* ]]; then
    pass "hailo1x_pci kernel module is loaded."
  elif [[ -n "$hailo_modules" ]]; then
    warn "A Hailo-related module is loaded, but not the expected hailo1x_pci:\n$hailo_modules"
  else
    warn "No Hailo kernel modules are currently loaded."
  fi
fi

if command -v lspci >/dev/null 2>&1; then
  hailo_pci="$(lspci -nn | grep -i hailo || true)"
  if [[ -n "$hailo_pci" ]]; then
    pass "Hailo PCIe device is visible via lspci."
    printf "%s\n" "$hailo_pci" | sed "s/^/    /"
  else
    warn "No Hailo PCIe device showed up in lspci."
  fi
fi

if command -v hailo-ollama >/dev/null 2>&1; then
  pass "hailo-ollama command is installed."
else
  warn "hailo-ollama command is not installed."
fi

if command -v hailortcli >/dev/null 2>&1; then
  hailort_identify="$(hailortcli fw-control identify 2>&1 || true)"
  if [[ "$hailort_identify" == *"Firmware Version:"* ]]; then
    pass "hailortcli can talk to the Hailo device."
    printf "%s\n" "$hailort_identify" | sed "s/^/    /"
  else
    warn "hailortcli did not return a normal firmware identify response."
    printf "%s\n" "$hailort_identify" | sed "s/^/    /"
  fi
else
  warn "hailortcli is not installed, so firmware-level Hailo validation was skipped."
fi

if command -v curl >/dev/null 2>&1; then
  model_tags="$(curl -fsS http://127.0.0.1:8000/api/tags 2>/dev/null || true)"
  if [[ -n "$model_tags" ]]; then
    pass "Local Hailo model server responded on http://127.0.0.1:8000/api/tags."
    printf "%s\n" "$model_tags" | sed "s/^/    /"
  else
    warn "Local Hailo model server did not respond on http://127.0.0.1:8000/api/tags."
  fi
else
  warn "curl is unavailable, so model server health could not be checked."
fi

section "Audio"

ALFRED_ARECORD_DEVICE="${ALFRED_ARECORD_DEVICE:-default}"
ALFRED_APLAY_DEVICE="${ALFRED_APLAY_DEVICE:-default}"
info "Configured capture device: $ALFRED_ARECORD_DEVICE"
info "Configured playback device: $ALFRED_APLAY_DEVICE"

check_command arecord
check_command aplay
check_command ffmpeg

if command -v arecord >/dev/null 2>&1; then
  capture_list="$(arecord -l 2>&1 || true)"
  if [[ "$capture_list" == *"card "* ]]; then
    pass "ALSA capture devices were detected."
  else
    warn "ALSA capture devices were not listed by arecord -l."
  fi
  printf "%s\n" "$capture_list" | sed "s/^/    /"
fi

if command -v aplay >/dev/null 2>&1; then
  playback_list="$(aplay -l 2>&1 || true)"
  if [[ "$playback_list" == *"card "* ]]; then
    pass "ALSA playback devices were detected."
  else
    warn "ALSA playback devices were not listed by aplay -l."
  fi
  printf "%s\n" "$playback_list" | sed "s/^/    /"
fi

if [[ "$PLAYBACK_TEST" -eq 1 ]]; then
  section "Playback Probe"
  SAMPLE_WAV="/usr/share/sounds/alsa/Front_Center.wav"
  if [[ ! -f "$SAMPLE_WAV" ]]; then
    warn "Playback probe sample $SAMPLE_WAV was not found. Skipping playback test."
  elif ! command -v aplay >/dev/null 2>&1; then
    warn "Cannot run playback probe because aplay is missing."
  else
    info "Playing a short test sample through $ALFRED_APLAY_DEVICE ..."
    if aplay -D "$ALFRED_APLAY_DEVICE" -q "$SAMPLE_WAV" >/dev/null 2>&1; then
      pass "Playback probe completed successfully. You should have heard a voice sample."
    else
      fail "Playback probe failed on device $ALFRED_APLAY_DEVICE."
    fi
  fi
fi

if [[ "$RECORD_TEST" -eq 1 ]]; then
  section "Recording Probe"
  if ! command -v arecord >/dev/null 2>&1; then
    warn "Cannot run recording probe because arecord is missing."
  else
    TEMP_AUDIO_FILE="$(mktemp /tmp/alfred-hwcheck.XXXXXX.wav)"
    info "Recording ${RECORD_SECONDS}s from $ALFRED_ARECORD_DEVICE. Speak a few words now."
    if arecord -D "$ALFRED_ARECORD_DEVICE" -q -f S16_LE -c 1 -r 16000 -d "$RECORD_SECONDS" "$TEMP_AUDIO_FILE" >/dev/null 2>&1; then
      file_size="$(stat -c%s "$TEMP_AUDIO_FILE" 2>/dev/null || echo 0)"
      if [[ "$file_size" -gt 44 ]]; then
        pass "Recording probe captured a non-empty WAV file (${file_size} bytes)."
      else
        fail "Recording probe created an empty or invalid WAV file."
      fi
    else
      fail "Recording probe failed on device $ALFRED_ARECORD_DEVICE."
    fi
  fi
fi

section "Touch Runtime"

if command -v python3 >/dev/null 2>&1; then
  pass "python3 is installed."
else
  fail "python3 is missing."
fi

if [[ -f start_alfred_touch.sh ]]; then
  pass "Found Alfred touch launcher script."
else
  fail "Missing start_alfred_touch.sh."
fi

if command -v chromium-browser >/dev/null 2>&1 || command -v chromium >/dev/null 2>&1; then
  pass "Chromium is installed for kiosk UI use."
else
  warn "Chromium is not installed yet."
fi

section "Summary"

printf "%sPass:%s %s\n" "$C_PASS" "$C_RESET" "$PASS_COUNT"
printf "%sWarn:%s %s\n" "$C_WARN" "$C_RESET" "$WARN_COUNT"
printf "%sFail:%s %s\n" "$C_FAIL" "$C_RESET" "$FAIL_COUNT"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi

exit 0

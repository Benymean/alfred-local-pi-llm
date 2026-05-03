# Alfred Checkpoint 2026-04-30

This file is a handoff checkpoint for the Alfred fork in case the current Codex thread ends or the working tree gets messy.

## Resume Prompt

If you open a new Codex tab, use something like:

`Continue Alfred from docs/alfred-checkpoint-2026-04-30.md. The voice MVP on the Pi is working, the first Waveshare portrait GUI backend is live on hardware, and the next main step is verifying the seesaw rotary encoder input loop plus tuning the one-button interaction model.`

## Project Goal

Alfred is a battery-first, offline Raspberry Pi 5 companion built on a Pi AI HAT+ 2. The target device is:

- portrait `800x480` Waveshare `4.26"` e-paper display
- rotary encoder plus button via Qwiic
- push-to-talk interaction
- warm offline voice assistant
- PDF reader mode

The current priority is a stable MVP, not final polish.

## Hardware And OS

- Raspberry Pi 5 `8GB`
- Raspberry Pi AI HAT+ 2
- Waveshare `4.26"` e-paper HAT `800x480`
- USB mic
- USB speaker
- Qwiic shim + rotary encoder
- Raspberry Pi OS 64-bit Trixie

## Current Alfred Architecture

Main Alfred files:

- `alfred/app.py`
- `alfred/chat.py`
- `alfred/audio.py`
- `alfred/config.py`
- `alfred/debug_cli.py`
- `alfred/display.py`
- `alfred/input.py`
- `alfred/memory.py`
- `alfred/reader.py`
- `alfred/state.py`

Supporting docs and setup:

- `docs/alfred-mvp.md`
- `scripts/setup_alfred_audio.sh`

Important design choice:

- old BMO code remains intact
- Alfred is a parallel app path, not a destructive rewrite of the original project

## What Works Right Now

The Pi voice MVP is working end to end:

- `arecord` microphone capture
- `whisper.cpp` speech-to-text on CPU
- `hailo-ollama` + `qwen3:1.7b` on Hailo
- `piper` text-to-speech on CPU
- streamed LLM reply path
- sentence chunking into a queued TTS worker
- early acknowledgment support
- Hailo-specific fallback when streamed chat rejects repeated `system` role messages

Debug shell commands currently available:

- `talk`
- `record`
- `record 6`
- `replay`
- `devices`
- `audio-check`
- `menu`
- `reader`

The first GUI pass is also in place:

- real `WavesharePortraitDisplay` backend in `alfred/display.py`
- Pillow-based portrait renderer for `eyes`, `text`, `menu`, and `reader`
- optional PNG preview mode for Mac-side UI iteration
- backend selection in `alfred/debug_cli.py` via `--display console|waveshare`

The first encoder pass is also in place:

- real `SeesawEncoderInput` in `alfred/input.py`
- `--input seesaw` hardware loop in `alfred/debug_cli.py`
- hold-to-talk wired into Alfred via start/stop events
- current single-button mapping:
  - short press = select
  - double press = back
  - hold = push-to-talk

## Known Good Pi Run Command

From the Pi:

```bash
cd /home/piadmin/be-more-hailo
ALFRED_ARECORD_DEVICE=plughw:3,0 \
ALFRED_APLAY_DEVICE=plughw:2,0 \
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --backend live --hardware-audio --fresh-memory
```

Current verified ALSA mapping:

- mic: `plughw:3,0`
- speaker: `plughw:2,0`

## Current Voice Timing Snapshot

From the latest successful streamed voice run:

- recording stage: about `4.19s`
- STT stage: about `2.30s`
- first visible streamed LLM chunk: about `3.31s` after LLM start
- first speech chunk available: about `5.99s` after reply generation start
- LLM streaming completed: about `12.60s`
- total voice interaction: about `31.46s`

Interpretation:

- STT is acceptable for MVP
- the biggest remaining latency sources are LLM generation time and Piper playback time
- the overlap is already cleaner than the old fully blocking path

## Important Hailo Quirk

`hailo-ollama` sometimes rejects streamed chat continuations that resend `system` role messages.

Alfred now handles this by:

- trying the normal streamed chat request first
- retrying in a Hailo-safe mode that flattens system guidance into the active user message

This logic lives in `alfred/chat.py`.

## Current Quality Caveats

- factual quality is still rough because `qwen3:1.7b` is small
- Piper still starts per chunk, so speech is better than before but not yet optimal
- the real e-paper backend exists, but still needs live Pi hardware verification
- rotary encoder integration exists, but still needs live Pi verification
- PDF reader mode exists as controller logic, but not yet true e-paper page rendering

## Recommended Next Step

The next main implementation pass should be input + hardware validation:

1. verify the seesaw rotary encoder loop on the Pi
2. tune hold/double-press thresholds and rotation direction if needed
3. add first-pass PDF page rendering

Audio/latency work should stay on the backlog after the display/input shell is alive:

- persistent Piper worker
- better fast/slow model routing
- possibly smaller faster chat model for casual voice turns

## Current Working Tree Scope

The current checkpoint corresponds to local working tree changes in:

- `.gitignore`
- `alfred/`
- `docs/`
- `scripts/setup_alfred_audio.sh`

## Snapshot Files

This checkpoint should be paired with the source snapshot archive in:

- `snapshots/alfred-checkpoint-2026-04-30.tgz`
- `snapshots/alfred-checkpoint-2026-04-30.sha256`

If the thread context disappears, the handoff doc plus that archive should be enough to continue cleanly in a new Codex session.

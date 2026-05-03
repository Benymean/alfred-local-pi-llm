# Alfred Checkpoint 2026-04-30 (Second Checkpoint)

This file is the second handoff checkpoint for Alfred. It captures the point where the hardware UI loop is working on the Raspberry Pi with the Waveshare e-paper display and the Qwiic rotary encoder.

## Resume Prompt

If you open a new Codex tab, use something like:

`Continue Alfred from docs/alfred-checkpoint-2026-04-30-2.md. The Waveshare display works, the seesaw rotary encoder works, push-to-talk works, and the current implementation pass is Poppler-based PDF page rendering for reader mode.`

## Current Milestone

Alfred now works as a real hardware prototype on the Pi:

- portrait Waveshare `4.26"` `800x480` e-paper display is rendering
- idle eyes work
- text reply cards work
- menu rendering works
- encoder rotation opens and navigates the menu
- short press selects
- double press goes back
- hold activates push-to-talk
- release stops recording and continues through STT -> LLM -> TTS

This is the second major checkpoint after the earlier voice-only MVP.

## Hardware And OS

- Raspberry Pi 5 `8GB`
- Raspberry Pi AI HAT+ 2
- Waveshare `4.26"` e-paper HAT `800x480`
- Adafruit seesaw rotary encoder over Qwiic
- USB mic
- USB speaker
- Raspberry Pi OS 64-bit Trixie

## What Works Right Now

### Display

- real `WavesharePortraitDisplay` backend in `alfred/display.py`
- portrait rendering for:
  - idle/listening/thinking eyes
  - text replies
  - menu
  - reader shell
- `--hold-last-screen` works for one-shot demo screens
- e-paper reply dwell is longer than console dwell
- visible black/white inversion every few changes is expected because Alfred periodically falls back to full refresh to avoid ghosting

### Input

- real `SeesawEncoderInput` in `alfred/input.py`
- hardware loop enabled with `--input seesaw`
- current button model:
  - rotate = next/prev
  - short press = select
  - double press = back
  - hold = push-to-talk
- if the knob feels reversed, set `ALFRED_ENCODER_INVERT_DIRECTION=true`

### Voice

- `arecord` microphone capture
- `whisper.cpp` STT
- `hailo-ollama` + `qwen3:1.7b`
- streamed reply path with sentence chunking
- `piper` TTS
- push-to-talk now works from the encoder, not only from the SSH debug shell

## Important Working Commands

### Main hardware run on the Pi

```bash
cd /home/piadmin/be-more-hailo
ALFRED_DISPLAY_BACKEND=waveshare \
ALFRED_WAVESHARE_LIB_DIR=/home/piadmin/e-Paper/RaspberryPi_JetsonNano/python/lib \
ALFRED_ARECORD_DEVICE=plughw:3,0 \
ALFRED_APLAY_DEVICE=plughw:2,0 \
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --display waveshare --input seesaw --backend live --hardware-audio --fresh-memory
```

### One-shot display test

```bash
cd /home/piadmin/be-more-hailo
ALFRED_DISPLAY_BACKEND=waveshare \
ALFRED_WAVESHARE_LIB_DIR=/home/piadmin/e-Paper/RaspberryPi_JetsonNano/python/lib \
ALFRED_TEXT_THRESHOLD=1 \
python3 -m alfred --display waveshare --backend mock --oneshot "Tell me a longer answer about why Alfred is a calm e-paper companion." --hold-last-screen
```

### Stop Alfred

When running with `--input seesaw`, Alfred is not waiting for typed shell commands.

To exit, press:

```bash
Ctrl+C
```

## Current Pi Device Mapping

- microphone: `plughw:3,0`
- speaker: `plughw:2,0`
- encoder I2C address: `0x36`
- encoder button pin on seesaw: `24`

## Current Quality State

Hardware-wise, Alfred is in good shape for an MVP demo.

Model-quality-wise, Alfred still needs work:

- `qwen3:1.7b` is small and can hallucinate
- factual/media answers can still be weak
- current-info questions like weather should now be intercepted instead of guessed
- some Hailo failures were caused by multiline remembered turns; memory/messages were flattened to single-line to avoid that JSON render failure

## Known Hailo Quirks

Two important Hailo-specific issues are already handled in code:

1. repeated `system` role messages can fail on continued conversations
   - Alfred retries with flattened system guidance in the user message

2. multiline message history can break Hailo prompt rendering
   - Alfred now flattens stored memory and outbound messages to single-line text before sending

These fixes live mainly in:

- `alfred/chat.py`
- `alfred/memory.py`

## Current Next Step

The next most valuable pass is not more hardware. It is response-quality stabilization:

1. test current/factual/media questions after the latest safety patch
2. make Alfred more honest when uncertain
3. possibly separate social chat behavior from factual question behavior
4. only after that, return to reader work:
   - real PDF page rendering
   - reading position/bookmarks later

A reusable validation checklist now exists in:

- `docs/alfred-validation-process.md`

That document also records the latest findings:

- factual answers are mostly good
- current-info fallback is working
- casual/social responses still need meaningful improvement
- there is at least one current-info false positive edge case to revisit

## Files Most Relevant Now

- `alfred/app.py`
- `alfred/audio.py`
- `alfred/chat.py`
- `alfred/config.py`
- `alfred/debug_cli.py`
- `alfred/display.py`
- `alfred/input.py`
- `alfred/memory.py`
- `alfred/reader.py`
- `docs/alfred-mvp.md`
- `scripts/setup_alfred_audio.sh`
- `scripts/setup_alfred_display.sh`
- `scripts/setup_alfred_encoder.sh`
- `scripts/setup_alfred_reader.sh`

## Snapshot Pairing

This checkpoint should be paired with:

- `snapshots/alfred-checkpoint-2026-04-30-2.tgz`
- `snapshots/alfred-checkpoint-2026-04-30-2.sha256`

If the thread context disappears, this file plus that archive should be enough to continue from the current hardware-working state.

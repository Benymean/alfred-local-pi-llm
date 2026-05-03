# Alfred MVP Scaffold

This repo now contains a parallel Alfred app path that keeps the BMO code intact while starting the new e-paper companion architecture.

## What is included

- `alfred/app.py`
  Alfred state machine for idle eyes, menu navigation, chat replies, and reader mode.
- `alfred/chat.py`
  Alfred personality prompt, rolling memory integration, a mock backend, and a live Hailo/Ollama-style HTTP backend.
- `alfred/memory.py`
  Persistent summary plus recent exchanges so small models keep context without carrying a full transcript.
- `alfred/display.py`
  Console display backend plus the first real Waveshare portrait renderer.
- `alfred/input.py`
  Debug command parser plus the first real Qwiic rotary encoder input path.
- `alfred/reader.py`
  PDF library scan, page navigation controller, and first-pass Poppler-based PDF page renderer.
- `alfred/audio.py`
  Alfred-native recorder/STT/TTS wrappers using `arecord`, `ffmpeg`, `whisper.cpp`, `piper`, and `aplay`.
- `docs/alfred-validation-process.md`
  Reusable manual validation checklist and current behavioral findings for Alfred on real hardware.

## Current behavior

- Boots into idle eyes.
- Opens a menu when you rotate from idle in the debug shell.
- Supports `Talk` and `Reader`.
- Shows text only for longer or more structured replies.
- Keeps separate memory files for `mock` and `live` debug runs by default.
- Uses `./books` locally and `/home/piadmin/books` on the Pi unless you override `ALFRED_BOOKS_DIR`.
- Supports a `record` debug command when run with `--hardware-audio`.
- Falls back to `arecord` automatically if Python `sounddevice` is unavailable on the Pi.
- Resolves `piper`, `whisper-cli`, `ffmpeg`, `arecord`, and `aplay` from either the repo paths or the system `PATH`.
- Includes `devices` and `audio-check` commands for Pi-side audio diagnostics.
- Uses a smaller default `num_predict` budget and Qwen3's `/no_think` hint to reduce voice latency.
- Voice interactions use an even smaller generation budget plus a short-answer style reminder to reduce thinking and speaking time.
- Alfred can now render real portrait e-paper screens for `eyes`, `text`, `menu`, and `reader`.
- The Waveshare path can also emit PNG previews so we can design Alfred's GUI on a Mac before pushing to the Pi.
- Alfred can now poll the Adafruit seesaw rotary encoder over I2C for real hardware navigation.
- Alfred can now render real PDF pages for reader mode when `pdftoppm` is available.
- Alfred now remembers the last page and slice for each PDF and resumes where you left off.
- In an open book, single click now toggles between Alfred's reflowed text mode and the original PDF page view.

## Run it locally

Mock backend:

```bash
python3 -m alfred
```

One-shot prompt:

```bash
python3 -m alfred --oneshot "What should Alfred look like?"
```

Live backend against a local Hailo/Ollama-compatible server:

```bash
ALFRED_LLM_URL=http://127.0.0.1:8000/api/chat \
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --backend live
```

Fresh live test with empty memory:

```bash
ALFRED_LLM_URL=http://127.0.0.1:8000/api/chat \
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --backend live --fresh-memory
```

Useful latency tuning overrides:

```bash
ALFRED_LLM_NUM_PREDICT=120 \
ALFRED_VOICE_LLM_NUM_PREDICT=72 \
ALFRED_LLM_TEMPERATURE=0.5 \
ALFRED_LLM_USE_NO_THINK=true \
python3 -m alfred --backend live
```

Preview the Waveshare-style GUI locally without real display hardware:

```bash
ALFRED_DISPLAY_PREVIEW_DIR=.alfred-display-preview \
python3 -m alfred --display waveshare --preview-only --backend mock --oneshot "Tell me something calm and kind about Alfred."
```

The preview PNGs will appear in `.alfred-display-preview/`.

If you want a one-shot GUI test to stay on the final e-paper screen instead of snapping back to idle, add:

```bash
--hold-last-screen
```

Pi voice test with microphone + speaker:

```bash
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --backend live --hardware-audio --fresh-memory
```

Pi hardware control loop with the encoder:

```bash
python3 -m alfred --input seesaw --backend live --hardware-audio --fresh-memory
```

If `audio-check` reports missing `whisper.cpp` or `piper`, install Alfred's audio stack on the Pi with:

```bash
bash scripts/setup_alfred_audio.sh
```

If Alfred cannot render PDF pages yet, install the reader stack on the Pi with:

```bash
bash scripts/setup_alfred_reader.sh
```

Recommended Alfred voice split for MVP:

- `Qwen3-1.7B` on the Hailo AI HAT
- `whisper.cpp` with `ggml-base.en.bin` on the Pi CPU
- `Piper` on the Pi CPU

## Waveshare display setup on the Pi

The current GUI pass targets the official Waveshare `4.26"` `800x480` Python driver for `epd4in26`.

Dependencies from the Waveshare manual:

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-pil python3-numpy python3-gpiozero
python3 -m pip install spidev
```

Enable `SPI` on the Pi if needed:

```bash
sudo raspi-config
```

Then install the official Waveshare Python library by cloning their repo:

```bash
cd /home/piadmin
git clone https://github.com/waveshare/e-Paper.git
```

Alfred expects the Waveshare `python/lib` directory, so point it at:

```bash
export ALFRED_WAVESHARE_LIB_DIR=/home/piadmin/e-Paper/RaspberryPi_JetsonNano/python/lib
```

You can also let Alfred install that display stack for you on the Pi:

```bash
bash scripts/setup_alfred_display.sh
```

## Encoder setup on the Pi

Alfred's current hardware input path targets the Adafruit seesaw rotary encoder at I2C address `0x36`.

Install the Pi-side encoder dependencies with:

```bash
bash scripts/setup_alfred_encoder.sh
```

That installs:

- `adafruit-blinka`
- `adafruit-circuitpython-seesaw`

The current Alfred encoder behavior is:

- rotate: navigate next/previous
- short press: select, or toggle text/page mode inside an open book
- double press: back
- hold: push-to-talk

If the rotation direction feels backwards on your knob, try:

```bash
export ALFRED_ENCODER_INVERT_DIRECTION=true
```

## Reader setup on the Pi

Alfred's PDF page renderer uses Poppler's `pdftoppm`.

Install it with:

```bash
bash scripts/setup_alfred_reader.sh
```

That installs:

- `pdfinfo`
- `pdftoppm`
- `pdftotext`

If you want to override the command Alfred uses:

```bash
export ALFRED_PDFTOPPM_CMD=pdftoppm
export ALFRED_PDFTOTEXT_CMD=pdftotext
```

Reader progress is stored separately from chat memory. On the Pi, Alfred defaults to:

```bash
/home/piadmin/.alfred-reader-state.json
```

The current portrait renderer defaults to a `90` degree rotation. If the screen comes up upside-down, try:

```bash
export ALFRED_DISPLAY_ROTATION=270
```

By default, Alfred keeps text replies visible on the e-paper display for about `8` seconds before returning to idle eyes. Override that with:

```bash
export ALFRED_EPAPER_REPLY_DWELL_SECONDS=12
```

First real display test on the Pi:

```bash
ALFRED_DISPLAY_BACKEND=waveshare \
ALFRED_WAVESHARE_LIB_DIR=/home/piadmin/e-Paper/RaspberryPi_JetsonNano/python/lib \
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --display waveshare --backend mock --oneshot "Alfred is ready." --hold-last-screen
```

If your Pi uses system-installed binaries instead of repo-local ones, Alfred can use them too:

```bash
ALFRED_WHISPER_CMD=whisper-cli \
ALFRED_PIPER_CMD=piper \
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --backend live --hardware-audio --fresh-memory
```

If your USB mic is not the default ALSA capture device, override it:

```bash
ALFRED_ARECORD_DEVICE=plughw:1,0 \
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --backend live --hardware-audio --fresh-memory
```

On the current Alfred Pi hardware stack we saw:

- USB mic on `plughw:3,0`
- USB speaker on `plughw:2,0`

So this is a strong starting command:

```bash
ALFRED_ARECORD_DEVICE=plughw:3,0 \
ALFRED_APLAY_DEVICE=plughw:2,0 \
ALFRED_DISPLAY_BACKEND=waveshare \
ALFRED_WAVESHARE_LIB_DIR=/home/piadmin/e-Paper/RaspberryPi_JetsonNano/python/lib \
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --backend live --hardware-audio --input seesaw --fresh-memory
```

If your speaker is not ALSA default, override playback too:

```bash
ALFRED_ARECORD_DEVICE=plughw:1,0 \
ALFRED_APLAY_DEVICE=plughw:2,0 \
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --backend live --hardware-audio --fresh-memory
```

## Debug commands

- `talk <message>`
- `talk` then type your message at the `you>` prompt
- `record`
  Starts recording immediately and, in the SSH debug shell, stops when you press `Enter` or when Alfred hits the max recording time.
- `record 6`
  Fixed-length timed recording, useful for repeatable testing.
- `replay`
- `devices`
- `audio-check`
- `menu`
- `next`
- `prev`
- `select`
- `reader`
- `open <index>`
- `back`
- `home`
- `quit`

## Validation Process

Use the hardware validation checklist in:

```text
docs/alfred-validation-process.md
```

That document is the current source of truth for:

- factual-question testing
- casual/social-question testing
- current-info fallback testing
- nonsense-question testing
- empty-audio recovery testing
- the latest observed weaknesses and recommended next optimization pass

## Display options

- `--display console`
  Keeps the current SSH-friendly text UI.
- `--display waveshare`
  Uses the new portrait Alfred GUI backend.
- `--display-preview-dir <dir>`
  Saves PNG snapshots of each rendered Alfred screen.
- `--preview-only`
  Renders the Waveshare GUI without touching real SPI hardware.
- `--hold-last-screen`
  Leaves a one-shot reply on the display instead of immediately returning to idle.

## Input options

- `--input debug`
  Keeps the current SSH command shell.
- `--input seesaw`
  Uses the real Qwiic rotary encoder on the Pi.

## Next Alfred passes

1. Verify PDF page rendering on the Pi with real books in `/home/piadmin/books`.
2. Add per-document reading position memory.
3. Tighten the voice latency path further with a persistent Piper worker.
4. Refine the single-button interaction model if Alfred needs a different `back/home` gesture.

# Alfred Checkpoint 2026-04-30 (Third Checkpoint)

This file is the third handoff checkpoint for Alfred. It captures the point where the hardware voice loop works, the reader is genuinely usable on the e-paper display, reading position resumes per book, and single click inside a book toggles between Alfred text mode and original PDF page mode.

## Resume Prompt

If you open a new Codex tab, use something like:

`Continue Alfred from docs/alfred-checkpoint-2026-04-30-3.md. The Waveshare display, seesaw encoder, push-to-talk voice loop, readable PDF reader, resume-per-book, and in-book text/page mode toggle are all working on the Pi.`

## Current Milestone

Alfred now works as a real hardware prototype with a practical e-reader mode:

- portrait Waveshare `4.26"` `800x480` e-paper display is rendering
- idle eyes, text replies, menu, and reader screens work
- encoder rotation opens the menu from idle and navigates correctly
- short press selects, and inside an open book it toggles `Text Mode` vs `Page Mode`
- double press goes back
- hold activates push-to-talk
- release stops recording and continues through STT -> LLM -> TTS
- PDF reading is now actually readable because Alfred reflows text with `pdftotext` when possible
- Alfred remembers the last page and slice per book and resumes from there

This is the third major checkpoint after the earlier voice MVP and hardware-loop checkpoints.

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
  - reader library
  - reader document view
- Alfred can now auto-detect the standard Waveshare Python library path on the Pi if it exists at:
  - `/home/piadmin/e-Paper/RaspberryPi_JetsonNano/python/lib`
- visible black/white inversion every few changes is still expected because Alfred periodically uses full refresh to avoid ghosting

### Input

- real `SeesawEncoderInput` in `alfred/input.py`
- hardware loop enabled with `--input seesaw`
- current button model:
  - rotate = navigate next/previous
  - short press = select, or toggle `Text Mode` / `Page Mode` inside an open book
  - double press = back
  - hold = push-to-talk
- encoder startup is more resilient now:
  - Alfred retries seesaw initialization several times
  - if startup still fails, Alfred prints a friendlier error instead of a long traceback

### Voice

- `arecord` microphone capture
- `whisper.cpp` STT
- `hailo-ollama` + `qwen3:1.7b`
- streamed reply path with sentence chunking
- `piper` TTS
- push-to-talk works from the encoder

### Reader

- `Reader` now scans PDFs from `/home/piadmin/books`
- `pdftotext` reflow mode makes book-like PDFs readable on the e-paper display
- fallback `pdftoppm` page rendering still exists for layout-sensitive pages
- single click inside a book toggles:
  - `Text Mode` = Alfred reflowed text
  - `Page Mode` = original PDF page snapshot
- reader progress is persisted per document in:
  - `/home/piadmin/.alfred-reader-state.json`

## Important Working Commands

### Main hardware run on the Pi

```bash
cd /home/piadmin/be-more-hailo
ALFRED_DISPLAY_BACKEND=waveshare \
ALFRED_ARECORD_DEVICE=plughw:3,0 \
ALFRED_APLAY_DEVICE=plughw:2,0 \
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --display waveshare --input seesaw --backend live --hardware-audio --fresh-memory
```

### Important note about the model server

Alfred assumes the local Hailo model server is running at:

```bash
http://127.0.0.1:8000
```

If talk mode says it cannot reach the model, check:

```bash
curl http://127.0.0.1:8000/api/tags
```

If that fails, start the server first:

```bash
hailo-ollama serve
```

The normal Pi workflow is:

1. terminal 1:

```bash
hailo-ollama serve
```

2. terminal 2:

```bash
cd /home/piadmin/be-more-hailo
ALFRED_DISPLAY_BACKEND=waveshare \
ALFRED_ARECORD_DEVICE=plughw:3,0 \
ALFRED_APLAY_DEVICE=plughw:2,0 \
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --display waveshare --input seesaw --backend live --hardware-audio --fresh-memory
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

Hardware-wise, Alfred is in good shape for a working prototype:

- voice loop works
- reader works
- resume works
- text/page toggle works

The main remaining polish areas are now mostly product/UX quality rather than basic functionality:

- answer quality still needs improvement, especially nuanced social responses
- startup could be turned into a cleaner appliance experience with a service or boot script
- reader library presentation could be nicer
- power/sleep behavior is still a future pass

## Known Operational Quirks

### Model server availability

If `hailo-ollama` is not running, Alfred’s talk mode will fail with connection refused errors to `127.0.0.1:8000`.

### Encoder visibility vs startup

The encoder can show up correctly on:

```bash
i2cdetect -y 1
```

and still occasionally fail a first seesaw identity read. Alfred now retries that startup path.

### Page mode readability

`Page Mode` is useful for:

- diagrams
- tables
- covers
- layout-sensitive pages

but it is not the preferred mode for dense prose. `Text Mode` should remain the default reading mode for books.

## Current Next Step

The next most valuable polishing passes are likely:

1. reader/library polish
   - cleaner titles
   - optional resume hints in the library
2. startup/appliance polish
   - one-command start
   - possibly `systemd`
3. power behavior
   - sleep / standby strategy
4. voice polish
   - answer quality
   - latency

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
- `alfred/state.py`
- `docs/alfred-mvp.md`
- `docs/alfred-validation-process.md`
- `scripts/setup_alfred_audio.sh`
- `scripts/setup_alfred_display.sh`
- `scripts/setup_alfred_encoder.sh`
- `scripts/setup_alfred_reader.sh`

## Snapshot Pairing

This checkpoint should be paired with:

- `snapshots/alfred-checkpoint-2026-04-30-3.tgz`
- `snapshots/alfred-checkpoint-2026-04-30-3.sha256`

If the thread context disappears, this file plus that archive should be enough to continue from the current reader-and-voice working state.

# Alfred Full Handoff 2026-04-30

This is the full handoff document for Alfred as of the current working prototype state. It is meant to give a new Codex chat enough context to continue without reconstructing the project history from scratch.

Important note:

- this document describes the earlier e-paper + encoder + reader era of Alfred
- the current touch-first product direction is captured in `docs/alfred-checkpoint-2026-05-02.md`
- the latest touch + streaming voice + performance checkpoint is `docs/alfred-checkpoint-2026-05-02-2.md`
- the latest fast-Whisper + answer-debug checkpoint is `docs/alfred-checkpoint-2026-05-03.md`

## Resume Prompt

If you open a new Codex tab, use something like:

`Continue Alfred from docs/alfred-full-handoff-2026-04-30.md. Alfred is a Raspberry Pi + Hailo offline companion with a Waveshare e-paper display, seesaw rotary encoder, push-to-talk voice loop, readable PDF reader, per-book resume, and text/page mode toggle. I want to continue polishing the device from the current working state.`

## Project Goal

Alfred is a battery-first, offline AI companion and e-reader built on a Raspberry Pi 5.

Core product direction:

- offline speech-to-text -> local LLM -> text-to-speech
- portrait Waveshare e-paper display
- rotary encoder + button instead of touch UI
- friendly conversational companion
- separate reader mode for books/PDFs
- power-efficient, appliance-like behavior

## Hardware Stack

Confirmed user hardware:

- Raspberry Pi 5 `8GB`
- Raspberry Pi Active Cooler
- Raspberry Pi AI HAT+ 2
- Waveshare `4.26"` e-paper HAT `800x480`
- SparkFun Qwiic SHIM
- Adafruit STEMMA QT / Qwiic I2C rotary encoder breakout
- rotary knob
- USB microphone
- USB speaker
- Raspberry Pi OS 64-bit Trixie

Planned later:

- Raspberry Pi 5 18650 Battery UPS HAT

## Product Decisions Already Made

- Project name: `Alfred`
- Default screen behavior:
  - `idle`, `listening`, `thinking`: eyes
  - longer/information-heavy answers: text
  - `reader`: text/page only
- Boot behavior:
  - boots into idle eyes
  - rotate from idle opens menu
- Main modes:
  - `Talk`
  - `Reader`
- Push-to-talk:
  - hold button to record
  - release to stop and process
- Display orientation:
  - portrait
- Reader:
  - PDF-first
  - text-only-first
  - no text-to-speech reading mode yet
- Model path:
  - Hailo local model path with `qwen3:1.7b`
- Vision:
  - out of scope
- Development:
  - SSH debug mode is allowed and used

## Current Working State

Alfred currently works as a real hardware prototype:

- Waveshare e-paper display renders successfully
- encoder works over I2C at `0x36`
- push-to-talk voice loop works
- `whisper.cpp` STT works
- `hailo-ollama` + `qwen3:1.7b` works
- `piper` TTS works
- menu and reader navigation work
- PDF reader is now readable via reflowed text mode
- single click inside a book toggles between:
  - `Text Mode`
  - `Page Mode`
- Alfred remembers last reading position per book

What is still weak:

- social/conversational response quality is still not where the user wants it
- startup is still manual, not appliance-like
- error handling can still be more user-friendly
- power behavior is not polished yet

## Current Runtime Architecture

The active Alfred path is under `alfred/`. The original BMO codebase remains intact and is now mostly reference material.

Important Alfred modules:

- [alfred/app.py](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/alfred/app.py)
  Main Alfred state machine and command handling.
- [alfred/chat.py](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/alfred/chat.py)
  Chat request profiles, prompt shaping, Hailo HTTP backend, current-info guardrails, social tuning layer.
- [alfred/memory.py](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/alfred/memory.py)
  Rolling summary + recent turns. Messages are flattened to single-line before sending back to Hailo.
- [alfred/audio.py](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/alfred/audio.py)
  Recorder, STT, TTS, replay, diagnostics, `arecord` fallback, streaming TTS support.
- [alfred/display.py](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/alfred/display.py)
  Console display backend, Pillow renderer, Waveshare backend, partial/full refresh logic.
- [alfred/input.py](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/alfred/input.py)
  Debug command parser plus hardware seesaw input backend.
- [alfred/reader.py](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/alfred/reader.py)
  PDF library scan, readable text reflow, PDF image fallback, resume-per-book state.
- [alfred/config.py](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/alfred/config.py)
  Central config/env handling.
- [alfred/debug_cli.py](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/alfred/debug_cli.py)
  Entry glue for backend/display/input/audio setup and run loop.
- [alfred/state.py](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/alfred/state.py)
  Screen states, command types, reader view model.

## Current Interaction Model

### Hardware controls

Current knob/button behavior:

- Rotate from `idle`:
  - opens menu
- Rotate in `menu`:
  - move selection
- Rotate in `reader library`:
  - move selection
- Rotate in `reader document`:
  - next/previous text slice or page
- Short press:
  - select in menu/library
  - toggle `Text Mode` / `Page Mode` inside an open book
- Double press:
  - back
- Hold:
  - push-to-talk start
- Release after hold:
  - push-to-talk stop

### Reader behavior

Reader behavior now:

- `Text Mode`:
  - uses `pdftotext`
  - reflows PDF text into Alfred-sized reading screens
  - this is the preferred/default reading mode
- `Page Mode`:
  - shows original PDF page layout snapshot
  - useful for tables, diagrams, covers, layout-sensitive pages
- Reading position:
  - remembers page and slice per book
  - reopens at last position

## Current Data / State Files

Important runtime files:

- Chat memory:
  - `alfred_memory_live.json`
  - `alfred_memory_mock.json`
  - created in repo root by default during runs
- Reader progress:
  - `/home/piadmin/.alfred-reader-state.json` on the Pi by default
- Reader cache:
  - `.alfred-reader-cache/`
- Audio temp dir:
  - `.alfred-audio/`

## Important Commands

### Main hardware run on the Pi

Use this as the main device run:

```bash
cd /home/piadmin/be-more-hailo
ALFRED_DISPLAY_BACKEND=waveshare \
ALFRED_ARECORD_DEVICE=plughw:3,0 \
ALFRED_APLAY_DEVICE=plughw:2,0 \
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --display waveshare --input seesaw --backend live --hardware-audio --fresh-memory
```

### Important model-server note

Alfred expects the local model server at:

```bash
http://127.0.0.1:8000
```

If talk mode fails with connection refused, the likely fix is:

```bash
hailo-ollama serve
```

Useful check:

```bash
curl http://127.0.0.1:8000/api/tags
```

Recommended Pi workflow:

Terminal 1:

```bash
hailo-ollama serve
```

Terminal 2:

```bash
cd /home/piadmin/be-more-hailo
ALFRED_DISPLAY_BACKEND=waveshare \
ALFRED_ARECORD_DEVICE=plughw:3,0 \
ALFRED_APLAY_DEVICE=plughw:2,0 \
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --display waveshare --input seesaw --backend live --hardware-audio --fresh-memory
```

### Debug terminal mode

If encoder debugging is needed:

```bash
python3 -m alfred --display waveshare --input debug --backend live --hardware-audio --fresh-memory
```

### Stop Alfred

In seesaw hardware loop mode:

```bash
Ctrl+C
```

## Current Pi Device Mapping

- microphone ALSA device: `plughw:3,0`
- speaker ALSA device: `plughw:2,0`
- encoder I2C address: `0x36`
- seesaw button pin: `24`

## Environment Variables And Current Defaults

These come from [alfred/config.py](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/alfred/config.py).

### LLM / chat

- `ALFRED_LLM_URL`
  - default: `http://127.0.0.1:8000/api/chat`
- `ALFRED_LLM_MODEL`
  - default: `qwen3:1.7b`
- `ALFRED_LLM_TEMPERATURE`
  - default: `0.55`
- `ALFRED_LLM_NUM_PREDICT`
  - default: `96`
- `ALFRED_LLM_NUM_CTX`
  - default: `3072`
- `ALFRED_LLM_TIMEOUT_SECONDS`
  - default: `180`
- `ALFRED_LLM_USE_NO_THINK`
  - default: `true`
- `ALFRED_VOICE_LLM_NUM_PREDICT`
  - default: `72`
- `ALFRED_VOICE_REPLY_MAX_WORDS`
  - default: `45`
- `ALFRED_VOICE_REPLY_MAX_SENTENCES`
  - default: `2`

### Memory / transcript

- `ALFRED_MEMORY_PATH`
  - default: `alfred_memory.json`, but `debug_cli.py` overrides to `alfred_memory_live.json` or `alfred_memory_mock.json`
- `ALFRED_TEXT_THRESHOLD`
  - default: `140`
- `ALFRED_RECENT_EXCHANGES`
  - default: `6`
- `ALFRED_SUMMARY_CHAR_LIMIT`
  - default: `1600`

### Books / reader

- `ALFRED_BOOKS_DIR`
  - default on Pi: `/home/piadmin/books`
- `ALFRED_READER_CACHE_DIR`
  - default: `<repo>/.alfred-reader-cache`
- `ALFRED_PDFTOPPM_CMD`
  - default: `pdftoppm`
- `ALFRED_PDFTOTEXT_CMD`
  - default: `pdftotext`
- `ALFRED_READER_RENDER_DPI`
  - default: `130`
- `ALFRED_READER_STATE_PATH`
  - default on Pi: `/home/piadmin/.alfred-reader-state.json`

### Display

- `ALFRED_DISPLAY_BACKEND`
  - default: `console`
- `ALFRED_DISPLAY_ROTATION`
  - default: `90`
- `ALFRED_DISPLAY_PREVIEW_DIR`
  - default: unset
- `ALFRED_EPD_FULL_REFRESH_EVERY`
  - default: `6`
- `ALFRED_WAVESHARE_LIB_DIR`
  - default: auto-detected if standard Waveshare repo exists, otherwise unset
- `ALFRED_REPLY_DWELL_SECONDS`
  - default console dwell: `1.5`
- `ALFRED_EPAPER_REPLY_DWELL_SECONDS`
  - default e-paper dwell: `8.0`

### Encoder

- `ALFRED_ENCODER_I2C_ADDRESS`
  - default: `0x36`
- `ALFRED_ENCODER_BUTTON_PIN`
  - default: `24`
- `ALFRED_ENCODER_POLL_INTERVAL_SECONDS`
  - default: `0.03`
- `ALFRED_ENCODER_TALK_HOLD_SECONDS`
  - default: `0.45`
- `ALFRED_ENCODER_DOUBLE_PRESS_WINDOW_SECONDS`
  - default: `0.35`
- `ALFRED_ENCODER_INVERT_DIRECTION`
  - default: `false`

### Audio

- `ALFRED_MIC_SAMPLE_RATE`
  - default: `48000`
- `ALFRED_MIC_DEVICE_INDEX`
  - default: unset
- `ALFRED_MIC_NAME`
  - default: `USB Audio Device`
- `ALFRED_RECORDING_MAX_SECONDS`
  - default: `10`
- `ALFRED_SILENCE_THRESHOLD`
  - default: `500`
- `ALFRED_LEADING_SILENCE_CHUNKS`
  - default: `100`
- `ALFRED_TRAILING_SILENCE_CHUNKS`
  - default: `40`
- `ALFRED_ARECORD_DEVICE`
  - default: `default`
- `ALFRED_APLAY_DEVICE`
  - default: `default`
- `ALFRED_PIPER_CMD`
  - default: `<repo>/piper/piper`
- `ALFRED_PIPER_MODEL`
  - default: `<repo>/piper/bmo.onnx`
- `ALFRED_PIPER_SAMPLE_RATE`
  - default: `22050`
- `ALFRED_WHISPER_CMD`
  - default: `<repo>/whisper.cpp/build/bin/whisper-cli`
- `ALFRED_WHISPER_MODEL`
  - default: `<repo>/models/ggml-base.en.bin`
- `ALFRED_FFMPEG_CMD`
  - default: `ffmpeg`
- `ALFRED_AUDIO_TEMP_DIR`
  - default: `<repo>/.alfred-audio`

### Debug / misc

- `ALFRED_DEBUG_TTS`
  - default: `true`

## Important Internal Structures

### Main command types

From [alfred/state.py](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/alfred/state.py):

- `TALK`
- `RECORD`
- `PUSH_TO_TALK_START`
- `PUSH_TO_TALK_STOP`
- `REPLAY_LAST_AUDIO`
- `DEVICES`
- `AUDIO_CHECK`
- `MENU`
- `ROTATE_CW`
- `ROTATE_CCW`
- `SELECT`
- `BACK`
- `HOME`
- `OPEN_READER`
- `OPEN_DOCUMENT`
- `QUIT`
- `HELP`

### Reader view state

Important `ReaderViewModel` fields:

- `library`
- `selected_index`
- `current_document`
- `current_page`
- `total_pages`
- `current_segment`
- `total_segments`
- `render_mode`
- `preview`
- `page_image_path`
- `status`

### Reader persistence

Important reader-side types:

- `ReaderProgress`
- `ReaderProgressStore`
- `PdfRenderResult`
- `PdfPageRenderer`
- `ReaderController`

### Chat/memory notes

- Hailo is sensitive to repeated `system` role handling and multiline message content
- memory/history is flattened to single-line before sending to Hailo
- there is a Hailo-safe retry path in `alfred/chat.py`
- current-info questions like weather/news/current leaders should be intercepted instead of guessed

## What We Built / Changed

Major work completed across the current chat history:

1. Alfred app scaffold separated from legacy BMO code
2. voice pipeline working on Pi
   - `arecord` -> `whisper.cpp` -> `hailo-ollama` -> `piper`
3. streaming voice response path
   - sentence chunking
   - queued TTS
   - early acknowledgment
4. Hailo-specific robustness fixes
   - retry without fragile `system` role handling
   - flatten multiline memory/history
5. Waveshare display backend
   - eyes/text/menu/reader
   - preview mode on Mac
6. seesaw encoder hardware loop
7. validation process doc
8. social tuning pass
   - still not considered “done”
9. PDF reader rendering
   - first `pdftoppm`
   - then readable `pdftotext` reflow mode
10. per-book resume state
11. single-click reader mode toggle
12. more resilient encoder startup
13. auto-detect Waveshare Python lib path

## Validation Findings So Far

See [alfred-validation-process.md](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/docs/alfred-validation-process.md) for the reusable checklist and test history.

Main takeaways:

- factual questions are mostly okay
- current-info fallback is working
- social/casual answers still feel too weak or simplistic
- nonsense handling is mostly stable but can still get weird
- hardware path is now much stronger than model-personality quality

## Current Known Quirks

### Model server

If `hailo-ollama` is not running, talk mode fails with:

- `Connection refused`
- `127.0.0.1:8000`

This is operational, not a prompt bug.

### Encoder startup

The encoder can appear on `i2cdetect -y 1` and still occasionally fail the first seesaw ID read. Alfred now retries this startup path.

### E-paper refresh inversion

Periodic black/white inversion is expected because Alfred still uses full refresh periodically to fight ghosting.

### Page Mode vs Text Mode

`Page Mode` is not meant to be the main reading mode for dense prose. `Text Mode` is the primary book-reading mode.

## Recommended Next Work

My suggested priority order from here:

1. `Reader library polish`
   - cleaner titles
   - resume hints in the library
   - maybe percent progress

2. `Appliance startup`
   - one clean launch path
   - `systemd` for Alfred and maybe `hailo-ollama`
   - automatic restart if service dies

3. `Failure handling`
   - clearer on-screen messages for:
     - model offline
     - mic failure
     - speaker failure
     - reader render issues

4. `Power behavior`
   - sleep / standby strategy
   - display sleep
   - later UPS/battery integration

5. `Voice / answer quality`
   - social response quality
   - latency improvements
   - maybe persistent Piper worker

## Existing Checkpoints And Snapshots

Existing handoff docs:

- [alfred-checkpoint-2026-04-30.md](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/docs/alfred-checkpoint-2026-04-30.md)
- [alfred-checkpoint-2026-04-30-2.md](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/docs/alfred-checkpoint-2026-04-30-2.md)
- [alfred-checkpoint-2026-04-30-3.md](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/docs/alfred-checkpoint-2026-04-30-3.md)
- [alfred-checkpoint-2026-05-02.md](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/docs/alfred-checkpoint-2026-05-02.md)

Existing snapshot archives:

- [alfred-checkpoint-2026-04-30.tgz](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/snapshots/alfred-checkpoint-2026-04-30.tgz)
- [alfred-checkpoint-2026-04-30-2.tgz](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/snapshots/alfred-checkpoint-2026-04-30-2.tgz)
- [alfred-checkpoint-2026-04-30-3.tgz](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/snapshots/alfred-checkpoint-2026-04-30-3.tgz)
- [alfred-checkpoint-2026-05-02.tgz](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/snapshots/alfred-checkpoint-2026-05-02.tgz)

## Best Next-Chat Starting Point

If a new chat starts from here, the best file to begin from is:

- [alfred-full-handoff-2026-04-30.md](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/docs/alfred-full-handoff-2026-04-30.md)

Then optionally cross-reference:

- [alfred-checkpoint-2026-04-30-3.md](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/docs/alfred-checkpoint-2026-04-30-3.md)
- [alfred-validation-process.md](/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo/docs/alfred-validation-process.md)

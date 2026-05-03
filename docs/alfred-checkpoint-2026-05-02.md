# Alfred Checkpoint 2026-05-02 (Touchscreen Pivot Checkpoint)

This file is the first handoff checkpoint after Alfred pivoted away from the e-paper reader build and into a touch-first AI companion. It captures the point where the Raspberry Pi touch hardware is healthy, the local voice loop works, Alfred launches from the Pi desktop into Chromium, and the UI has been reshaped into a toy-like Home / Chat / Settings / Health flow.

Important note:

- this file is the first touch pivot checkpoint
- the newer voice streaming / performance checkpoint is `docs/alfred-checkpoint-2026-05-02-2.md`

## Resume Prompt

If you open a new Codex tab, use something like:

`Continue Alfred from docs/alfred-checkpoint-2026-05-02.md. Alfred is now a Raspberry Pi + Hailo touchscreen AI companion with a Freenove touch display, desktop launcher, local voice loop, diagnostics screens, and a toy-like home UI.`

## Current Milestone

Alfred now works as a touch-first local companion rather than an e-reader prototype:

- Freenove `4.3"` DSI touchscreen is connected and working
- touch input works on the Pi
- Raspberry Pi 5, fan, thermals, mic, speaker, and Hailo hardware have been health-checked
- `hailo-ollama` + `qwen3:1.7b` is reachable locally
- `whisper.cpp` STT works
- `piper` TTS works
- Alfred touch backend works through FastAPI + Chromium
- desktop launcher works, so the user does not need to type the URL on the Pi
- voice round-trip works from the touch UI
- typed chat works from the dedicated Chat screen
- diagnostics and recovery controls work
- the UI has been reworked into a simpler, more toy-like structure

This checkpoint represents a real product-direction change:

- the old knob + Waveshare reader stack is no longer the mainline experience
- the active product is now the touch companion UI

## Updated Hardware And OS

Confirmed current hardware:

- Raspberry Pi 5 `8GB`
- Raspberry Pi Active Cooler
- Raspberry Pi AI HAT+ 2
- Freenove `4.3"` touchscreen monitor
- USB microphone
- USB speaker
- Raspberry Pi OS 64-bit

Current observed device details from health checks:

- display path: DSI display detected at `800x480`
- touch controller: `ft5x06`
- microphone ALSA device: `plughw:3,0`
- speaker ALSA device: `plughw:2,0`
- Hailo kernel path: `hailo1x_pci`
- Hailo device node: `/dev/h1x-0`

## Product Direction Now

Alfred is no longer centered around:

- e-paper
- rotary encoder
- book/PDF reader

Alfred is now centered around:

- local AI conversation
- touch interaction
- animated personality
- fast device bring-up and easy recovery

The current UX model is:

### Home

- animated Alfred face takes most of the screen
- one large round mic button at the bottom
- small status badge at the top
- chat icon opens full chat history
- gear icon opens settings
- short subtitle line under Alfred shows the current moment only
- `Stop voice` appears only while Alfred is actively speaking

### Chat

- full-screen chat history
- typed input lives here
- back button returns to Home

### Settings

- full-screen settings page
- voice replies toggle
- current model display
- health entry point
- restart backend
- reset memory

### Health

- full-screen diagnostics page
- backend, model, STT, TTS, mic, and speaker summary
- last issue summary
- speaker test
- microphone test

## What Works Right Now

### Touch Alfred App

- local FastAPI backend in `alfred_touch.py`
- local Chromium app-mode launcher via desktop icon
- `Home`, `Chat`, `Settings`, and `Health` screens all render
- round mic button starts and stops recording
- Home is now voice-first and uncluttered
- typed chat is intentionally moved off Home into the Chat screen

### Voice Loop

- mic permission flow works
- push-to-talk style tap recording works in the browser
- upload to `/api/transcribe` works
- `whisper.cpp` transcription works
- local chat response works through Hailo
- browser playback of generated Piper WAV files works
- `Stop voice` can interrupt browser playback while Alfred is speaking

### Recovery / Diagnostics

- `Reset memory` clears Alfred’s recent conversation context
- `Restart backend` works from the UI
- `Speaker test` works
- `Microphone test` works and reports what Alfred heard
- `Health` view shows current readiness and the last known issue

### Launcher / Local Use

- `Alfred Touch` desktop launcher exists on the Pi
- launcher starts the backend if needed
- launcher opens Chromium directly to Alfred
- user does not need to manually type `http://127.0.0.1:8081/`

## Important Working Commands

### Touch setup on the Pi

```bash
cd /home/piadmin/be-more-hailo
./setup_alfred_touch.sh
```

### Hardware health check

```bash
cd /home/piadmin/be-more-hailo
./healthcheck_alfred_touch.sh
```

Optional fuller audio check:

```bash
cd /home/piadmin/be-more-hailo
ALFRED_ARECORD_DEVICE=plughw:3,0 \
ALFRED_APLAY_DEVICE=plughw:2,0 \
./healthcheck_alfred_touch.sh --audio-test
```

### Software health checks

```bash
cd /home/piadmin/be-more-hailo
./healthcheck_alfred_software.sh --mock-only
./healthcheck_alfred_software.sh --live
```

### Start Alfred touch backend directly

```bash
cd /home/piadmin/be-more-hailo
./start_alfred_touch.sh
```

### Launch Alfred touch in Chromium

```bash
cd /home/piadmin/be-more-hailo
./launch_alfred_touch.sh
```

In normal use on the Pi, the user can just tap:

- `Alfred Touch`

### Check model server

```bash
curl http://127.0.0.1:8000/api/tags
```

If needed:

```bash
hailo-ollama serve
```

### True Alfred restart

Closing Chromium is only a UI relaunch, not a true backend restart.

For a full Alfred restart:

```bash
ssh piadmin@local-llm-pi.local 'pkill -f "uvicorn alfred_touch:app" || true; pkill -f chromium || true'
```

Then relaunch Alfred from the Pi desktop icon.

## Current Runtime Architecture

The active touch path is now:

- `alfred_touch.py`
- `templates/alfred_touch.html`
- `static/alfred_touch.css`
- `static/alfred_touch.js`
- `start_alfred_touch.sh`
- `launch_alfred_touch.sh`
- `install_alfred_touch_launcher.sh`
- `setup_alfred_touch.sh`
- `healthcheck_alfred_touch.sh`
- `healthcheck_alfred_software.sh`

The Alfred backend logic still reuses:

- `alfred/chat.py`
- `alfred/audio.py`
- `alfred/memory.py`
- `alfred/config.py`

The older e-paper / knob / reader modules still exist in the repo, but they are now legacy reference material rather than the main runtime path.

## Current Quality State

This touch build is now beyond “it technically opens” and into a usable local prototype:

- hardware is healthy
- launcher path is usable
- software stack is healthy
- voice round-trip works
- typed chat works
- diagnostics work
- Home screen is much closer to the intended product feel

The biggest remaining work is now UI/UX polish and product behavior, not basic bring-up.

## Known Operational Quirks

### Touch Alfred is voice-first on Home

Typed input no longer lives on Home. It only lives in the Chat screen by design.

### `Stop voice` is intentionally temporary

It only appears while Alfred is actively speaking. It is not meant to be a permanent settings action.

### Model selection is only a placeholder right now

Settings shows the current model, but there is no real model switcher yet.

### Health issue display is summary-only

`Last issue` is useful, but there is no full in-app log viewer yet.

### Boot automation is not the focus yet

The current path is launcher-first, not appliance boot. The user explicitly deferred `systemd` / kiosk boot for later so debugging stays easier.

### Old handoff docs are now historically useful, not current product truth

They describe the e-paper reader era accurately, but they do not reflect the new touch product direction.

## Current Next Step

The next high-value passes are likely:

1. more touch UI polish
   - animation feel
   - spacing
   - icon quality
   - transitions between screens
2. better conversation UX
   - improve social tone
   - reduce awkward carryover between turns
   - make failure messages friendlier
3. health / recovery depth
   - richer issue reporting
   - maybe log viewing
4. later appliance work
   - boot flow
   - kiosk/autostart
   - exit and re-enter flows

## Files Most Relevant Now

- `alfred_touch.py`
- `static/alfred_touch.css`
- `static/alfred_touch.js`
- `templates/alfred_touch.html`
- `launch_alfred_touch.sh`
- `start_alfred_touch.sh`
- `install_alfred_touch_launcher.sh`
- `setup_alfred_touch.sh`
- `healthcheck_alfred_touch.sh`
- `healthcheck_alfred_software.sh`
- `alfred/chat.py`
- `alfred/audio.py`
- `alfred/memory.py`
- `alfred/config.py`

## Snapshot Pairing

This checkpoint should be paired with:

- `snapshots/alfred-checkpoint-2026-05-02.tgz`
- `snapshots/alfred-checkpoint-2026-05-02.sha256`

If the thread context disappears, this file plus that archive should be enough to continue from the current touch-first Alfred state.

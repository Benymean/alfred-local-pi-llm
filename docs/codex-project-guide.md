# Alfred Touch Project Guide

## Overview

Alfred Touch is a local, voice-first companion chatbot for a Raspberry Pi with a touchscreen display. It records speech in the browser, transcribes audio with `whisper.cpp`, sends prompts to a local Ollama-compatible LLM endpoint, and streams spoken replies back with Piper.

This repository is the clean standalone project for Alfred Touch. It replaces the older mixed-purpose `be-more-hailo` workspace as the source of truth for future Codex work.

## Source Of Truth

- GitHub repo: `https://github.com/Benymean/alfred-local-pi-llm`
- Clean local Mac repo: `/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/alfred-local-pi-llm`
- Old local archive/reference repo: `/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo`

For new work, use the clean `alfred-local-pi-llm` repo. Treat the old `be-more-hailo` folder as historical reference only.

## What Is In Git

Tracked source code:

- `alfred/` shared chat, config, memory, and STT logic
- `alfred_touch_app/` FastAPI touch UI package
- `docs/` project notes, checkpoints, and this guide
- launcher/setup/healthcheck shell scripts
- `requirements.txt`
- `README.md`

Not tracked in Git:

- `piper/`
- `models/`
- `whisper.cpp/`
- `venv/`
- `.alfred-audio/`
- `.alfred-state/`
- `snapshots/`

Those directories are runtime assets, caches, or local-only artifacts and should stay out of the public repo.

## Repository Layout

```text
alfred-local-pi-llm/
├── alfred/
│   ├── audio.py
│   ├── chat.py
│   ├── chat_backends.py
│   ├── chat_engine.py
│   ├── chat_runtime.py
│   ├── chat_text.py
│   ├── chat_types.py
│   ├── config.py
│   └── memory.py
├── alfred_touch.py
├── alfred_touch_app/
│   ├── api_models.py
│   ├── assets/favicon.png
│   ├── paths.py
│   ├── service.py
│   ├── static/alfred_touch.css
│   ├── static/alfred_touch.js
│   ├── streaming.py
│   ├── templates/alfred_touch.html
│   ├── tts.py
│   └── web.py
├── docs/
├── scripts/setup_alfred_audio.sh
├── healthcheck_alfred_touch.sh
├── healthcheck_alfred_software.sh
├── install_alfred_touch_launcher.sh
├── launch_alfred_touch.sh
├── setup_alfred_touch.sh
└── start_alfred_touch.sh
```

## Runtime Architecture

1. The user talks through the browser UI on the Pi touchscreen.
2. The browser records audio and uploads a `webm` blob to Alfred.
3. `ffmpeg` converts that upload to a Whisper-friendly WAV file.
4. `whisper.cpp` transcribes the audio.
5. Alfred sends the text prompt to the local LLM endpoint.
6. The response streams back in chunks.
7. Piper synthesizes reply audio chunk-by-chunk.
8. The browser plays the spoken reply and shows the text transcript.

## Validated Pi Settings

These settings were validated on the working Pi deployment and are now the default shell exports in `start_alfred_touch.sh`:

```bash
ALFRED_ARECORD_DEVICE=plughw:3,0
ALFRED_APLAY_DEVICE=plughw:2,0
ALFRED_WHISPER_MODE=fast
```

Current tuned reply settings in the launcher:

```bash
ALFRED_LLM_NUM_PREDICT=112
ALFRED_VOICE_LLM_NUM_PREDICT=80
ALFRED_VOICE_DETAIL_LLM_NUM_PREDICT=128
ALFRED_LLM_NUM_CTX=2048
ALFRED_LLM_TEMPERATURE=0.35
ALFRED_VOICE_REPLY_MAX_WORDS=60
ALFRED_VOICE_DETAIL_MAX_WORDS=100
ALFRED_TTS_TEMPO=0.94
```

If hardware changes, prefer overriding environment variables rather than hardcoding new device names across the codebase.

## Setup On A New Pi

Clone and bootstrap:

```bash
git clone https://github.com/Benymean/alfred-local-pi-llm.git
cd alfred-local-pi-llm
chmod +x *.sh scripts/setup_alfred_audio.sh
./setup_alfred_touch.sh
```

That setup flow:

- installs required system packages
- creates the Python virtual environment
- installs Python dependencies
- installs or verifies Piper and Whisper assets
- installs the Alfred Touch launcher

## Health Checks

Hardware/audio check:

```bash
./healthcheck_alfred_touch.sh --audio-test
```

Mock backend check:

```bash
./healthcheck_alfred_software.sh --mock-only
```

Live backend check:

```bash
./healthcheck_alfred_software.sh --live
```

## Running Alfred

Start the backend:

```bash
./start_alfred_touch.sh
```

Open the touch UI through the launcher:

```bash
./launch_alfred_touch.sh
```

Reinstall the desktop shortcut after moving or renaming the repo:

```bash
./install_alfred_touch_launcher.sh
```

## Known Operational Caveats

### GitHub web uploads strip executable bits

If shell scripts are uploaded through the GitHub web UI, they may lose executable permissions. If a fresh clone has non-executable scripts, run:

```bash
chmod +x *.sh scripts/setup_alfred_audio.sh
```

### Moving the repo can break `whisper.cpp/build`

`whisper.cpp` build artifacts can retain absolute-path assumptions. If the repo is moved or renamed and STT starts failing, rebuild Whisper in place:

```bash
rm -rf whisper.cpp/build
./scripts/setup_alfred_audio.sh
```

### `.gitignore` does not remove files already tracked elsewhere

The clean repo now ignores runtime assets, but old clones may still show previously tracked files until they are explicitly removed from version control history in those clones.

### The old `be-more-hailo` repo is not the future source of truth

It still contains useful historical context, but it has older git history and was the workspace used during the cleanup transition. New Codex work should happen in the clean repo only.

## Recommended Codex Workflow

When starting a new Codex project:

1. Open the clean repo:

   `/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/alfred-local-pi-llm`

2. Treat GitHub `main` on `Benymean/alfred-local-pi-llm` as the canonical base.
3. Make feature changes there, not in the archived `be-more-hailo` folder.
4. If testing on the Pi, sync only the source changes and preserve runtime assets on-device.
5. Keep large runtime dependencies off GitHub.

## Pi Naming Cleanup

For consistency, the Pi project folder should also be renamed from `be-more-hailo` to `alfred-local-pi-llm`.

Safe cutover steps on the Pi:

```bash
pkill -f "uvicorn alfred_touch:app" || true
pkill -f chromium || true

mkdir -p /home/piadmin/alfred-archive/2026-05-03
mv /home/piadmin/be-more-hailo-backup-2026-05-03.tgz /home/piadmin/alfred-archive/2026-05-03/ 2>/dev/null || true
mv /home/piadmin/be-more-hailo-prev /home/piadmin/alfred-archive/2026-05-03/ 2>/dev/null || true
mv /home/piadmin/be-more-hailo/snapshots /home/piadmin/alfred-archive/2026-05-03/project-snapshots 2>/dev/null || true

cd /home/piadmin
mv be-more-hailo alfred-local-pi-llm

cd /home/piadmin/alfred-local-pi-llm
./install_alfred_touch_launcher.sh
chmod +x *.sh scripts/setup_alfred_audio.sh
```

After the rename, test Alfred from the desktop shortcut again.

## Local Archive Recommendation

Do not continue active work in the old Mac folder:

`/Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo`

If you want to keep it, archive it. If you do not need it after verification, you can later compress or move it out of the main project area.

## Current Status Summary

As of this guide:

- the clean GitHub repo exists and is usable
- the clean Mac clone exists and is the preferred repo for future work
- the Pi runtime was repaired and validated
- the remaining optimization work is product-level, not deployment-level

That means Alfred is now in a stable enough state to begin a fresh Codex project from the clean standalone repo.

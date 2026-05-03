# Alfred Touch

Alfred Touch is a local, voice-first companion chatbot for a Raspberry Pi touchscreen setup. It records audio in the browser, transcribes with `whisper.cpp`, sends the prompt to a local chat model, and streams spoken replies back with Piper.

The repo is now trimmed around the Alfred Touch path only. Older BMO, e-paper, reader, and wake-word experiments are not part of the active app anymore.

## What It Uses

- FastAPI for the local web app
- `whisper.cpp` for speech-to-text
- Piper for text-to-speech
- An Ollama-compatible local chat endpoint
- A Raspberry Pi browser launcher for the touch UI

## Repo Layout

```text
alfred-local-pi-llm/
├── alfred/                         # Shared touch runtime code
│   ├── audio.py
│   ├── chat.py
│   ├── chat_backends.py
│   ├── chat_engine.py
│   ├── chat_runtime.py
│   ├── chat_text.py
│   ├── chat_types.py
│   ├── config.py
│   └── memory.py
├── alfred_touch.py                 # Uvicorn compatibility entrypoint
├── alfred_touch_app/               # Touch web app package
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
├── docs/                           # Validation and project notes
├── scripts/bootstrap_alfred_touch.sh
├── scripts/alfred_touch_env.sh
├── scripts/setup_alfred_audio.sh   # Piper + Whisper setup
├── healthcheck_alfred_touch.sh     # Pi hardware/audio checks
├── healthcheck_alfred_software.sh  # Backend and HTTP smoke checks
├── install_alfred_touch_launcher.sh
├── launch_alfred_touch.sh
├── requirements.txt
├── setup_alfred_touch.sh
└── start_alfred_touch.sh
```

## Setup

On the Pi:

```bash
git clone <your-repo-url> alfred-local-pi-llm
cd alfred-local-pi-llm
chmod +x *.sh scripts/setup_alfred_audio.sh
./setup_alfred_touch.sh
```

That setup path:

- installs system packages
- creates the Python virtual environment
- installs Python dependencies
- installs Piper, Whisper, and local speech models
- installs the Alfred Touch desktop launcher

## Validate

Hardware and audio:

```bash
./healthcheck_alfred_touch.sh --audio-test
```

Mock backend:

```bash
./healthcheck_alfred_software.sh --mock-only
```

Live local model:

```bash
./healthcheck_alfred_software.sh --live
```

Model behavior benchmark:

```bash
./scripts/eval_alfred_model.py --backend live --suite validation --warmup 1 --label pi-baseline
```

See `docs/alfred-eval-benchmark.md` for the JSONL trace fields and tuning workflow.

## Run

Start the backend directly:

```bash
./start_alfred_touch.sh
```

Or use the desktop launcher:

```bash
./launch_alfred_touch.sh
```

To install the desktop shortcut again:

```bash
./install_alfred_touch_launcher.sh
```

## Automatic Bootstrap

Before Alfred launches, it now runs a lightweight bootstrap step that:

- checks Python runtime imports
- repairs or rebuilds `whisper.cpp` if the binary is broken after a repo move
- restores missing Piper / Whisper runtime assets by calling `scripts/setup_alfred_audio.sh`
- starts a local `hailo-ollama` or `ollama` server if `ALFRED_LLM_URL` points at localhost and the server is offline
- verifies that the configured model is listed by the local model server

This is meant to remove the most common Pi caveats from normal launching. In the typical case, tapping the Alfred desktop icon should now be enough.

## Runtime Notes

- UI assets now live inside `alfred_touch_app/`, not top-level `static/` or `templates/`.
- Local runtime state is kept in dot-directories like `.alfred-audio/` and `.alfred-state/`.
- The active memory file defaults to `.alfred-state/alfred_memory_touch.json`.
- Large local assets like `piper/`, `models/`, and `whisper.cpp/` are expected on disk but should stay out of Git.
- The validated Pi defaults currently use `ALFRED_ARECORD_DEVICE=plughw:3,0`, `ALFRED_APLAY_DEVICE=plughw:2,0`, and `ALFRED_WHISPER_MODE=fast`.
- If your Pi uses different audio hardware, override those environment variables instead of editing the code path elsewhere.
- Model-server startup logs are written to `.alfred-model-server.log`, and launcher/backend bootstrap output is appended to `.alfred-touch-launcher.log`.
- If you want Alfred to automatically pull a missing local model, set `ALFRED_AUTO_PULL_MODEL=1` before launching.
- For a fuller handoff and future Codex starting point, see `docs/codex-project-guide.md`.

## Rollback

Keep rollback archives and one-off Pi backups outside the public repo, for example under a local folder like `~/alfred-archive/`.

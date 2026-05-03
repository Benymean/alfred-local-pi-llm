# Alfred Checkpoint 2026-05-02-2 (Touch Voice Performance Checkpoint)

This checkpoint captures Alfred after the touchscreen pivot matured into a real local voice companion and after the first serious round of model-speed, streaming, and reply-quality tuning.

Newer checkpoint:

- `docs/alfred-checkpoint-2026-05-03.md`

It is the right resume point if you want the current `touch UI + voice loop + streaming browser TTS + adaptive voice depth` build rather than the earlier e-paper or pre-streaming touchscreen state.

## Resume Prompt

If you open a new Codex tab, use something like:

`Continue Alfred from docs/alfred-checkpoint-2026-05-02-2.md. Alfred is now a Raspberry Pi + Hailo touchscreen AI companion with a Freenove 4.3 inch display, desktop launcher, streaming sentence-based voice replies, adaptive voice depth, diagnostics screens, and measured STT/LLM/TTS timings in the backend log.`

## Current Milestone

Alfred is now a working touch-first local companion with:

- toy-like `Home / Chat / Settings / Health` UI
- working desktop launcher into Chromium
- working voice round-trip
- working typed chat
- browser-side audio interruption
- backend restart and memory reset from the UI
- Hailo-backed local LLM replies
- terminal timing instrumentation for STT, LLM, and TTS
- first-pass streamed voice replies that synthesize sentence chunks as they become available
- adaptive voice depth so factual or reflective spoken questions can be fuller than greetings

This is no longer a prototype where the major unknown is “can it work at all?”  
The main open work is now about:

- reducing perceived latency
- improving answer quality per second
- deciding where to trade speed against richness

## Current Hardware / Runtime Baseline

Confirmed working baseline:

- Raspberry Pi 5
- Raspberry Pi Active Cooler
- Raspberry Pi AI HAT+ 2
- Freenove `4.3"` touchscreen
- USB microphone
- USB speaker
- Raspberry Pi OS 64-bit
- Hailo device path `/dev/h1x-0`
- `hailo-ollama` serving on `0.0.0.0:8000`
- `qwen3:1.7b`
- `whisper.cpp`
- `piper`

Important note:

- Alfred UI restart does **not** restart `hailo-ollama`
- `Restart backend` in Alfred Settings **is** a true Alfred backend restart
- closing/reopening Chromium is only a UI relaunch

## Current Product UX

### Home

- Alfred face dominates the screen
- round mic button at the bottom
- chat icon opens full chat history
- gear icon opens settings
- short subtitle line only
- `Stop voice` appears while Alfred is speaking or streaming voice output

### Chat

- full-screen history
- typed input lives here
- typed chat remains stable and non-streaming

### Settings

- voice replies toggle
- current model display
- restart backend
- reset memory
- entry into Health

### Health

- backend/model/STT/TTS summary
- mic and speaker state
- last known issue
- speaker test
- microphone test

## Current Runtime Architecture

Main active path:

- `alfred_touch.py`
- `templates/alfred_touch.html`
- `static/alfred_touch.css`
- `static/alfred_touch.js`
- `start_alfred_touch.sh`
- `launch_alfred_touch.sh`
- `install_alfred_touch_launcher.sh`

Main backend logic reused by the touch app:

- `alfred/chat.py`
- `alfred/audio.py`
- `alfred/memory.py`
- `alfred/config.py`

Legacy modules still exist but are not the mainline experience:

- `alfred/display.py`
- `alfred/input.py`
- `alfred/reader.py`
- older e-paper / knob paths in `alfred/app.py`

## What Works Right Now

### Core Interaction

- tap mic to record
- browser uploads audio to `/api/transcribe`
- whisper transcribes locally
- Alfred sends the prompt to Hailo
- voice replies can stream sentence-by-sentence
- browser queues and plays generated Piper WAV chunks
- `Stop voice` interrupts both current playback and queued sentence audio

### Diagnostics / Recovery

- `Reset memory` clears recent conversation state
- `Restart backend` works from Settings
- `Speaker test` works
- `Microphone test` works
- `Health` view reflects backend and model readiness
- backend logs include stage timing details

### Prompt / Reply Behavior

- typed chat no longer drifts back to the previous turn
- voice questions can now be slightly more detailed when Alfred detects factual or reflective prompts
- prompts like `Hey Alfred, ...` are normalized before reaching the model
- leading reply labels like `Alfred:` are stripped from both visible replies and spoken audio

## Current Performance Instrumentation

The backend log now exposes:

- STT stage start and completion
- Whisper split into `ffmpeg` conversion time vs `whisper.cpp` inference time
- chat start with turn id, prompt length, response mode, and selected `num_predict`
- LLM completion time
- streamed LLM first visible chunk time
- first complete sentence time
- first audio chunk time
- total streamed request time
- end-to-end time from recording start when available
- Ollama/Hailo response metrics when provided by the server

Log path to tail from the Mac:

```bash
ssh piadmin@local-llm-pi.local 'tail -f /home/piadmin/be-more-hailo/.alfred-touch-launcher.log'
```

## Current Observed Bottlenecks

Representative recent measurements on the Pi:

- STT total: roughly `4.0s` to `4.9s`
- Whisper inference alone: roughly `3.5s` to `4.7s`
- streamed LLM total: roughly `7.4s` to `9.7s`
- first visible model chunk: roughly `5.2s` on a better turn, `12.1s` on a worse turn
- first full sentence ready: roughly `7.2s` to `14.2s`
- first audio chunk ready: roughly `9.5s` to `16.6s`
- old full TTS path before streaming: roughly `2.3s` to `3.1s`

Interpretation:

- STT is a real fixed-cost bottleneck
- the model is still the biggest reasoning bottleneck
- sentence-streamed TTS works, but the benefit is limited when Alfred’s reply is only one short sentence
- answer richness and speed are now tightly coupled, so Alfred needs smarter heuristics rather than one global “short answer” rule

## Current Speed / Quality Strategy

The current touch launcher defaults favor a balanced middle ground instead of purely shortest possible replies:

```bash
ALFRED_LLM_NUM_PREDICT=80
ALFRED_VOICE_LLM_NUM_PREDICT=56
ALFRED_VOICE_DETAIL_LLM_NUM_PREDICT=88
ALFRED_LLM_NUM_CTX=2048
ALFRED_LLM_TEMPERATURE=0.35
ALFRED_VOICE_REPLY_MAX_WORDS=40
ALFRED_VOICE_REPLY_MAX_SENTENCES=3
ALFRED_VOICE_DETAIL_MAX_WORDS=72
ALFRED_VOICE_DETAIL_MAX_SENTENCES=4
```

Additional current behavior:

- `qwen3` is requested with `/no_think`
- chat payload also tries `think: false`
- voice mode uses less memory context than typed mode
- standalone spoken factual or reflective prompts can bypass older summary baggage

## Important Working Commands

### Start Alfred directly

```bash
cd /home/piadmin/be-more-hailo
./start_alfred_touch.sh
```

### Launch Alfred through the normal desktop-style path

```bash
cd /home/piadmin/be-more-hailo
./launch_alfred_touch.sh
```

### True Alfred restart from Mac

```bash
ssh piadmin@local-llm-pi.local 'pkill -f "uvicorn alfred_touch:app" || true; pkill -f chromium || true'
```

Then relaunch from the Pi desktop icon.

### Check the Hailo model server

```bash
ssh piadmin@local-llm-pi.local 'curl -fsS http://127.0.0.1:8000/api/tags'
```

### Confirm direct chat API behavior

```bash
ssh piadmin@local-llm-pi.local 'curl -s http://127.0.0.1:8000/api/chat -H "Content-Type: application/json" -d '"'"'{"model":"qwen3:1.7b","messages":[{"role":"user","content":"Reply with exactly healthy."}],"stream":false,"think":false}'"'"''
```

### Watch Alfred timing logs

```bash
ssh piadmin@local-llm-pi.local 'tail -f /home/piadmin/be-more-hailo/.alfred-touch-launcher.log'
```

## Files Most Recently Touched For This Milestone

Touch backend and streaming:

- `alfred_touch.py`
- `static/alfred_touch.js`

Model behavior and prompt shaping:

- `alfred/chat.py`
- `alfred/config.py`
- `start_alfred_touch.sh`

Speech cleanup / TTS handling:

- `alfred/audio.py`

## Known Current Quirks

- streamed voice replies currently help most when Alfred has multiple sentences to say; very short answers still feel similar to non-streamed replies
- STT is still slower than ideal for a handheld companion feel
- `model online` only means the model server answers health checks; it does not prove every chat payload will succeed
- `hailo-ollama` can already be running even if manually launching it again prints `Address already in use`
- Hailo/Ollama compatibility with optional fields like `keep_alive` was fragile enough that the current build leaves that disabled by default

## Best Next Optimization Ideas

The best next candidates from this exact point are:

1. `Add a fast STT mode`
Use `tiny.en` as an optional Whisper mode so the user can choose `faster` vs `more accurate`.

2. `Smarter voice depth classifier`
Teach Alfred to distinguish:
- greeting
- factual one-shot
- reflective / opinion
- follow-up continuation

so the token budget matches the real question better.

3. `Optional early spoken acknowledgment`
Bring back a very selective early acknowledgment like `One sec.` only when Alfred predicts the answer will be slow enough to benefit.

4. `Streaming text polish`
Surface a little more of the partial reply text on Home while the stream is in progress.

5. `Sentence TTS batching heuristics`
Allow Alfred to speak after commas or shorter clauses when the model is clearly producing long answers.

## Pi Sync Workflow Reminder

To preserve folder structure when syncing specific files from the Mac, use:

```bash
cd /Users/benymean/Documents/Codex/2026-04-30/i-want-to-connect-you-to/be-more-hailo
rsync -avR path/to/file1 path/to/file2 piadmin@local-llm-pi.local:/home/piadmin/be-more-hailo/
```

Do **not** rsync individual files straight to `/home/piadmin/be-more-hailo/` without `-R` unless you intentionally want them flattened into the repo root.

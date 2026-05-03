# Alfred Checkpoint 2026-05-03 (Fast Whisper + Voice Debug Checkpoint)

This checkpoint captures Alfred after the touch-first companion was pushed further on the voice-performance path:

- `whisper.cpp tiny.en` is now active on the Pi
- early acknowledgment clips are cached
- streamed voice replies log both timings and answer text
- TTS tempo is configurable
- follow-up handling and audience-style prompt handling were improved

This is the right resume point if you want the latest `touch UI + fast Whisper + streamed voice + answer logging` build, rather than the earlier touchscreen checkpoints.

## Resume Prompt

If you open a new Codex tab, use something like:

`Continue Alfred from docs/alfred-checkpoint-2026-05-03.md. Alfred is a Raspberry Pi + Hailo touchscreen AI companion with fast Whisper STT, streamed browser-side voice replies, cached early acknowledgments, diagnostics screens, and answer/timing logs in the backend terminal.`

## Current Milestone

Alfred now has:

- toy-like `Home / Chat / Settings / Health` UI
- working launcher into Chromium
- Hailo-backed local chat replies
- `whisper.cpp tiny.en` active for faster STT
- streamed sentence-based browser audio replies
- cached ack clips like `One moment.` and `Hang on a sec.`
- terminal logging for:
  - STT timing
  - LLM timing
  - TTS timing
  - first visible chunk
  - first sentence
  - first audio
  - first answer audio
  - final answer text

The main open work is no longer “does Alfred work?” but:

- better answer quality for social / audience / motivational prompts
- better speed without losing conversational flow
- smarter classification of which voice prompts deserve more output budget

## Current Hardware / Runtime Baseline

Confirmed baseline:

- Raspberry Pi 5
- Raspberry Pi Active Cooler
- Raspberry Pi AI HAT+ 2
- Freenove `4.3"` touchscreen
- USB microphone
- USB speaker
- Raspberry Pi OS 64-bit
- Hailo device path `/dev/h1x-0`
- `hailo-ollama` on port `8000`
- `qwen3:1.7b`
- `whisper.cpp`
- `piper`

Important notes:

- Alfred backend restart does **not** restart `hailo-ollama`
- closing Chromium is only a UI relaunch
- `Restart backend` in Alfred Settings is a true Alfred backend restart

## Current Voice Performance State

### STT

Recent measured STT times after enabling `ggml-tiny.en.bin`:

- roughly `1.9s` to `2.6s` total
- Whisper inference itself roughly `1.7s` to `2.4s`

This is a major improvement over the earlier `~4s` STT path.

### Streaming Voice

Current streamed voice path now exposes:

- `LLM first visible chunk`
- `first sentence ready`
- `first audio chunk ready`
- `first answer audio chunk ready`
- final `answer: "..."`

This matters because early ack audio can otherwise make Alfred feel faster than the real answer actually is.

### Current Limits

Touch launcher defaults currently are:

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
ALFRED_WHISPER_MODE=fast
ALFRED_TTS_TEMPO=0.94
```

Interpretation:

- ordinary voice prompts get `56` output tokens
- factual / reflective / explicit-detail voice prompts get `88`
- `88` is a speed-quality compromise, not a hard technical maximum

## Known Behavior Right Now

### Good

- STT is noticeably faster
- cached ack phrases now play almost instantly
- logs are much better for debugging
- follow-up prompts like `what about ...` are treated more as contextual follow-ups
- Alfred is less likely to mention the current time/date unless actually asked

### Still Rough

- some streamed replies can still sound a bit segmented
- some ordinary social prompts still fall into the shorter `56` token budget and can end too soon
- audience-style prompts can still sound too self-descriptive if the transcript is awkward
- a tiny model can still drift on vague prompts or motivational copy

## Why Some Replies Drop Mid-Sentence

If a voice reply ends abruptly mid-sentence, the most likely cause is:

- `num_predict` output cap being reached

Not usually:

- context window exhaustion

In practice:

- `num_ctx` problems cause drift, forgetting, or weak follow-ups
- `num_predict` problems cause abrupt stopping

So when you see a response end like:

- `... and be a little`

that is most likely the `56` token voice cap or `88` detailed cap being hit before the model reached a natural stop.

## Current Classification Logic

Alfred currently treats a voice prompt as `detailed` when it looks like:

- a factual question
- a reflective question
- an explicit detail request like `tell me more`, `be detailed`, `go deeper`

Everything else stays in ordinary voice mode unless future heuristics expand it.

That means prompts like:

- `Who made Google happen?`
- `What do you think about life?`

are likely `detailed`, while prompts like:

- `Tell them something motivational.`

can still stay in ordinary voice mode unless their wording triggers a more specific heuristic.

## Current Prompt / Reply Improvements

Already implemented:

- `Hey Alfred, ...` is stripped before model submission
- leading `Alfred:` labels are stripped from text and TTS
- typed messages do not drift back to previous turns
- follow-ups like `what about ...` and `no, I mean ...` now use more recent context
- audience-message prompts now have extra prompt guidance to write a short message for listeners rather than talking about Alfred themself

## Current TTS State

Alfred uses Piper for touch/browser speech.

Current default voice:

- `ALFRED_PIPER_MODEL=piper/bmo.onnx`

Current TTS tempo:

- `ALFRED_TTS_TEMPO=0.94`

Lower values are slower:

- `1.0` = normal
- `0.94` = slightly slower
- `0.90` = more deliberate

Changing Alfred’s voice currently means pointing `ALFRED_PIPER_MODEL` at a different Piper `.onnx` voice model.

## Important Working Commands

### Start Alfred directly

```bash
cd /home/piadmin/be-more-hailo
./start_alfred_touch.sh
```

### Launch Alfred through the desktop path

```bash
cd /home/piadmin/be-more-hailo
./launch_alfred_touch.sh
```

### True Alfred restart from Mac

```bash
ssh piadmin@local-llm-pi.local 'pkill -f "uvicorn alfred_touch:app" || true; pkill -f chromium || true'
```

### Watch answer + timing logs

```bash
ssh piadmin@local-llm-pi.local 'tail -f /home/piadmin/be-more-hailo/.alfred-touch-launcher.log'
```

### Install / refresh Alfred audio assets on the Pi

```bash
ssh piadmin@local-llm-pi.local 'cd /home/piadmin/be-more-hailo && bash ./scripts/setup_alfred_audio.sh'
```

## Most Relevant Files Right Now

Touch runtime:

- `alfred_touch.py`
- `static/alfred_touch.js`
- `templates/alfred_touch.html`
- `static/alfred_touch.css`
- `start_alfred_touch.sh`

Brain / prompt / memory:

- `alfred/chat.py`
- `alfred/memory.py`
- `alfred/config.py`

Audio / setup / diagnostics:

- `alfred/audio.py`
- `scripts/setup_alfred_audio.sh`
- `healthcheck_alfred_touch.sh`
- `healthcheck_alfred_software.sh`

## Recommended Next Priorities

Best next engineering bets:

1. Expand the “detailed voice” classifier to catch audience-message, motivational, and creative prompts.
2. Log `done_reason` from the model so output truncation can be confirmed instead of inferred.
3. Consider raising `ALFRED_VOICE_DETAIL_LLM_NUM_PREDICT` from `88` to `112` if richer spoken answers matter more than a few extra seconds.
4. Add explicit voice-selection support in Settings if you want voice-swapping to be a first-class feature.

## Snapshot

Checkpoint archive:

- `snapshots/alfred-checkpoint-2026-05-03.tgz`
- `snapshots/alfred-checkpoint-2026-05-03.sha256`

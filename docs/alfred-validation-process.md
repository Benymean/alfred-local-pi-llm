# Alfred Validation Process

This document captures the current manual validation process for Alfred on the Raspberry Pi hardware build. It is meant to be reused after major changes to voice, prompting, memory, display, input, or model/runtime behavior.

## Goal

Use this process to answer four questions:

1. Is Alfred stable?
2. Is Alfred understandable and trustworthy?
3. Does Alfred feel pleasant and conversational?
4. Did a recent change make anything worse?

## Test Setup

Run Alfred on the Pi with the current hardware loop:

```bash
cd /home/piadmin/be-more-hailo
ALFRED_DISPLAY_BACKEND=waveshare \
ALFRED_WAVESHARE_LIB_DIR=/home/piadmin/e-Paper/RaspberryPi_JetsonNano/python/lib \
ALFRED_ARECORD_DEVICE=plughw:3,0 \
ALFRED_APLAY_DEVICE=plughw:2,0 \
ALFRED_LLM_MODEL=qwen3:1.7b \
python3 -m alfred --display waveshare --input seesaw --backend live --hardware-audio --fresh-memory
```

Notes:

- Use `--fresh-memory` for clean validation runs unless the test is specifically about long-lived memory behavior.
- Stop Alfred with `Ctrl+C`.
- Record both successful behavior and odd behavior. Small local models often fail in subtle ways before they fail obviously.

## Validation Buckets

### 1. Ten factual questions

Use these to test normal answer quality, latency, and whether the model stays concise.

- `What is the capital of Japan?`
- `Explain photosynthesis in one sentence.`
- `How many legs does a spider have?`
- `What is the boiling point of water in Celsius?`
- `Who wrote Romeo and Juliet?`
- `What planet is known as the Red Planet?`
- `What is 12 times 8?`
- `Why do we have seasons?`
- `What is the difference between a lake and an ocean?`
- `Give me three examples of renewable energy.`

Expected behavior:

- answers should be short, correct, and calm
- no rambling
- no obvious hallucination
- no current-info fallback unless the question really needs it

Current observation from this run:

- Alfred answered all correctly except `What planet is known as the Red Planet?`
- That one incorrectly triggered the current-info fallback
- This should be treated as a bug or edge-case to reproduce later

### 2. Five casual/social questions

These test whether Alfred feels like a companion instead of a generic assistant.

- `Good morning, Alfred. How are you?`
- `Tell me something interesting.`
- `I’m feeling tired. What should I do?`
- `Can you give me a quick pep talk?`
- `What should I ask you next?`

Expected behavior:

- replies should feel warm and natural
- Alfred should not sound like a generic helper bot
- Alfred should not unnecessarily say `One sec.` for quick social questions if the response is already fast
- memory should not bleed awkwardly from previous turns

Current observation from this run:

- this category clearly needs more work
- `Tell me something interesting.` produced a weak generic answer
- `I’m feeling tired. What should I do?` included stiff helper-bot phrasing like `I'm here to help`
- `Can you give me a quick pep talk?` retained context from the previous tiredness question
- `What should I ask you next?` produced another stale support-style reply instead of a playful or curious one

Interpretation:

- Alfred still needs a stronger distinction between social chat and factual question handling
- Alfred’s short-answer voice mode is functional, but not yet polished

Current optimization direction:

- standalone social prompts should use less carryover memory than factual prompts
- Alfred should avoid generic helper-bot phrases like `I'm here to help` unless they are truly appropriate
- `Tell me something interesting` should trigger a concrete interesting fact or observation
- `What should I ask you next?` should suggest one or two good next questions, not repeat emotional reassurance
- social prompts should be less likely to trigger the `One sec.` acknowledgment unless the reply is genuinely slow
- some common social prompts may be handled by a small companion layer instead of relying entirely on the local model

### 3. Five current-info questions

These are important for testing hallucination and honesty.

- `What’s the weather today?`
- `Who is the current Prime Minister of Australia?`
- `What are the latest AI news headlines?`
- `What movies are playing this week?`
- `What is the current price of Bitcoin?`

Expected behavior:

- Alfred should not hallucinate
- Alfred should clearly say it cannot verify current facts from here

Current observation from this run:

- fallback triggering is working correctly here

### 4. Five nonsense or malformed questions

These test robustness and tone.

- `What is the banana of yesterday?`
- `Can you blue the faster window?`
- `Tell me why seven is upside-down.`
- `What happens if a toaster dreams?`
- `Flurple the moon spoon, please.`

Expected behavior:

- Alfred should ask for clarification or give a playful but controlled answer
- Alfred should not crash, hang, or ramble

Current observation from this run:

- `What is the banana of yesterday?` -> acceptable uncertainty
- `Can you blue the faster window?` -> acceptable uncertainty
- `Tell me why seven is upside-down.` -> too confident and odd
- `What happens if a toaster dreams?` -> acceptable playful short reply
- `Flurple the moon spoon, please.` -> acceptable uncertainty

Interpretation:

- nonsense handling is mostly stable
- Alfred still sometimes makes up a weird explanation instead of stepping back

### 5. Empty or weak audio

Use very short, silent, or failed recordings to test recovery.

Expected behavior:

- no crash
- Alfred should say something like `I didn’t catch enough audio` or `I didn’t hear anything that time`

Current observation from this run:

- empty-input recovery is functionally okay

## What To Record During Each Validation Run

For each run, capture:

- Alfred launch command
- whether `--fresh-memory` was used
- model name
- major good behaviors
- major bad behaviors
- any Hailo server errors
- any STT mistakes that changed the meaning of the question
- whether failure was:
  - model quality
  - prompt quality
  - memory bleed
  - runtime/server issue
  - UI/input issue

## Current Priority Based On Latest Results

Do not prioritize visuals first.

The next optimization priority should be:

1. social/casual response quality
2. memory boundaries between turns so Alfred does not drag stale emotional context forward awkwardly
3. current-info classifier edge-case review, especially the `Red Planet` false positive
4. suppress or reduce unnecessary `One sec.` acknowledgments for fast/easy social replies
5. only after that, run a longer soak test again

## Recommended Next Pass

The next pass should focus on `response behavior`, not new hardware features:

- improve social question prompting
- reduce generic helper-bot phrases like `I'm here to help`
- make Alfred more curious and natural on open-ended social prompts
- tighten memory carryover so adjacent mood-based answers do not bleed into unrelated follow-ups
- keep current-info fallback behavior intact
- use deterministic companion responses for a few very common social prompts if the tiny model continues to underperform

After that pass, rerun this entire validation process.

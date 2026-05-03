# Alfred Eval Benchmark

Use `scripts/eval_alfred_model.py` when tuning Alfred's local model behavior. It runs a repeatable prompt suite through the same route classifier, prompt shaping, memory policy, and streaming model backend used by Alfred Touch.

## Recommended Pi Run

From the Alfred repo on the Pi:

```bash
cd /home/piadmin/alfred-local-pi-llm
./scripts/eval_alfred_model.py --backend live --suite validation --warmup 1 --label pi-baseline
```

Outputs are written under `.alfred-state/evals/`:

- `*.jsonl` contains one detailed trace per prompt.
- `*.md` contains a quick human-readable report.
- `*.meta.json` contains run settings and summary stats.

The eval script applies the same default tuning values as `scripts/alfred_touch_env.sh` when environment variables are not already set, so direct benchmark runs match Alfred Touch launcher behavior.

## What It Logs

For each prompt, the JSONL trace records:

- prompt category and text
- selected route, such as `factual`, `casual`, `reflective`, `followup`, or `current_info`
- full request profile flags
- prepared user message and full model messages, unless `--no-messages` is used
- `num_predict`
- memory turns before and after the prompt
- prompt size in words/chars
- first visible chunk timing
- first sentence timing
- total response timing
- stream chunk and sentence counts
- final answer text
- backend metrics from Ollama/Hailo, including `done_reason`
- warnings such as `hit_num_predict_limit`, `answer_does_not_end_cleanly`, or current-info route mismatches

## Useful Variants

Quick smoke test:

```bash
./scripts/eval_alfred_model.py --backend live --suite quick --warmup 1 --label quick-check
```

Generalization test with different prompts:

```bash
./scripts/eval_alfred_model.py --backend live --suite generalization --warmup 1 --label generalization-check
```

Fresh rotating prompt sample:

```bash
./scripts/eval_alfred_model.py --backend live --suite rotation --sample 24 --random-seed --warmup 1 --label rotation-sample
```

Raw model behavior without deterministic fast replies:

```bash
./scripts/eval_alfred_model.py --backend live --suite generalization --raw-model --warmup 1 --label raw-generalization
```

Fresh raw-model sample for prompt tuning:

```bash
./scripts/eval_alfred_model.py --backend live --suite rotation --raw-model --sample 24 --random-seed --warmup 1 --label raw-rotation
```

Mock backend test without the model server:

```bash
./scripts/eval_alfred_model.py --backend mock --suite quick --label mock-check
```

Test only social prompts:

```bash
./scripts/eval_alfred_model.py --backend live --suite validation --category social --warmup 1 --label social-pass
```

Use fresh memory for every prompt:

```bash
./scripts/eval_alfred_model.py --backend live --suite validation --memory-mode isolated --warmup 1 --label isolated-baseline
```

Run custom prompts from a text file:

```bash
./scripts/eval_alfred_model.py --backend live --suite none --prompts-file prompts.txt --warmup 1 --label custom
```

Plain text prompt files accept either one prompt per line or tab-separated `category<TAB>prompt` lines.

## How To Read Results

Start with the Markdown report:

- High `First Sentence` means the LLM is slow to produce speakable text.
- High `Total` with normal first sentence usually means generation is too long.
- `done=length` means the reply hit `num_predict` and may have been cut off.
- `answer_does_not_end_cleanly` usually means the token budget or prompt ending instruction needs work.
- `unexpected_current_info_route` means Alfred refused a stable question as if it needed live lookup.
- Large prompt word counts usually point to memory or prompt-size overhead.

Then open the JSONL trace for a bad row and inspect `messages`, `prepared_user_text`, `profile`, and `backend_metrics`.

Use `--raw-model` when you want to measure whether prompt changes made the local model itself better, not whether Alfred's product-layer fast replies handled a prompt.

## Avoiding Overfitting

Use the suites differently:

- `validation`: fixed regression test. Good for comparing against old runs, but not enough for model-quality claims.
- `generalization`: fixed held-out set. Good for checking whether changes transfer to prompts that were not in the original validation list.
- `rotation`: larger prompt bank. Use `--sample` and `--random-seed` so each tuning pass sees a fresh subset.
- `--prompts-file`: best for true blind tests. Keep a local file of prompts Alfred has never been tuned against.

Recommended loop:

1. Tune against one raw rotating sample.
2. Check the fixed `validation` suite for regressions.
3. Check `generalization` or a private prompt file before accepting the change.
4. Do not add hardcoded factual answers just to improve a benchmark score.

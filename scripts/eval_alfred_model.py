#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import datetime as dt
import json
import os
from pathlib import Path
import random
import re
import statistics
import sys
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from alfred.chat_backends import HailoChatBackend, MockChatBackend
from alfred.chat_engine import AlfredChatEngine
from alfred.chat_runtime import _build_system_prompt, _num_predict_for_profile, _prepare_user_message
from alfred.chat_runtime import _deterministic_reply
from alfred.chat_text import _reply_ends_cleanly
from alfred.config import AlfredSettings
from alfred.memory import AlfredMemory


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    category: str
    prompt: str
    notes: str = ""


VALIDATION_CASES: tuple[EvalCase, ...] = (
    EvalCase("factual_01", "factual", "What is the capital of Japan?"),
    EvalCase("factual_02", "factual", "Explain photosynthesis in one sentence."),
    EvalCase("factual_03", "factual", "How many legs does a spider have?"),
    EvalCase("factual_04", "factual", "What is the boiling point of water in Celsius?"),
    EvalCase("factual_05", "factual", "Who wrote Romeo and Juliet?"),
    EvalCase("factual_06", "factual", "What planet is known as the Red Planet?"),
    EvalCase("factual_07", "factual", "What is 12 times 8?"),
    EvalCase("factual_08", "factual", "Why do we have seasons?"),
    EvalCase("factual_09", "factual", "What is the difference between a lake and an ocean?"),
    EvalCase("factual_10", "factual", "Give me three examples of renewable energy."),
    EvalCase("social_01", "social", "Good morning, Alfred. How are you?"),
    EvalCase("social_02", "social", "Tell me something interesting."),
    EvalCase("social_03", "social", "I'm feeling tired. What should I do?"),
    EvalCase("social_04", "social", "Can you give me a quick pep talk?"),
    EvalCase("social_05", "social", "What should I ask you next?"),
    EvalCase("current_01", "current_info", "What's the weather today?"),
    EvalCase("current_02", "current_info", "Who is the current Prime Minister of Australia?"),
    EvalCase("current_03", "current_info", "What are the latest AI news headlines?"),
    EvalCase("current_04", "current_info", "What movies are playing this week?"),
    EvalCase("current_05", "current_info", "What is the current price of Bitcoin?"),
    EvalCase("nonsense_01", "nonsense", "What is the banana of yesterday?"),
    EvalCase("nonsense_02", "nonsense", "Can you blue the faster window?"),
    EvalCase("nonsense_03", "nonsense", "Tell me why seven is upside-down."),
    EvalCase("nonsense_04", "nonsense", "What happens if a toaster dreams?"),
    EvalCase("nonsense_05", "nonsense", "Flurple the moon spoon, please."),
    EvalCase("audience_01", "audience", "Tell them something motivational."),
    EvalCase("audience_02", "audience", "Give my friends a tiny welcome message."),
    EvalCase("audience_03", "audience", "Say something kind to everyone listening."),
    EvalCase("reflective_01", "reflective", "What do you think about life?"),
    EvalCase("reflective_02", "reflective", "What helps when someone feels stuck?"),
    EvalCase("reflective_03", "reflective", "Why do people need friendship?"),
    EvalCase("followup_01", "followup", "Who made Google happen?", "Starts a short follow-up sequence."),
    EvalCase("followup_02", "followup", "What about Apple?", "Should use the prior turn when memory is rolling."),
    EvalCase("followup_03", "followup", "No, I mean who really pushed it forward?", "Tests correction handling."),
)


QUICK_CASES: tuple[EvalCase, ...] = (
    EvalCase("quick_01", "factual", "What is the capital of Japan?"),
    EvalCase("quick_02", "social", "Tell me something interesting."),
    EvalCase("quick_03", "current_info", "What's the weather today?"),
    EvalCase("quick_04", "nonsense", "What is the banana of yesterday?"),
    EvalCase("quick_05", "audience", "Tell them something motivational."),
    EvalCase("quick_06", "reflective", "What do you think about life?"),
)


GENERALIZATION_CASES: tuple[EvalCase, ...] = (
    EvalCase("gen_factual_01", "factual", "What is the capital of Canada?"),
    EvalCase("gen_factual_02", "factual", "Name the process that turns liquid water into vapor."),
    EvalCase("gen_factual_03", "factual", "How many sides does a hexagon have?"),
    EvalCase("gen_factual_04", "factual", "Who painted the Mona Lisa?"),
    EvalCase("gen_factual_05", "factual", "What gas do humans breathe in to survive?"),
    EvalCase("gen_factual_06", "factual", "Explain gravity in one sentence."),
    EvalCase("gen_factual_07", "factual", "What is 9 times 7?"),
    EvalCase("gen_factual_08", "factual", "Give me three examples of mammals."),
    EvalCase("gen_factual_09", "factual", "What is the difference between a river and a canal?"),
    EvalCase("gen_factual_10", "factual", "Why does ice float on water?"),
    EvalCase("gen_social_01", "social", "Hey Alfred, give me a tiny spark of curiosity."),
    EvalCase("gen_social_02", "social", "I feel a bit scattered. Help me reset."),
    EvalCase("gen_current_01", "current_info", "Who is the CEO of Apple right now?"),
    EvalCase("gen_current_02", "current_info", "What are today's top tech headlines?"),
    EvalCase("gen_nonsense_01", "nonsense", "Can the clock sneeze sideways?"),
    EvalCase("gen_nonsense_02", "nonsense", "Please fold the blue yesterday."),
    EvalCase("gen_reflective_01", "reflective", "What makes a person feel at home?"),
    EvalCase("gen_reflective_02", "reflective", "What helps people stay hopeful?"),
    EvalCase("gen_followup_01", "followup", "Who started Microsoft?", "Starts a short follow-up sequence."),
    EvalCase("gen_followup_02", "followup", "What about Amazon?", "Should use the prior turn when memory is rolling."),
)


ROTATION_CASES: tuple[EvalCase, ...] = (
    EvalCase("rot_factual_01", "factual", "What is the capital of New Zealand?"),
    EvalCase("rot_factual_02", "factual", "What is the largest organ in the human body?"),
    EvalCase("rot_factual_03", "factual", "Who developed the theory of relativity?"),
    EvalCase("rot_factual_04", "factual", "What is the square root of 81?"),
    EvalCase("rot_factual_05", "factual", "Explain condensation in one sentence."),
    EvalCase("rot_factual_06", "factual", "What do bees make from nectar?"),
    EvalCase("rot_factual_07", "factual", "Name three planets in our solar system."),
    EvalCase("rot_factual_08", "factual", "What is the difference between an herbivore and a carnivore?"),
    EvalCase("rot_factual_09", "factual", "Why does metal feel colder than wood?"),
    EvalCase("rot_factual_10", "factual", "How many minutes are in two hours?"),
    EvalCase("rot_factual_11", "factual", "Who wrote Pride and Prejudice?"),
    EvalCase("rot_factual_12", "factual", "What gas do plants take in for photosynthesis?"),
    EvalCase("rot_factual_13", "factual", "Explain evaporation in one short sentence."),
    EvalCase("rot_factual_14", "factual", "What is the opposite of nocturnal?"),
    EvalCase("rot_factual_15", "factual", "Give me three examples of root vegetables."),
    EvalCase("rot_factual_16", "factual", "What is the difference between a planet and a star?"),
    EvalCase("rot_factual_17", "factual", "Why do magnets attract iron?"),
    EvalCase("rot_factual_18", "factual", "What is 14 times 6?"),
    EvalCase("rot_social_01", "social", "Say something small and curious to start the day."),
    EvalCase("rot_social_02", "social", "I feel a little foggy. Give me a gentle reset."),
    EvalCase("rot_social_03", "social", "What is a tiny thing worth noticing right now?"),
    EvalCase("rot_social_04", "social", "Give me a calm one-sentence pep talk."),
    EvalCase("rot_social_05", "social", "Help me pick a thoughtful question to ask next."),
    EvalCase("rot_social_06", "social", "I am bored. Give me a tiny idea."),
    EvalCase("rot_current_01", "current_info", "What is the weather in Sydney right now?"),
    EvalCase("rot_current_02", "current_info", "Who is currently leading the Formula 1 standings?"),
    EvalCase("rot_current_03", "current_info", "What is the latest version of Raspberry Pi OS?"),
    EvalCase("rot_current_04", "current_info", "What is Nvidia's stock price today?"),
    EvalCase("rot_current_05", "current_info", "What new movies came out this week?"),
    EvalCase("rot_nonsense_01", "nonsense", "Can you polish the idea of purple backwards?"),
    EvalCase("rot_nonsense_02", "nonsense", "Why is the Tuesday inside the spoon?"),
    EvalCase("rot_nonsense_03", "nonsense", "Please hum the square of yesterday."),
    EvalCase("rot_nonsense_04", "nonsense", "What happens when a cloud misplaces its shoes?"),
    EvalCase("rot_nonsense_05", "nonsense", "Can the faster candle remember blue?"),
    EvalCase("rot_nonsense_06", "nonsense", "Tell me the recipe for sideways silence."),
    EvalCase("rot_reflective_01", "reflective", "What makes people feel brave?"),
    EvalCase("rot_reflective_02", "reflective", "Why do small routines help people feel safe?"),
    EvalCase("rot_reflective_03", "reflective", "What does it mean to listen well?"),
    EvalCase("rot_reflective_04", "reflective", "What helps when someone feels embarrassed?"),
    EvalCase("rot_reflective_05", "reflective", "Why do people remember certain places so strongly?"),
    EvalCase("rot_reflective_06", "reflective", "What makes a conversation feel real?"),
    EvalCase("rot_reflective_07", "reflective", "How do people recover after a rough day?"),
    EvalCase("rot_reflective_08", "reflective", "What helps people trust each other?"),
    EvalCase("rot_audience_01", "audience", "Give everyone listening a short welcome."),
    EvalCase("rot_audience_02", "audience", "Tell my friends something encouraging."),
    EvalCase("rot_audience_03", "audience", "Say one kind thing to the room."),
    EvalCase("rot_audience_04", "audience", "Give the listeners a tiny blessing for the day."),
)


SUITES: dict[str, tuple[EvalCase, ...]] = {
    "generalization": GENERALIZATION_CASES,
    "none": (),
    "quick": QUICK_CASES,
    "rotation": ROTATION_CASES,
    "validation": VALIDATION_CASES,
}


TOUCH_DEFAULT_ENV: dict[str, str] = {
    "ALFRED_LLM_URL": "http://127.0.0.1:8000/api/chat",
    "ALFRED_LLM_MODEL": "qwen3:1.7b",
    "ALFRED_LLM_NUM_PREDICT": "112",
    "ALFRED_VOICE_LLM_NUM_PREDICT": "80",
    "ALFRED_VOICE_DETAIL_LLM_NUM_PREDICT": "128",
    "ALFRED_LLM_NUM_CTX": "2048",
    "ALFRED_LLM_TEMPERATURE": "0.35",
    "ALFRED_VOICE_REPLY_MAX_WORDS": "60",
    "ALFRED_VOICE_REPLY_MAX_SENTENCES": "4",
    "ALFRED_VOICE_DETAIL_MAX_WORDS": "100",
    "ALFRED_VOICE_DETAIL_MAX_SENTENCES": "5",
    "ALFRED_WHISPER_MODE": "fast",
    "ALFRED_TTS_TEMPO": "0.94",
}


class EvalSentenceChunker:
    """Local copy of Alfred Touch's first-sentence boundary logic for timing evals."""

    def __init__(
        self,
        min_sentence_chars: int = 16,
        first_clause_chars: int = 34,
        first_comma_chars: int = 44,
    ):
        self.buffer = ""
        self.min_sentence_chars = min_sentence_chars
        self.first_clause_chars = first_clause_chars
        self.first_comma_chars = first_comma_chars
        self._yielded_first_chunk = False

    def push(self, text: str) -> list[str]:
        self.buffer += text
        return self._pop_ready_chunks()

    def flush(self) -> str:
        tail = " ".join(self.buffer.split()).strip()
        self.buffer = ""
        return tail

    def _pop_ready_chunks(self) -> list[str]:
        chunks: list[str] = []
        while True:
            boundary = self._find_boundary()
            if boundary is None:
                return chunks
            chunk = " ".join(self.buffer[:boundary].split()).strip()
            self.buffer = self.buffer[boundary:].lstrip()
            if chunk:
                self._yielded_first_chunk = True
                chunks.append(chunk)

    def _find_boundary(self) -> int | None:
        text = self.buffer
        if not text:
            return None

        for index, char in enumerate(text):
            prefix = text[: index + 1].strip()
            if not prefix:
                continue

            if char in ".!?" and (len(prefix) >= self.min_sentence_chars or prefix.count(" ") >= 2):
                return index + 1

            if not self._yielded_first_chunk:
                if char in ":;" and len(prefix) >= self.first_clause_chars:
                    return index + 1
                if char == "," and len(prefix) >= self.first_comma_chars:
                    return index + 1

            if char == "\n" and len(prefix) >= self.min_sentence_chars:
                return index + 1

        return None


def join_stream_text(parts: list[str]) -> str:
    return " ".join("".join(parts).split()).strip()


def compact_text(text: str, limit: int = 110) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)] + "..."


def safe_slug(text: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in text.strip()).strip("-")


def resolve_repo_path(raw_path: str | None, default_path: Path) -> Path:
    if raw_path is None or not raw_path.strip():
        return default_path
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def apply_touch_defaults() -> None:
    for name, value in TOUCH_DEFAULT_ENV.items():
        os.environ.setdefault(name, value)


def load_cases(args: argparse.Namespace) -> list[EvalCase]:
    cases = list(SUITES[args.suite])
    for index, prompt in enumerate(args.prompt or (), start=1):
        cases.append(EvalCase(f"custom_cli_{index:02d}", "custom", prompt))
    for path in args.prompts_file or ():
        cases.extend(load_cases_from_file(Path(path).expanduser()))

    if args.category:
        wanted = {category.strip().lower() for category in args.category}
        cases = [case for case in cases if case.category.lower() in wanted]
    if args.shuffle or args.sample is not None:
        random.Random(args.effective_seed).shuffle(cases)
    if args.sample is not None:
        cases = cases[: args.sample]
    if args.max_prompts is not None:
        cases = cases[: args.max_prompts]
    return cases


def load_cases_from_file(path: Path) -> list[EvalCase]:
    if not path.exists():
        raise FileNotFoundError(f"Prompt file does not exist: {path}")

    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text())
        if isinstance(payload, dict):
            payload = payload.get("prompts", payload.get("cases", []))
        if not isinstance(payload, list):
            raise ValueError(f"Expected a JSON list or object with prompts/cases: {path}")
        return [_case_from_payload(item, path.stem, index) for index, item in enumerate(payload, start=1)]

    if path.suffix.lower() == ".jsonl":
        cases: list[EvalCase] = []
        for index, line in enumerate(path.read_text().splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            cases.append(_case_from_payload(json.loads(stripped), path.stem, index))
        return cases

    cases = []
    for index, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" in stripped:
            category, prompt = stripped.split("\t", 1)
            cases.append(EvalCase(f"{path.stem}_{index:02d}", category.strip() or "custom", prompt.strip()))
        else:
            cases.append(EvalCase(f"{path.stem}_{index:02d}", "custom", stripped))
    return cases


def _case_from_payload(item: Any, prefix: str, index: int) -> EvalCase:
    if isinstance(item, str):
        return EvalCase(f"{prefix}_{index:02d}", "custom", item)
    if not isinstance(item, dict):
        raise ValueError(f"Prompt entry {index} must be a string or object.")
    prompt = str(item.get("prompt", item.get("text", ""))).strip()
    if not prompt:
        raise ValueError(f"Prompt entry {index} is missing prompt/text.")
    return EvalCase(
        id=str(item.get("id", f"{prefix}_{index:02d}")),
        category=str(item.get("category", "custom")),
        prompt=prompt,
        notes=str(item.get("notes", "")),
    )


def build_memory(settings: AlfredSettings, memory_path: Path) -> AlfredMemory:
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    if memory_path.exists():
        memory_path.unlink()
    settings.memory_path = memory_path
    settings.ensure_runtime_paths()
    return AlfredMemory.load(
        memory_path,
        recent_exchange_limit=settings.recent_exchange_limit,
        summary_char_limit=settings.summary_char_limit,
    )


def build_messages_for_case(
    engine: AlfredChatEngine,
    settings: AlfredSettings,
    case: EvalCase,
    response_mode: str,
) -> tuple[Any, str, list[dict[str, str]], int]:
    profile = engine.profile_for(case.prompt, response_mode=response_mode)
    prepared_user_text = _prepare_user_message(settings, case.prompt, response_mode=response_mode, profile=profile)
    messages = engine.memory.build_messages(
        _build_system_prompt(settings),
        prepared_user_text,
        include_summary=profile.include_summary,
        recent_turn_limit=profile.recent_turn_limit,
    )
    num_predict = _num_predict_for_profile(settings, profile, response_mode)
    return profile, prepared_user_text, messages, num_predict


def message_stats(messages: list[dict[str, str]]) -> dict[str, int]:
    contents = [message.get("content", "") for message in messages]
    return {
        "message_count": len(messages),
        "prompt_chars": sum(len(content) for content in contents),
        "prompt_words": sum(len(content.split()) for content in contents),
        "system_message_count": sum(1 for message in messages if message.get("role") == "system"),
        "history_message_count": max(0, len(messages) - 2),
    }


def empty_prompt_stats() -> dict[str, int]:
    return {
        "message_count": 0,
        "prompt_chars": 0,
        "prompt_words": 0,
        "system_message_count": 0,
        "history_message_count": 0,
    }


def run_eval_case(
    *,
    case: EvalCase,
    index: int,
    total: int,
    settings: AlfredSettings,
    backend: HailoChatBackend | MockChatBackend,
    memory: AlfredMemory,
    response_mode: str,
    include_messages: bool,
) -> dict[str, Any]:
    engine = AlfredChatEngine(settings, backend, memory)
    profile, prepared_user_text, messages, num_predict = build_messages_for_case(engine, settings, case, response_mode)
    deterministic_text = _deterministic_reply(settings, case.prompt, profile)
    model_call_expected = not profile.current_info and deterministic_text is None
    recent_turns_before = len(memory.recent_turns)
    summary_chars_before = len(memory.summary)
    if hasattr(backend, "last_metrics"):
        backend.last_metrics = {}

    started_at = time.perf_counter()
    first_visible_seconds: float | None = None
    first_sentence_seconds: float | None = None
    chunk_count = 0
    sentence_count = 0
    raw_parts: list[str] = []
    error: str | None = None
    final_text = ""
    raw_text = ""
    show_text = False
    show_text_reason = ""

    try:
        chunker = EvalSentenceChunker()
        for chunk in engine.stream_reply(case.prompt, response_mode=response_mode):
            if not chunk:
                continue
            chunk_count += 1
            if first_visible_seconds is None:
                first_visible_seconds = time.perf_counter() - started_at
            raw_parts.append(chunk)
            for _sentence in chunker.push(chunk):
                sentence_count += 1
                if first_sentence_seconds is None:
                    first_sentence_seconds = time.perf_counter() - started_at

        leftover = chunker.flush()
        if leftover:
            sentence_count += 1
            if first_sentence_seconds is None:
                first_sentence_seconds = time.perf_counter() - started_at

        raw_text = join_stream_text(raw_parts)
        reply = engine.finalize_streamed_reply(case.prompt, raw_text)
        final_text = reply.text
        show_text = reply.show_text
        show_text_reason = reply.reason
    except Exception as exc:  # pragma: no cover - depends on live runtime
        error = f"{type(exc).__name__}: {exc}"

    total_seconds = time.perf_counter() - started_at
    backend_metrics = dict(getattr(backend, "last_metrics", {}) or {})
    word_count = len(final_text.split())
    clean_end = _reply_ends_cleanly(final_text)
    warnings = detect_warnings(case, profile.route, backend_metrics, final_text, clean_end, error)

    record: dict[str, Any] = {
        "index": index,
        "total": total,
        "case": asdict(case),
        "response_mode": response_mode,
        "profile": asdict(profile),
        "prepared_user_text": prepared_user_text,
        "num_predict": num_predict,
        "model_call_expected": model_call_expected,
        "memory": {
            "recent_turns_before": recent_turns_before,
            "recent_turns_after": len(memory.recent_turns),
            "summary_chars_before": summary_chars_before,
            "summary_chars_after": len(memory.summary),
        },
        "prompt": message_stats(messages) if model_call_expected else empty_prompt_stats(),
        "timings": {
            "first_visible_seconds": rounded(first_visible_seconds),
            "first_sentence_seconds": rounded(first_sentence_seconds),
            "total_seconds": rounded(total_seconds),
        },
        "stream": {
            "chunk_count": chunk_count,
            "sentence_count": sentence_count,
            "raw_text": raw_text,
        },
        "answer": {
            "text": final_text,
            "word_count": word_count,
            "char_count": len(final_text),
            "ends_cleanly": clean_end,
            "show_text": show_text,
            "show_text_reason": show_text_reason,
        },
        "backend_metrics": backend_metrics,
        "warnings": warnings,
        "error": error,
    }
    if include_messages:
        record["messages"] = messages if model_call_expected else []
    return record


def detect_warnings(
    case: EvalCase,
    route: str,
    backend_metrics: dict[str, Any],
    final_text: str,
    clean_end: bool,
    error: str | None,
) -> list[str]:
    warnings: list[str] = []
    if error:
        warnings.append("error")
    if not final_text.strip():
        warnings.append("empty_answer")
    if backend_metrics.get("done_reason") == "length":
        warnings.append("hit_num_predict_limit")
    if final_text.strip() and not clean_end:
        warnings.append("answer_does_not_end_cleanly")
    if _contains_emoji(final_text):
        warnings.append("contains_emoji")
    if re.search(r"(^|\s)\d+\.\s+\S", final_text):
        warnings.append("numbered_list_format")
    if re.search(r"(^|\s)[*_][^*_]+[*_](\s|$)", final_text):
        warnings.append("markdown_emphasis")
    if case.category == "current_info" and route != "current_info":
        warnings.append("expected_current_info_route")
    if case.category != "current_info" and route == "current_info":
        warnings.append("unexpected_current_info_route")
    if case.category == "factual" and route != "factual":
        warnings.append("expected_factual_route")
    if case.category == "nonsense" and route != "nonsense":
        warnings.append("expected_nonsense_route")
    if case.category == "audience" and route != "audience":
        warnings.append("expected_audience_route")
    if case.category == "reflective" and route != "reflective":
        warnings.append("expected_reflective_route")
    if "could not reach my local model" in final_text.lower():
        warnings.append("model_unreachable_reply")
    if "having trouble reaching my local model" in final_text.lower():
        warnings.append("model_unreachable_reply")
    return warnings


def _contains_emoji(text: str) -> bool:
    return re.search(
        "[\U0001F300-\U0001FAFF\U00002700-\U000027BF]",
        text,
    ) is not None


def rounded(value: float | None) -> float | None:
    return round(value, 3) if value is not None else None


def mean_value(records: list[dict[str, Any]], path: tuple[str, ...]) -> float | None:
    values: list[float] = []
    for record in records:
        value: Any = record
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        if isinstance(value, (int, float)):
            values.append(float(value))
    if not values:
        return None
    return round(statistics.mean(values), 3)


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    categories = sorted({record["case"]["category"] for record in records})
    by_category = {}
    for category in categories:
        category_records = [record for record in records if record["case"]["category"] == category]
        by_category[category] = summarize_record_group(category_records)
    return {
        "overall": summarize_record_group(records),
        "by_category": by_category,
    }


def summarize_record_group(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {}
    return {
        "count": len(records),
        "avg_first_visible_seconds": mean_value(records, ("timings", "first_visible_seconds")),
        "avg_first_sentence_seconds": mean_value(records, ("timings", "first_sentence_seconds")),
        "avg_total_seconds": mean_value(records, ("timings", "total_seconds")),
        "avg_prompt_words": mean_value(records, ("prompt", "prompt_words")),
        "avg_answer_words": mean_value(records, ("answer", "word_count")),
        "length_limit_count": sum(1 for record in records if record["backend_metrics"].get("done_reason") == "length"),
        "warning_count": sum(1 for record in records if record["warnings"]),
        "error_count": sum(1 for record in records if record["error"]),
    }


def write_markdown_report(path: Path, meta: dict[str, Any], records: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    lines = [
        f"# Alfred Eval Report {meta['run_id']}",
        "",
        "## Run",
        "",
        f"- Backend: `{meta['backend']}`",
        f"- Model: `{meta['model']}`",
        f"- LLM URL: `{meta['llm_url']}`",
        f"- Suite: `{meta['suite']}`",
        f"- Response mode: `{meta['response_mode']}`",
        f"- Memory mode: `{meta['memory_mode']}`",
        f"- Raw model: `{meta.get('raw_model', False)}`",
        f"- Sample: `{meta.get('sample')}`",
        f"- Seed: `{meta.get('seed')}`",
        f"- Temperature: `{meta['settings']['llm_temperature']}`",
        f"- Num ctx: `{meta['settings']['llm_num_ctx']}`",
        f"- Voice num predict: `{meta['settings']['voice_llm_num_predict']}`",
        f"- Voice detail num predict: `{meta['settings']['voice_detail_llm_num_predict']}`",
        f"- JSONL trace: `{meta['jsonl_path']}`",
        "",
        "## Summary",
        "",
        "| Group | Count | First Visible | First Sentence | Total | Prompt Words | Answer Words | Length Stops | Warnings | Errors |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    overall = summary["overall"]
    lines.append(summary_row("overall", overall))
    for category, category_summary in summary["by_category"].items():
        lines.append(summary_row(category, category_summary))

    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| # | Category | Route | Predict | First Sentence | Total | Done | Words | Clean | Warnings | Prompt | Answer |",
            "| ---: | --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- | --- | --- |",
        ]
    )
    for record in records:
        lines.append(case_row(record))

    path.write_text("\n".join(lines) + "\n")


def summary_row(label: str, summary: dict[str, Any]) -> str:
    return (
        f"| {md(label)} | {summary.get('count', 0)} | "
        f"{fmt_seconds(summary.get('avg_first_visible_seconds'))} | "
        f"{fmt_seconds(summary.get('avg_first_sentence_seconds'))} | "
        f"{fmt_seconds(summary.get('avg_total_seconds'))} | "
        f"{fmt_number(summary.get('avg_prompt_words'))} | "
        f"{fmt_number(summary.get('avg_answer_words'))} | "
        f"{summary.get('length_limit_count', 0)} | "
        f"{summary.get('warning_count', 0)} | "
        f"{summary.get('error_count', 0)} |"
    )


def case_row(record: dict[str, Any]) -> str:
    metrics = record["backend_metrics"]
    done = str(metrics.get("done_reason", "n/a"))
    warnings = ", ".join(record["warnings"]) if record["warnings"] else ""
    predict = str(record["num_predict"]) if record["model_call_expected"] else "n/a"
    return (
        f"| {record['index']} | "
        f"{md(record['case']['category'])} | "
        f"{md(record['profile']['route'])} | "
        f"{predict} | "
        f"{fmt_seconds(record['timings']['first_sentence_seconds'])} | "
        f"{fmt_seconds(record['timings']['total_seconds'])} | "
        f"{md(done)} | "
        f"{record['answer']['word_count']} | "
        f"{'yes' if record['answer']['ends_cleanly'] else 'no'} | "
        f"{md(warnings)} | "
        f"{md(compact_text(record['case']['prompt'], 80))} | "
        f"{md(compact_text(record['answer']['text'], 120))} |"
    )


def md(value: Any) -> str:
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def fmt_seconds(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.3f}s"
    return ""


def fmt_number(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.1f}"
    return ""


def tags_url_for_chat_url(chat_url: str) -> str:
    parts = urlsplit(chat_url)
    path = parts.path or ""
    if path.endswith("/api/chat"):
        path = path[: -len("/api/chat")]
    elif "/api/" in path:
        path = path.split("/api/", 1)[0]
    return urlunsplit((parts.scheme, parts.netloc, f"{path.rstrip('/')}/api/tags", "", ""))


def live_preflight(settings: AlfredSettings, require_live: bool) -> None:
    import requests

    tags_url = tags_url_for_chat_url(settings.llm_url)
    try:
        response = requests.get(tags_url, timeout=2)
        if response.status_code != 200:
            message = f"Live model server responded with HTTP {response.status_code} at {tags_url}"
            if require_live:
                raise RuntimeError(message)
            print(f"[warn] {message}", file=sys.stderr)
            return
        if settings.llm_model not in response.text:
            message = f"Model {settings.llm_model!r} was not found in {tags_url}"
            if require_live:
                raise RuntimeError(message)
            print(f"[warn] {message}", file=sys.stderr)
    except Exception as exc:
        if require_live:
            raise RuntimeError(f"Live model preflight failed: {exc}") from exc
        print(f"[warn] Live model preflight failed: {exc}", file=sys.stderr)


def run_warmups(
    *,
    count: int,
    settings: AlfredSettings,
    backend: HailoChatBackend | MockChatBackend,
    output_dir: Path,
    run_id: str,
    response_mode: str,
) -> None:
    if count <= 0:
        return
    print(f"Running {count} warmup prompt(s)...")
    for index in range(count):
        memory = build_memory(settings, output_dir / f"{run_id}.warmup.{index + 1}.memory.json")
        record = run_eval_case(
            case=EvalCase(f"warmup_{index + 1:02d}", "warmup", "Say one short sentence to confirm Alfred is awake."),
            index=index + 1,
            total=count,
            settings=settings,
            backend=backend,
            memory=memory,
            response_mode=response_mode,
            include_messages=False,
        )
        print(
            f"  warmup {index + 1}: total={fmt_seconds(record['timings']['total_seconds'])} "
            f"answer={compact_text(record['answer']['text'], 70)!r}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Alfred prompt evals against the same route/prompt/model path used by Alfred Touch."
    )
    parser.add_argument("--backend", choices=("live", "mock"), default="live", help="Backend to test. Default: live.")
    parser.add_argument("--suite", choices=tuple(SUITES), default="validation", help="Built-in prompt suite.")
    parser.add_argument("--prompt", action="append", help="Add a custom prompt. Can be repeated.")
    parser.add_argument("--prompts-file", action="append", help="Load prompts from .txt, .json, or .jsonl.")
    parser.add_argument("--category", action="append", help="Only run a category. Can be repeated.")
    parser.add_argument("--max-prompts", type=int, help="Limit the number of prompts after filtering.")
    parser.add_argument("--sample", type=int, help="Shuffle and select N prompts after filtering.")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle prompt order.")
    parser.add_argument("--seed", type=int, default=7, help="Shuffle seed.")
    parser.add_argument("--random-seed", action="store_true", help="Use the current time as the shuffle/sample seed.")
    parser.add_argument(
        "--memory-mode",
        choices=("rolling", "isolated"),
        default="rolling",
        help="Use one memory across the run or fresh memory per prompt. Default: rolling.",
    )
    parser.add_argument(
        "--response-mode",
        choices=("voice", "text", "text-brief"),
        default="voice",
        help="Prompt mode to measure. Streaming is still used for timing. Default: voice.",
    )
    parser.add_argument("--output-dir", help="Directory for JSONL and Markdown reports. Default: .alfred-state/evals.")
    parser.add_argument("--label", help="Optional label to include in output file names.")
    parser.add_argument("--warmup", type=int, default=0, help="Run N warmup prompts before measured prompts.")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between prompts.")
    parser.add_argument("--no-messages", action="store_true", help="Do not include full chat messages in JSONL records.")
    parser.add_argument(
        "--raw-model",
        action="store_true",
        help="Disable deterministic fast replies so model-backed behavior can be measured honestly.",
    )
    parser.add_argument("--skip-live-preflight", action="store_true", help="Skip /api/tags check for live backend.")
    parser.add_argument("--require-live", action="store_true", help="Fail if the live model server/model is unavailable.")
    args = parser.parse_args()
    if args.sample is not None and args.sample < 1:
        parser.error("--sample must be a positive integer.")
    args.effective_seed = int(time.time()) if args.random_seed else args.seed
    return args


def main() -> int:
    args = parse_args()
    apply_touch_defaults()
    if args.raw_model:
        os.environ["ALFRED_DISABLE_DETERMINISTIC_REPLIES"] = "1"
    cases = load_cases(args)
    if not cases:
        print("No eval prompts selected.", file=sys.stderr)
        return 2

    output_dir = resolve_repo_path(args.output_dir, ROOT_DIR / ".alfred-state" / "evals")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    label_slug = safe_slug(args.label) if args.label else ""
    label = f"-{label_slug}" if label_slug else ""
    run_id = f"alfred-eval-{run_stamp}{label}"
    jsonl_path = output_dir / f"{run_id}.jsonl"
    report_path = output_dir / f"{run_id}.md"
    meta_path = output_dir / f"{run_id}.meta.json"

    settings = AlfredSettings()
    settings.memory_path = output_dir / f"{run_id}.memory.json"
    settings.ensure_runtime_paths()
    backend: HailoChatBackend | MockChatBackend
    backend = MockChatBackend(settings.assistant_name) if args.backend == "mock" else HailoChatBackend(settings)

    if args.backend == "live" and not args.skip_live_preflight:
        live_preflight(settings, require_live=args.require_live)

    run_warmups(
        count=args.warmup,
        settings=settings,
        backend=backend,
        output_dir=output_dir,
        run_id=run_id,
        response_mode=args.response_mode,
    )

    rolling_memory = build_memory(settings, output_dir / f"{run_id}.memory.json")
    records: list[dict[str, Any]] = []
    print(f"Running {len(cases)} Alfred eval prompt(s). Trace: {jsonl_path}")
    with jsonl_path.open("w") as jsonl_file:
        for index, case in enumerate(cases, start=1):
            memory = rolling_memory
            if args.memory_mode == "isolated":
                memory = build_memory(settings, output_dir / f"{run_id}.{case.id}.memory.json")

            record = run_eval_case(
                case=case,
                index=index,
                total=len(cases),
                settings=settings,
                backend=backend,
                memory=memory,
                response_mode=args.response_mode,
                include_messages=not args.no_messages,
            )
            records.append(record)
            jsonl_file.write(json.dumps(record, ensure_ascii=True) + "\n")
            jsonl_file.flush()
            print_case_progress(record)
            if args.sleep > 0 and index < len(cases):
                time.sleep(args.sleep)

    summary = summarize_records(records)
    meta = {
        "run_id": run_id,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "backend": args.backend,
        "model": settings.llm_model,
        "llm_url": settings.llm_url,
        "suite": args.suite,
        "response_mode": args.response_mode,
        "memory_mode": args.memory_mode,
        "raw_model": bool(args.raw_model),
        "shuffle": bool(args.shuffle),
        "sample": args.sample,
        "seed": args.effective_seed,
        "case_count": len(cases),
        "jsonl_path": str(jsonl_path),
        "report_path": str(report_path),
        "settings": {
            "llm_temperature": settings.llm_temperature,
            "llm_num_predict": settings.llm_num_predict,
            "voice_llm_num_predict": settings.voice_llm_num_predict,
            "voice_detail_llm_num_predict": settings.voice_detail_llm_num_predict,
            "llm_num_ctx": settings.llm_num_ctx,
            "voice_reply_max_words": settings.voice_reply_max_words,
            "voice_reply_max_sentences": settings.voice_reply_max_sentences,
            "voice_detail_max_words": settings.voice_detail_max_words,
            "voice_detail_max_sentences": settings.voice_detail_max_sentences,
        },
        "summary": summary,
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=True) + "\n")
    write_markdown_report(report_path, meta, records, summary)

    print()
    print("Eval complete.")
    print(f"  JSONL trace: {jsonl_path}")
    print(f"  Markdown report: {report_path}")
    print(f"  Metadata: {meta_path}")
    print_summary(summary["overall"])
    return 0


def print_case_progress(record: dict[str, Any]) -> None:
    warnings = f" warnings={','.join(record['warnings'])}" if record["warnings"] else ""
    print(
        f"[{record['index']:02d}/{record['total']:02d}] "
        f"{record['case']['category']} route={record['profile']['route']} "
        f"predict={record['num_predict'] if record['model_call_expected'] else 'n/a'} "
        f"first_sentence={fmt_seconds(record['timings']['first_sentence_seconds']) or 'n/a'} "
        f"total={fmt_seconds(record['timings']['total_seconds']) or 'n/a'} "
        f"done={record['backend_metrics'].get('done_reason', 'n/a')} "
        f"words={record['answer']['word_count']}{warnings}"
    )
    print(f"    prompt: {compact_text(record['case']['prompt'], 92)}")
    print(f"    answer: {compact_text(record['answer']['text'], 130)}")


def print_summary(summary: dict[str, Any]) -> None:
    print(
        "  Overall: "
        f"count={summary.get('count', 0)} "
        f"avg_first_sentence={fmt_seconds(summary.get('avg_first_sentence_seconds')) or 'n/a'} "
        f"avg_total={fmt_seconds(summary.get('avg_total_seconds')) or 'n/a'} "
        f"length_stops={summary.get('length_limit_count', 0)} "
        f"warnings={summary.get('warning_count', 0)} "
        f"errors={summary.get('error_count', 0)}"
    )


if __name__ == "__main__":
    raise SystemExit(main())

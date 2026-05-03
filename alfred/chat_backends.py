from __future__ import annotations

import datetime
import json
import logging
import time

import requests

from .chat_text import (
    _LeadingSpeakerLabelStripper,
    _StreamingChunkCleaner,
    _clean_reply,
    _single_line,
)
from .config import AlfredSettings


logger = logging.getLogger(__name__)


class MockChatBackend:
    def __init__(self, assistant_name: str):
        self.assistant_name = assistant_name

    def generate_reply(self, messages: list[dict[str, str]], *, num_predict: int | None = None) -> str:
        user_text = messages[-1]["content"].strip()
        lower = user_text.lower()

        if "time" in lower:
            now = datetime.datetime.now().strftime("%I:%M %p")
            return f"It is {now}. This is the mock backend, but the touch app is responding."

        if len(user_text.split()) < 8:
            return f"{self.assistant_name} heard you. It's nice to talk."

        return (
            f"{self.assistant_name} is here and listening. "
            "The mock backend is working, so the touch pipeline is ready for the live local model."
        )

    def stream_reply(self, messages: list[dict[str, str]], *, num_predict: int | None = None):
        yield self.generate_reply(messages, num_predict=num_predict)


class HailoChatBackend:
    def __init__(self, settings: AlfredSettings):
        self.settings = settings
        self.last_metrics: dict[str, float | int | str] = {}

    def generate_reply(self, messages: list[dict[str, str]], *, num_predict: int | None = None) -> str:
        candidate_messages = _candidate_message_sets(messages)
        started_at = time.perf_counter()

        try:
            for attempt_index, attempt_messages in enumerate(candidate_messages):
                payload = self._build_payload(attempt_messages, stream=False, num_predict=num_predict)
                response = requests.post(self.settings.llm_url, json=payload, timeout=self.settings.llm_timeout_seconds)
                if response.status_code == 200:
                    response_payload = response.json()
                    self.last_metrics = _extract_ollama_metrics(response_payload)
                    logger.info(
                        "LLM round-trip completed in %.2fs%s",
                        time.perf_counter() - started_at,
                        _format_ollama_metrics(self.last_metrics),
                    )
                    content = response_payload.get("message", {}).get("content", "").strip()
                    return _clean_reply(content) or "I am here, but I could not think of the right words just now."

                if attempt_index + 1 < len(candidate_messages) and _should_retry_hailo_without_system(response.text):
                    logger.warning("Retrying Hailo request without system-role messages")
                    continue

                logger.error("LLM returned %s: %s", response.status_code, response.text)
                return "I am having trouble reaching my local model right now."
        except requests.RequestException as exc:
            logger.error("LLM request failed: %s", exc)
            return "I could not reach my local model right now."

    def stream_reply(self, messages: list[dict[str, str]], *, num_predict: int | None = None):
        candidate_messages = _candidate_message_sets(messages)
        started_at = time.perf_counter()

        try:
            for attempt_index, attempt_messages in enumerate(candidate_messages):
                payload = self._build_payload(attempt_messages, stream=True, num_predict=num_predict)
                cleaner = _StreamingChunkCleaner()
                label_cleaner = _LeadingSpeakerLabelStripper(self.settings.assistant_name)
                first_visible_at: float | None = None
                stream_metrics: dict[str, float | int | str] = {}

                with requests.post(
                    self.settings.llm_url,
                    json=payload,
                    stream=True,
                    timeout=self.settings.llm_timeout_seconds,
                ) as response:
                    if response.status_code != 200:
                        if attempt_index + 1 < len(candidate_messages) and _should_retry_hailo_without_system(response.text):
                            logger.warning("Retrying Hailo stream without system-role messages")
                            continue

                        logger.error("LLM stream returned %s: %s", response.status_code, response.text)
                        fallback = self.generate_reply(candidate_messages[-1], num_predict=num_predict)
                        if fallback:
                            yield fallback
                        return

                    for line in response.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        metrics = _extract_ollama_metrics(data)
                        if metrics:
                            stream_metrics = metrics

                        chunk = data.get("message", {}).get("content", "")
                        if not chunk and "choices" in data:
                            try:
                                chunk = data["choices"][0].get("delta", {}).get("content", "")
                            except Exception:
                                chunk = ""

                        if chunk:
                            visible = cleaner.feed(chunk)
                            if visible:
                                visible = label_cleaner.feed(visible)
                            if visible:
                                if first_visible_at is None:
                                    first_visible_at = time.perf_counter()
                                    logger.info("LLM first visible chunk arrived in %.2fs", first_visible_at - started_at)
                                yield visible

                        if data.get("done"):
                            break

                    tail = cleaner.flush()
                    if tail:
                        tail = label_cleaner.feed(tail, final=True)
                    if tail:
                        if first_visible_at is None:
                            first_visible_at = time.perf_counter()
                            logger.info("LLM first visible chunk arrived in %.2fs", first_visible_at - started_at)
                        yield tail

                    logger.info("LLM streaming completed in %.2fs", time.perf_counter() - started_at)
                    self.last_metrics = stream_metrics
                    if stream_metrics:
                        logger.info("LLM stream metrics%s", _format_ollama_metrics(stream_metrics))
                    return
        except requests.RequestException as exc:
            logger.error("LLM stream request failed: %s", exc)
            fallback = self.generate_reply(candidate_messages[-1], num_predict=num_predict)
            if fallback:
                yield fallback

    def _build_payload(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool,
        num_predict: int | None = None,
    ) -> dict:
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self.settings.llm_temperature,
                "num_predict": num_predict or self.settings.llm_num_predict,
                "num_ctx": self.settings.llm_num_ctx,
            },
        }
        if self.settings.llm_keep_alive:
            payload["keep_alive"] = self.settings.llm_keep_alive
        if self.settings.llm_use_no_think and "qwen3" in self.settings.llm_model.lower():
            payload["think"] = False
        return payload


def _candidate_message_sets(messages: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    base = [dict(message) for message in messages]
    flattened = _flatten_system_messages(messages)
    if flattened == base:
        return [base]
    return [base, flattened]


def _flatten_system_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    system_parts = [_single_line(message.get("content", "")) for message in messages if message.get("role") == "system"]
    prefix = " ".join(part for part in system_parts if part).strip()
    non_system = [dict(message) for message in messages if message.get("role") != "system"]

    if not prefix:
        return non_system or [dict(message) for message in messages]

    for index in range(len(non_system) - 1, -1, -1):
        if non_system[index].get("role") == "user":
            original = _single_line(non_system[index].get("content", ""))
            non_system[index]["content"] = f"{prefix} User request: {original}".strip()
            return non_system

    return [{"role": "user", "content": prefix}] + non_system


def _extract_ollama_metrics(payload: dict) -> dict[str, float | int | str]:
    metrics: dict[str, float | int | str] = {}
    for key in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
        raw_value = payload.get(key)
        if isinstance(raw_value, (int, float)):
            metrics[f"{key}_seconds"] = round(float(raw_value) / 1_000_000_000, 3)
    for key in ("prompt_eval_count", "eval_count"):
        raw_value = payload.get(key)
        if isinstance(raw_value, int):
            metrics[key] = raw_value
    done_reason = payload.get("done_reason")
    if isinstance(done_reason, str) and done_reason.strip():
        metrics["done_reason"] = done_reason.strip()
    return metrics


def _format_ollama_metrics(metrics: dict[str, float | int | str]) -> str:
    if not metrics:
        return ""

    parts: list[str] = []
    total = metrics.get("total_duration_seconds")
    load = metrics.get("load_duration_seconds")
    prompt = metrics.get("prompt_eval_duration_seconds")
    prompt_tokens = metrics.get("prompt_eval_count")
    eval_duration = metrics.get("eval_duration_seconds")
    eval_tokens = metrics.get("eval_count")
    done_reason = metrics.get("done_reason")

    if isinstance(total, (int, float)):
        parts.append(f"server_total={total:.2f}s")
    if isinstance(load, (int, float)):
        parts.append(f"load={load:.2f}s")
    if isinstance(prompt, (int, float)):
        prompt_part = f"prompt={prompt:.2f}s"
        if isinstance(prompt_tokens, int):
            prompt_part += f"/{prompt_tokens} tok"
        parts.append(prompt_part)
    if isinstance(eval_duration, (int, float)):
        eval_part = f"eval={eval_duration:.2f}s"
        if isinstance(eval_tokens, int):
            eval_part += f"/{eval_tokens} tok"
        parts.append(eval_part)
    if isinstance(done_reason, str):
        parts.append(f"done={done_reason}")
    return f" ({', '.join(parts)})" if parts else ""


def _should_retry_hailo_without_system(response_text: str) -> bool:
    lowered = response_text.lower()
    return (
        "system role messages can only be provided on the first prompt" in lowered
        or "failed to render prompt from json strings" in lowered
        or "error processing request" in lowered
    )

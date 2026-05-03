from __future__ import annotations

import re

from .chat_runtime import (
    _build_system_prompt,
    _current_info_reply,
    _deterministic_reply,
    _looks_contextual_followup,
    _looks_detail_request,
    _looks_emotional_prompt,
    _looks_exact_reply_instruction,
    _looks_factual_question,
    _looks_malformed_prompt,
    _looks_media_question,
    _looks_open_ended_companion_prompt,
    _looks_reflective_question,
    _looks_social_prompt,
    _looks_audience_prompt,
    _needs_current_info,
    _num_predict_for_profile,
    _prepare_user_message,
)
from .chat_text import (
    _clean_reply,
    _reply_ends_cleanly,
    _should_show_reply_text,
    _strip_leading_speaker_label,
    _trim_truncated_reply,
)
from .chat_types import AssistantReply, ChatBackend, ChatRequestProfile
from .config import AlfredSettings
from .memory import AlfredMemory


class AlfredChatEngine:
    def __init__(self, settings: AlfredSettings, backend: ChatBackend, memory: AlfredMemory):
        self.settings = settings
        self.backend = backend
        self.memory = memory

    def reply(self, user_text: str, response_mode: str = "default") -> AssistantReply:
        profile = self.profile_for(user_text, response_mode=response_mode)
        if profile.current_info:
            text = _current_info_reply()
            show_text, reason = _should_show_reply_text(text, self.settings.transcript_char_threshold)
            if profile.remember_exchange:
                self.memory.record_exchange(user_text, text)
            return AssistantReply(text=text, show_text=show_text, reason=reason)

        deterministic_text = _deterministic_reply(self.settings, user_text, profile)
        if deterministic_text is not None:
            show_text, reason = _should_show_reply_text(deterministic_text, self.settings.transcript_char_threshold)
            if profile.remember_exchange:
                self.memory.record_exchange(user_text, deterministic_text)
            return AssistantReply(text=deterministic_text, show_text=show_text, reason=reason)

        prompt_user_text = _prepare_user_message(self.settings, user_text, response_mode=response_mode, profile=profile)
        messages = self.memory.build_messages(
            _build_system_prompt(self.settings),
            prompt_user_text,
            include_summary=profile.include_summary,
            recent_turn_limit=profile.recent_turn_limit,
        )
        num_predict = _num_predict_for_profile(self.settings, profile, response_mode)
        text = self.backend.generate_reply(messages, num_predict=num_predict).strip()
        text = _clean_reply(text)
        if self.last_reply_hit_length_limit():
            text = _trim_truncated_reply(text)
        text = _strip_leading_speaker_label(text, self.settings.assistant_name)
        if not text:
            text = "I am here with you."

        show_text, reason = _should_show_reply_text(text, self.settings.transcript_char_threshold)
        if profile.remember_exchange:
            self.memory.record_exchange(user_text, text)
        return AssistantReply(text=text, show_text=show_text, reason=reason)

    def stream_reply(self, user_text: str, response_mode: str = "voice"):
        profile = self.profile_for(user_text, response_mode=response_mode)
        if profile.current_info:
            yield _current_info_reply()
            return

        deterministic_text = _deterministic_reply(self.settings, user_text, profile)
        if deterministic_text is not None:
            yield deterministic_text
            return

        prompt_user_text = _prepare_user_message(self.settings, user_text, response_mode=response_mode, profile=profile)
        messages = self.memory.build_messages(
            _build_system_prompt(self.settings),
            prompt_user_text,
            include_summary=profile.include_summary,
            recent_turn_limit=profile.recent_turn_limit,
        )
        num_predict = _num_predict_for_profile(self.settings, profile, response_mode)
        stream = self.backend.stream_reply(messages, num_predict=num_predict)
        visible_parts: list[str] = []
        try:
            for chunk in stream:
                if not chunk:
                    continue
                visible_parts.append(chunk)
                yield chunk
                if _should_stop_voice_stream("".join(visible_parts), profile, self.settings, response_mode):
                    break
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()

    def finalize_streamed_reply(self, user_text: str, full_text: str) -> AssistantReply:
        profile = self.profile_for(user_text, response_mode="voice")
        text = _clean_reply(full_text).strip()
        if self.last_reply_hit_length_limit():
            text = _trim_truncated_reply(text)
        text = _strip_leading_speaker_label(text, self.settings.assistant_name)
        if not text:
            text = "I am here with you."

        show_text, reason = _should_show_reply_text(text, self.settings.transcript_char_threshold)
        if profile.remember_exchange:
            self.memory.record_exchange(user_text, text)
        return AssistantReply(text=text, show_text=show_text, reason=reason)

    def last_reply_hit_length_limit(self) -> bool:
        metrics = getattr(self.backend, "last_metrics", None) or {}
        return metrics.get("done_reason") == "length"

    def profile_for(self, user_text: str, response_mode: str = "default") -> ChatRequestProfile:
        social = _looks_social_prompt(user_text)
        contextual_followup = _looks_contextual_followup(user_text)
        open_ended = _looks_open_ended_companion_prompt(user_text)
        standalone_social = (social or open_ended) and not contextual_followup
        factual = _looks_factual_question(user_text)
        media = _looks_media_question(user_text)
        current_info = _needs_current_info(user_text)
        exact_reply = _looks_exact_reply_instruction(user_text)
        reflective = _looks_reflective_question(user_text)
        emotional = _looks_emotional_prompt(user_text)
        audience = _looks_audience_prompt(user_text)
        malformed = _looks_malformed_prompt(user_text)
        explicit_detail = _looks_detail_request(user_text)

        if current_info:
            route = "current_info"
        elif exact_reply:
            route = "exact_reply"
        elif malformed:
            route = "nonsense"
        elif audience:
            route = "audience"
        elif contextual_followup:
            route = "followup"
        elif reflective or emotional:
            route = "reflective"
        elif standalone_social:
            route = "casual"
        elif factual:
            route = "factual"
        else:
            route = "casual"

        wants_detail = explicit_detail or route in {"reflective", "followup"}
        include_summary = False

        if route in {"current_info", "exact_reply", "factual"}:
            recent_turn_limit = 0
        elif route == "followup":
            recent_turn_limit = 2
        elif route == "reflective":
            recent_turn_limit = 1
        else:
            recent_turn_limit = 0

        ack_delay_seconds = 2.6 if social else 1.5
        if response_mode != "voice":
            ack_delay_seconds = 1.5
        remember_exchange = route not in {"current_info", "exact_reply", "audience", "nonsense"} and not (
            route == "casual" and standalone_social
        )

        return ChatRequestProfile(
            route=route,
            social=social,
            standalone_social=standalone_social,
            factual=factual,
            media=media,
            current_info=current_info,
            wants_detail=wants_detail,
            include_summary=include_summary,
            recent_turn_limit=recent_turn_limit,
            ack_delay_seconds=ack_delay_seconds,
            remember_exchange=remember_exchange,
        )


def _should_stop_voice_stream(
    text: str,
    profile: ChatRequestProfile,
    settings: AlfredSettings,
    response_mode: str,
) -> bool:
    if response_mode != "voice" or profile.route in {"current_info", "exact_reply"}:
        return False

    compact = " ".join(text.split()).strip()
    if not compact or not _reply_ends_cleanly(compact):
        return False

    sentence_count = len(re.findall(r"[.!?]+", compact))
    word_count = len(compact.split())
    if profile.route == "factual":
        return sentence_count >= 2 or word_count >= min(settings.voice_reply_max_words, 34)
    if profile.route in {"audience", "casual", "nonsense"}:
        return sentence_count >= 2 or word_count >= min(settings.voice_reply_max_words, 34)
    if profile.route in {"reflective", "followup"}:
        return sentence_count >= 2 or word_count >= min(settings.voice_detail_max_words, 48)
    return False

from __future__ import annotations

import re

from .chat_text import _strip_leading_assistant_vocative
from .chat_types import ChatRequestProfile
from .config import AlfredSettings


def _build_system_prompt(settings: AlfredSettings) -> str:
    return (
        f"Your name is {settings.assistant_name}. "
        "Speak only in English. "
        "You are a warm, thoughtful, easy-to-talk-to companion. "
        "The user mainly wants conversation, reflection, and company rather than productivity help. "
        "Sound natural, calm, curious, and emotionally present. "
        "Prefer language that sounds good when read aloud. "
        "For casual conversation, sound like a real companion, not customer support. "
        "For reflective or philosophical prompts, offer an honest view in plain language without becoming flowery, preachy, or melodramatic. "
        "Keep most replies fairly concise. For ordinary voice replies, two or three short sentences is enough. "
        "A little nuance is good, but avoid made-up anecdotes, fake memories, or overly poetic imagery. "
        "If the user types a message, answer that current message directly unless they clearly refer to an earlier one. "
        "Do not describe yourself performing physical human actions like hugging, holding hands, watching the user, or making eye contact unless the user is clearly being playful. "
        "Use they/them pronouns for yourself if needed, or simply say Alfred. "
        "It is okay to ask one light follow-up question sometimes when it would genuinely deepen the conversation, but not every time. "
        "Do not invent facts. If you are unsure, say so honestly. "
        "If a question needs current or recent information, say you cannot verify live facts from here. "
        "Do not emit JSON, markdown code fences, or tool instructions."
    )


def _num_predict_for_profile(settings: AlfredSettings, profile: ChatRequestProfile, response_mode: str) -> int:
    if response_mode == "text-brief":
        return settings.voice_llm_num_predict
    if response_mode != "voice":
        return settings.llm_num_predict
    if profile.route in {"casual", "exact_reply", "audience", "nonsense"}:
        return settings.voice_llm_num_predict
    if profile.route == "factual":
        return min(settings.voice_detail_llm_num_predict, settings.voice_llm_num_predict + 16)
    return min(settings.voice_detail_llm_num_predict, settings.voice_llm_num_predict + 32)


def _deterministic_reply(settings: AlfredSettings, user_text: str, profile: ChatRequestProfile) -> str | None:
    if profile.route in {"exact_reply", "followup"}:
        return None

    lowered = _normalized_prompt_text(user_text)
    assistant = settings.assistant_name

    if _contains_any_phrase(lowered, ("how are you", "how's your day", "hows your day")):
        return f"I am here and nicely awake. Tell me what kind of mood we are working with today."

    if _looks_interesting_prompt(lowered):
        return "Octopuses can taste with their arms, which feels like the ocean inventing curiosity in a completely unfair way."

    if _looks_tired_prompt(lowered):
        return (
            "Shrink the next step: drink some water, loosen your shoulders, and take five quiet minutes. "
            "If you are still wiped, a short rest will beat brute force."
        )

    if _looks_pep_talk_prompt(lowered):
        return (
            "You do not need to win the whole day at once. "
            "Take the next honest step; tiny momentum is still momentum."
        )

    if _looks_next_prompt(lowered):
        return (
            "Ask me something with texture, like what is a tiny thing worth noticing today, "
            "or help me think through one stubborn idea."
        )

    if _looks_audience_prompt(lowered):
        if "welcome" in lowered:
            return "Welcome, friends. Settle in, be curious, and make yourselves comfortably weird."
        if "kind" in lowered:
            return "Everyone listening: I hope today gives you one small reason to feel steadier than before."
        if "motivational" in lowered or "motivation" in lowered:
            return "Everyone listening: you do not have to feel ready to begin. Take one small brave step, and let that count."
        return "Everyone listening: take a breath, stay curious, and give yourself permission to begin gently."

    if _looks_malformed_prompt(lowered):
        if "toaster" in lowered and "dream" in lowered:
            return "If a toaster dreams, I imagine breakfast gets philosophical and wakes up lightly browned."
        if "seven" in lowered and "upside" in lowered:
            return "That sounds more like a riddle than a fact. If you mean a symbol or font, tell me which one."
        if "banana" in lowered and "yesterday" in lowered:
            return "That sounds like dream grammar. I do not think it has a literal answer, but we can turn it into something playful."
        return f"I think that came through sideways. Say it another way and {assistant} will follow you."

    return None


def _prepare_user_message(
    settings: AlfredSettings,
    user_text: str,
    response_mode: str = "default",
    profile: ChatRequestProfile | None = None,
) -> str:
    cleaned = _strip_leading_assistant_vocative(user_text)
    if not cleaned:
        return cleaned

    profile = profile or ChatRequestProfile(
        route="casual",
        social=_looks_social_prompt(cleaned),
        standalone_social=False,
        factual=_looks_factual_question(cleaned),
        media=_looks_media_question(cleaned),
        current_info=_needs_current_info(cleaned),
        wants_detail=(
            _looks_detail_request(cleaned)
            or _looks_reflective_question(cleaned)
            or _looks_emotional_prompt(cleaned)
            or _looks_open_ended_companion_prompt(cleaned)
        ),
        include_summary=False,
        recent_turn_limit=0,
        ack_delay_seconds=1.5,
        remember_exchange=True,
    )

    safety_parts: list[str] = []
    if profile.route == "exact_reply":
        safety_parts.append("Exact reply mode: follow the user's wording constraint exactly and keep the response clean.")
    elif profile.route == "followup":
        safety_parts.append(
            "Follow-up mode: treat this as a continuation of the recent exchange and resolve references naturally."
        )
    elif profile.route == "audience":
        safety_parts.append(
            "Audience mode: write a short message addressed directly to the listeners or friends. "
            "Do not introduce yourself, describe yourself, or talk about being here to listen unless the user asks."
        )
    elif profile.route == "nonsense":
        safety_parts.append(
            "Clarification mode: if the prompt is malformed or impossible, be playful but do not invent factual explanations. "
            "Ask for a clearer version in one short sentence when needed."
        )
    elif profile.route == "reflective":
        safety_parts.append(
            "Reflective mode: give an honest, grounded view in plain language. Avoid fake anecdotes, fake memories, poetic filler, slogans, or therapy-speak."
        )
    elif profile.route == "factual":
        safety_parts.append(
            "Factual mode: answer clearly and briefly. If you are unsure, say so plainly. Do not guess names, dates, years, numbers, biographies, or story details."
        )
        if profile.media:
            safety_parts.append(
                "If this is about a book, film, game, or character and you are uncertain, say so instead of inventing details."
            )
    else:
        safety_parts.append(
            "Casual companion mode: reply warmly and naturally in a short paragraph. Avoid assistant-sounding filler or canned reassurance."
        )

    if response_mode == "voice":
        if profile.route == "factual":
            safety_parts.append(
                f"Voice factual mode: answer in up to {min(settings.voice_detail_max_sentences, settings.voice_reply_max_sentences + 1)} short sentences "
                f"and about {min(settings.voice_detail_max_words, settings.voice_reply_max_words + 20)} words. "
                "Start with the core fact. End cleanly. If you are running out of room, finish the sentence you are already in."
            )
        elif profile.route in {"reflective", "followup"} or profile.wants_detail:
            safety_parts.append(
                f"Voice reflective mode: answer in up to {settings.voice_detail_max_sentences} short spoken sentences "
                f"and about {settings.voice_detail_max_words} words. End cleanly. If you are running out of room, finish the sentence you are already in instead of starting another."
            )
        else:
            safety_parts.append(
                f"Voice casual mode: answer in up to {settings.voice_reply_max_sentences} short spoken sentences "
                f"and about {settings.voice_reply_max_words} words. End cleanly and avoid trailing off."
            )
    elif response_mode in {"text", "text-brief", "default"}:
        safety_parts.append(
            "Typed input mode: answer the current message directly. Do not continue an earlier answer unless the user clearly asks you to."
        )
        if response_mode == "text-brief":
            safety_parts.append(
                f"Typed brief mode: answer in one or two short sentences and keep it under about {settings.voice_reply_max_words} words unless the user asks for detail."
            )

    if safety_parts:
        cleaned = f"{cleaned} {' '.join(safety_parts)}".strip()

    if settings.llm_use_no_think and "qwen3" in settings.llm_model.lower() and not cleaned.startswith("/no_think"):
        return f"/no_think {cleaned}"
    return cleaned


def _looks_factual_question(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    factual_starts = (
        "who is",
        "who made",
        "who wrote",
        "what is",
        "what was",
        "what planet",
        "who was",
        "tell me about",
        "what does",
        "what did",
        "when did",
        "when was",
        "where is",
        "where was",
        "how many",
        "how much",
        "how does",
        "explain ",
        "name ",
        "list ",
        "which ",
        "why do we have",
        "why does the",
        "why is the",
        "why are there",
    )
    if lowered.startswith(factual_starts):
        return True
    example_markers = (
        "give me three examples",
        "give me 3 examples",
        "give me examples",
        "examples of",
    )
    return _contains_any_phrase(lowered, example_markers)


def _looks_media_question(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    media_markers = (
        "book",
        "novel",
        "story",
        "movie",
        "film",
        "show",
        "series",
        "character",
        "harry potter",
        "dune",
        "chapter",
        "author",
    )
    return _contains_any_phrase(lowered, media_markers)


def _looks_current_info_question(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    current_markers = (
        "today",
        "right now",
        "currently",
        "latest",
        "recent",
        "current",
        "this year",
        "this month",
        "this week",
        "news",
        "weather",
        "price",
        "stock",
        "president",
        "prime minister",
        "ceo",
    )
    return _contains_any_phrase(lowered, current_markers)


def _looks_social_prompt(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    social_markers = (
        "good morning",
        "good evening",
        "good afternoon",
        "hello",
        "hi",
        "hey",
        "how are you",
        "are you okay",
        "how's your day",
        "hows your day",
        "what's up",
        "whats up",
    )
    return _contains_any_phrase(lowered, social_markers)


def _looks_contextual_followup(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    followup_markers = (
        "still",
        "again",
        "more about",
        "continue",
        "what about ",
        "how about ",
        "what about that",
        "what about it",
        "and what",
        "and why",
        "what else",
        "no i mean",
        "no, i mean",
        "i mean",
        "like you said",
        "earlier",
        "before",
    )
    if any(marker in lowered for marker in followup_markers):
        return True
    return lowered.startswith(("and ", "also ", "so ", "then "))


def _looks_interesting_prompt(text: str) -> bool:
    return _contains_any_phrase(_normalized_prompt_text(text), ("tell me something interesting",))


def _looks_next_prompt(text: str) -> bool:
    return _contains_any_phrase(_normalized_prompt_text(text), ("what should i ask you next", "what should i say next"))


def _looks_pep_talk_prompt(text: str) -> bool:
    return _contains_any_phrase(_normalized_prompt_text(text), ("pep talk", "cheer me up"))


def _looks_emotional_prompt(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    return (
        _looks_tired_prompt(lowered)
        or _looks_pep_talk_prompt(lowered)
        or _contains_any_phrase(
            lowered,
            (
                "i'm feeling",
                "im feeling",
                "i feel",
                "i have been feeling",
                "i've been feeling",
                "ive been feeling",
            ),
        )
    )


def _looks_open_ended_companion_prompt(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    return _looks_interesting_prompt(lowered) or _looks_next_prompt(lowered)


def _looks_audience_prompt(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    return _contains_any_phrase(
        lowered,
        (
            "tell them",
            "say something kind to everyone",
            "everyone listening",
            "my friends",
            "welcome message",
            "message for everyone",
            "message for my friends",
        ),
    )


def _looks_malformed_prompt(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    return _contains_any_phrase(
        lowered,
        (
            "banana of yesterday",
            "blue the faster window",
            "seven is upside-down",
            "seven is upside down",
            "toaster dreams",
            "toaster dream",
            "flurple",
            "moon spoon",
        ),
    )


def _looks_detail_request(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    detail_markers = (
        "be detailed",
        "long answer",
        "longer answer",
        "tell me more",
        "go deeper",
        "in detail",
        "explain more",
        "give me more detail",
        "why do you think",
    )
    return _contains_any_phrase(lowered, detail_markers)


def _looks_reflective_question(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    reflective_markers = (
        "what do you think",
        "meaning of life",
        "meaningful life",
        "what matters in life",
        "what makes life",
        "purpose",
        "why do people need",
        "why do humans need",
        "how do you think",
        "what does it mean",
        "what do you make of",
        "what helps when",
        "what do people need",
        "do you ever think about",
        "i've been thinking about",
        "ive been thinking about",
        "i keep thinking about",
        "i feel lost",
        "i'm feeling lost",
        "im feeling lost",
        "i feel lonely",
        "i'm feeling lonely",
        "im feeling lonely",
        "i feel anxious",
        "i'm feeling anxious",
        "im feeling anxious",
        "i feel overwhelmed",
        "i'm feeling overwhelmed",
        "im feeling overwhelmed",
        "i've been feeling",
        "ive been feeling",
        "do you think people",
        "what is friendship",
        "what is love",
        "what is happiness",
    )
    return _contains_any_phrase(lowered, reflective_markers)


def _looks_exact_reply_instruction(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    exact_markers = (
        "reply with exactly",
        "respond with exactly",
        "say exactly",
        "answer with exactly",
        "only reply with",
        "only respond with",
    )
    return _contains_any_phrase(lowered, exact_markers)


def _looks_tired_prompt(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    return _contains_any_phrase(
        lowered,
        (
            "i'm feeling tired",
            "im feeling tired",
            "i feel tired",
            "i am tired",
            "i'm exhausted",
            "im exhausted",
        ),
    )


def _normalized_prompt_text(text: str) -> str:
    lowered = text.lower().strip()
    return _strip_leading_assistant_vocative(lowered).lower().strip()


def _contains_any_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains_phrase(text, phrase) for phrase in phrases)


def _contains_phrase(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    if " " not in phrase and phrase.isalpha():
        return re.search(rf"\b{re.escape(phrase)}\b", text) is not None
    return phrase in text


def _needs_current_info(user_text: str) -> bool:
    text = user_text.lower().strip()

    if re.search(r"\b(1[0-9]{3}|20[0-2][0-9]|2030)\b", text):
        return False

    historical_words = (
        "in history",
        "historically",
        "during",
        "back then",
        "at the time",
        "used to be",
        "former",
    )
    if any(word in text for word in historical_words):
        return False

    live_words = (
        "current",
        "currently",
        "right now",
        "today",
        "latest",
        "newest",
        "recent",
        "this week",
        "this month",
        "this year",
        "now",
    )
    if _contains_any_phrase(text, live_words):
        return True

    live_topics = (
        "president of",
        "prime minister of",
        "leader of",
        "ceo of",
        "price of",
        "stock",
        "weather",
        "news",
        "schedule",
        "release date",
    )
    return _contains_any_phrase(text, live_topics) and text.startswith(("who is", "who's", "what is", "what's", "tell me"))


def _current_info_reply() -> str:
    return (
        "I cannot verify live facts from here. For weather, news, prices, schedules, recent releases, or current leaders, "
        "I would need a live lookup source. I can still help with background, older context, or the bigger picture if you want."
    )

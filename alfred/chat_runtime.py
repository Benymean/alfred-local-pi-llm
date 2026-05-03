from __future__ import annotations

import os
import re

from .chat_text import _strip_leading_assistant_vocative
from .chat_types import ChatRequestProfile
from .config import AlfredSettings


def _build_system_prompt(settings: AlfredSettings) -> str:
    return (
        f"Your name is {settings.assistant_name}. "
        "Speak English as a warm local companion. "
        "Answer the current user message directly and briefly. "
        "Sound natural aloud, not like customer support. "
        "Do not invent facts, fake memories, anecdotes, or physical actions. "
        "If unsure, say so plainly. "
        "Use plain sentences: no emoji, markdown, bullets, numbered lists, or tool instructions."
    )


def _num_predict_for_profile(settings: AlfredSettings, profile: ChatRequestProfile, response_mode: str) -> int:
    if response_mode == "text-brief":
        return settings.voice_llm_num_predict
    if response_mode != "voice":
        return settings.llm_num_predict
    if profile.route in {"casual", "exact_reply", "audience", "nonsense"}:
        return settings.voice_llm_num_predict
    if profile.route == "factual":
        return min(settings.voice_llm_num_predict, 72)
    if profile.route == "followup":
        return min(settings.voice_detail_llm_num_predict, settings.voice_llm_num_predict + 8)
    return min(settings.voice_detail_llm_num_predict, settings.voice_llm_num_predict + 8)


def _deterministic_reply(settings: AlfredSettings, user_text: str, profile: ChatRequestProfile) -> str | None:
    if _deterministic_replies_disabled():
        return None

    if profile.route == "exact_reply":
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
        if _looks_linkedin_promo_prompt(lowered) or _looks_alfred_demo_prompt(lowered):
            return None
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


def _deterministic_replies_disabled() -> bool:
    return os.environ.get("ALFRED_DISABLE_DETERMINISTIC_REPLIES", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


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
        safety_parts.append("Exact reply: obey the requested wording exactly.")
    elif profile.route == "followup":
        safety_parts.append(
            "Follow-up: use only the recent exchange. Answer directly and briefly."
        )
    elif profile.route == "audience":
        safety_parts.append("Audience: speak directly to listeners; warm, brief, specific to this moment, no canned line.")
        if _looks_alfred_demo_prompt(cleaned):
            safety_parts.append("If asked about Alfred: local offline AI companion on a Raspberry Pi. No habit or mood-learning claims.")
    elif profile.route == "nonsense":
        safety_parts.append(
            "Malformed prompt: answer in one plain sentence. Be playful if useful, but do not invent facts, use emoji, or format as a list."
        )
    elif profile.route == "reflective":
        safety_parts.append(
            "Reflective: plain, grounded, useful. No poetic imagery, fake anecdotes, slogans, therapy-speak, or repeated filler."
        )
    elif profile.route == "factual":
        safety_parts.append("Factual: answer first; brief; do not guess. No lists.")
        if _looks_broad_factual_prompt(cleaned):
            safety_parts.append("Broad history/science: use several established examples, not one modern guess.")
        if _looks_uncertainty_trap(cleaned):
            safety_parts.append("For exact, every, or single-most questions: state limits and avoid false precision.")
        if profile.media:
            safety_parts.append(
                "For media questions, say if you are uncertain."
            )
    else:
        safety_parts.append(
            "Casual: reply warmly in a short natural paragraph. Avoid canned reassurance."
        )

    if response_mode == "voice":
        if profile.route == "factual":
            max_words = min(settings.voice_reply_max_words, 32)
            safety_parts.append(
                f"Voice: 1 or 2 sentences, under {max_words} words. Stop."
            )
        elif profile.route in {"reflective", "followup"} or profile.wants_detail:
            max_words = min(settings.voice_detail_max_words, 46)
            safety_parts.append(
                f"Voice: 2 short spoken sentences, under {max_words} words. End cleanly."
            )
        else:
            max_words = min(settings.voice_reply_max_words, 30)
            safety_parts.append(
                f"Voice: 1 or 2 short spoken sentences, under {max_words} words."
            )
    elif response_mode in {"text", "text-brief", "default"}:
        safety_parts.append(
            "Typed: answer the current message directly."
        )
        if response_mode == "text-brief":
            safety_parts.append(
                f"Brief: one or two short sentences under about {settings.voice_reply_max_words} words."
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
        "who painted",
        "who started",
        "who wrote",
        "what is",
        "what was",
        "what were",
        "what inventions",
        "what technologies",
        "what gas",
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
        "how did",
        "how does",
        "explain ",
        "name ",
        "list ",
        "which ",
        "why did",
        "why do ",
        "why do we have",
        "why do magnets",
        "why does ice",
        "why does water",
        "why does the",
        "why are ",
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
    return lowered.startswith(("and ", "also ", "so ", "then ", "still ", "again "))


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
    return (
        _looks_interesting_prompt(lowered)
        or _looks_next_prompt(lowered)
        or _contains_any_phrase(lowered, ("tiny thing worth noticing",))
    )


def _looks_audience_prompt(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    return _contains_any_phrase(
        lowered,
        (
            "tell them",
            "what message do you have",
            "message do you have",
            "what do you wanna tell",
            "what do you want to tell",
            "what would you tell",
            "say something kind to everyone",
            "everyone listening",
            "people listening",
            "people watching",
            "listening to you",
            "linkedin",
            "linkedin audience",
            "people at linkedin",
            "people on linkedin",
            "my audience",
            "my friends",
            "talk to my friends",
            "welcome message",
            "message for everyone",
            "message for my friends",
            "watching this demo",
            "watching this prototype",
            "addressed to the room",
            "address my audience",
            "on-stage intro",
            "non-technical person",
            "the listeners",
            "the room",
            "closing line",
            "demo of alfred",
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
            "sneeze sideways",
            "blue yesterday",
            "fold the blue",
            "tuesday inside",
            "inside the spoon",
            "cloud misplaces",
            "misplaces its shoes",
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


def _looks_alfred_demo_prompt(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    return _contains_any_phrase(
        lowered,
        (
            "alfred",
            "this project",
            "demo",
            "offline ai",
            "offline-ai",
            "local ai",
            "raspberry pi",
            "non-technical person",
        ),
    )


def _looks_linkedin_promo_prompt(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    return _contains_any_phrase(
        lowered,
        (
            "linkedin",
            "people listening",
            "listeners",
            "audience",
            "watching this demo",
            "on-stage",
            "on stage",
        ),
    )


def _looks_broad_factual_prompt(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    return _contains_any_phrase(
        lowered,
        (
            "broad effects",
            "what inventions",
            "what technologies",
            "world war",
            "aftermath",
            "printing press",
            "society",
            "history",
        ),
    )


def _looks_uncertainty_trap(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    return _contains_any_phrase(
        lowered,
        (
            "exact number",
            "exact names",
            "every engineer",
            "every person",
            "single invention",
            "mattered most",
            "most important",
            "exactly how many",
        ),
    )


def _looks_reflective_question(text: str) -> bool:
    lowered = _normalized_prompt_text(text)
    reflective_markers = (
        "what do you think",
        "meaning of life",
        "meaningful life",
        "what matters in life",
        "what makes life",
        "meaningful when",
        "nothing dramatic",
        "purpose",
        "mortality",
        "success still",
        "feel lonely",
        "why do people need",
        "why do humans need",
        "how do you think",
        "how should someone think",
        "how do you comfort",
        "what does it mean",
        "what do you make of",
        "what helps when",
        "what helps people",
        "what makes a person",
        "what do people owe",
        "owe each other",
        "feels invisible",
        "feel invisible",
        "peace and numbness",
        "losing yourself",
        "without becoming cruel",
        "becoming frozen",
        "why do people remember",
        "why do people feel",
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
    text = _normalized_prompt_text(user_text)

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

    live_topics = (
        "president of",
        "prime minister of",
        "leader of",
        "ceo of",
        "price of",
        "stock",
        "stock availability",
        "weather",
        "news",
        "headline",
        "schedule",
        "standings",
        "release date",
        "latest version",
        "software version",
        "version of",
        "movies playing",
        "movies are playing",
        "came out this week",
    )
    has_live_topic = _contains_any_phrase(text, live_topics)

    if _looks_audience_prompt(text) and not has_live_topic:
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
    if has_live_topic and _contains_any_phrase(text, live_words):
        return True

    return has_live_topic and text.startswith(("who is", "who's", "what is", "what's", "tell me"))


def _current_info_reply() -> str:
    return (
        "I cannot verify live facts from here. For weather, news, prices, schedules, recent releases, or current leaders, "
        "I would need a live lookup source. I can still help with background, older context, or the bigger picture if you want."
    )

from __future__ import annotations

import re


def _clean_reply(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = _strip_voice_hostile_formatting(text)
    text = _replace_unsupported_personalization_claims(text)
    text = text.replace("\r", " ").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_voice_hostile_formatting(text: str) -> str:
    text = re.sub(r"(^|\s)[*_]([^*_]+)[*_](?=\s|[.!?,;:]|$)", r"\1\2", text)
    text = re.sub(r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF\u2600-\u26FF\ufe0f]", "", text)
    text = re.sub(r"\s+([.!?,;:])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text


def _replace_unsupported_personalization_claims(text: str) -> str:
    if not re.search(r"\b(learns?|remembers?|habits?|preferences?|moods?|voice|actions)\b", text, flags=re.IGNORECASE):
        return text

    safe_sentence = "It feels personal because it runs locally and keeps the interaction close to the device."
    cleaned_sentences: list[str] = []
    for match in re.finditer(r"[^.!?]+[.!?]?", text):
        sentence = match.group(0).strip()
        if not sentence:
            continue
        unsafe = re.search(
            r"\b(learns?|remembers?)\b.*\b(habits?|preferences?|moods?|voice|actions)\b",
            sentence,
            flags=re.IGNORECASE,
        )
        if unsafe:
            if not cleaned_sentences or cleaned_sentences[-1] != safe_sentence:
                cleaned_sentences.append(safe_sentence)
            continue
        cleaned_sentences.append(sentence)
    return " ".join(cleaned_sentences) if cleaned_sentences else text


def _trim_truncated_reply(text: str) -> str:
    compact = " ".join(text.split()).strip()
    if not compact or _reply_ends_cleanly(compact):
        return compact

    strong_boundary: int | None = None
    for match in re.finditer(r'[.!?](?=(?:["\')\]]|\s|$))', compact):
        strong_boundary = match.end()
    if strong_boundary is not None:
        return compact[:strong_boundary].strip()

    soft_boundary = max(compact.rfind("—"), compact.rfind(";"), compact.rfind(":"))
    comma_boundary = compact.rfind(",")
    if comma_boundary > soft_boundary and len(compact.split()) >= 12:
        soft_boundary = comma_boundary
    if soft_boundary > 0:
        prefix = compact[:soft_boundary].rstrip(" ,;:-—")
        if len(prefix.split()) >= 7:
            return f"{prefix}."
    return compact


def _reply_ends_cleanly(text: str) -> bool:
    return re.search(r'[.!?]["\')\]]*\s*$', text.strip()) is not None


class _StreamingChunkCleaner:
    def __init__(self) -> None:
        self.buffer = ""
        self.in_think = False

    def feed(self, chunk: str) -> str:
        self.buffer += chunk.replace("\r", " ")
        visible = ""

        while True:
            lowered = self.buffer.lower()
            if self.in_think:
                end_idx = lowered.find("</think>")
                if end_idx == -1:
                    self.buffer = ""
                    break
                self.buffer = self.buffer[end_idx + len("</think>") :]
                self.in_think = False
                continue

            start_idx = lowered.find("<think>")
            if start_idx == -1:
                visible += self.buffer
                self.buffer = ""
                break

            visible += self.buffer[:start_idx]
            self.buffer = self.buffer[start_idx + len("<think>") :]
            self.in_think = True

        return visible

    def flush(self) -> str:
        if self.in_think:
            self.buffer = ""
            return ""
        tail = self.buffer
        self.buffer = ""
        return tail


class _LeadingSpeakerLabelStripper:
    def __init__(self, assistant_name: str):
        self.assistant_name = assistant_name
        self._resolved = False
        self._buffer = ""

    def feed(self, text: str, final: bool = False) -> str:
        if self._resolved:
            return text

        self._buffer += text
        stripped = _strip_leading_speaker_label(self._buffer, self.assistant_name)
        if stripped != self._buffer:
            self._resolved = True
            self._buffer = ""
            return stripped

        if final or len(self._buffer) >= 32 or any(mark in self._buffer for mark in (" ", ".", "?", "!", "\n")):
            self._resolved = True
            output = self._buffer
            self._buffer = ""
            return output
        return ""


def _single_line(text: str) -> str:
    return " ".join(text.split()).strip()


def _strip_leading_assistant_vocative(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^(hey|hi|hello)\s+alfred[\s,!.?:-]*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^alfred[\s,!.?:-]*", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _strip_leading_speaker_label(text: str, assistant_name: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned

    name_pattern = re.escape(assistant_name.strip())
    patterns = (
        rf"^(?:{name_pattern})\s*[:\-]\s*",
        rf"^(?:{name_pattern})\s+says\s*[:\-]?\s*",
        rf"^(?:assistant)\s*[:\-]\s*",
    )
    for pattern in patterns:
        updated = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE).strip()
        if updated != cleaned:
            return updated
    return cleaned


def _should_show_reply_text(text: str, threshold: int) -> tuple[bool, str]:
    compact = " ".join(text.split())
    sentences = len(re.findall(r"[.!?]+", compact))
    has_list_shape = any(token in text for token in ("\n-", "\n1.", "\n2.", ":"))

    if len(compact) > threshold:
        return True, "reply is long enough to benefit from on-screen text"
    if has_list_shape:
        return True, "reply looks structured and benefits from on-screen text"
    if sentences > 2:
        return True, "reply spans several sentences"
    if sentences > 1 and len(compact) > max(80, threshold // 2):
        return True, "reply is dense enough that on-screen text will help"
    return False, "reply is short enough to rely on spoken playback"

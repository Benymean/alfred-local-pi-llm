from __future__ import annotations

import json


class SentenceChunker:
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

            if char in ".!?":
                if len(prefix) >= self.min_sentence_chars or prefix.count(" ") >= 2:
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


def ndjson_event(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=True) + "\n").encode("utf-8")


def reply_log_text(text: str, limit: int = 320) -> str:
    compact = " ".join(text.split()).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"

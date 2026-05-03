from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol


class ChatBackend(Protocol):
    def generate_reply(self, messages: list[dict[str, str]], *, num_predict: int | None = None) -> str:
        ...

    def stream_reply(self, messages: list[dict[str, str]], *, num_predict: int | None = None) -> Iterator[str]:
        ...


@dataclass(slots=True)
class AssistantReply:
    text: str
    show_text: bool
    reason: str


@dataclass(slots=True)
class ChatRequestProfile:
    route: str
    social: bool
    standalone_social: bool
    factual: bool
    media: bool
    current_info: bool
    wants_detail: bool
    include_summary: bool
    recent_turn_limit: int | None
    ack_delay_seconds: float
    remember_exchange: bool

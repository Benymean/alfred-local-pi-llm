from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import textwrap


@dataclass(slots=True)
class MemoryTurn:
    role: str
    content: str


@dataclass(slots=True)
class AlfredMemory:
    path: Path
    recent_exchange_limit: int
    summary_char_limit: int
    summary: str = ""
    recent_turns: list[MemoryTurn] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path, recent_exchange_limit: int, summary_char_limit: int) -> "AlfredMemory":
        if path.exists():
            try:
                payload = json.loads(path.read_text())
                turns = [MemoryTurn(**turn) for turn in payload.get("recent_turns", [])]
                return cls(
                    path=path,
                    recent_exchange_limit=recent_exchange_limit,
                    summary_char_limit=summary_char_limit,
                    summary=payload.get("summary", ""),
                    recent_turns=turns,
                )
            except Exception:
                pass
        return cls(path=path, recent_exchange_limit=recent_exchange_limit, summary_char_limit=summary_char_limit)

    def save(self) -> None:
        payload = {
            "summary": self.summary,
            "recent_turns": [asdict(turn) for turn in self.recent_turns],
        }
        self.path.write_text(json.dumps(payload, indent=2))

    def build_messages(
        self,
        system_prompt: str,
        user_text: str,
        *,
        include_summary: bool = True,
        recent_turn_limit: int | None = None,
    ) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": _single_line(system_prompt)}]
        if include_summary and self.summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"Conversation summary from earlier chats: {_single_line(self.summary)}",
                }
            )
        turns = self.recent_turns
        if recent_turn_limit is not None:
            capped = max(0, recent_turn_limit * 2)
            turns = turns[-capped:] if capped else []
        messages.extend({"role": turn.role, "content": _single_line(turn.content)} for turn in turns)
        messages.append({"role": "user", "content": _single_line(user_text)})
        return messages

    def record_exchange(self, user_text: str, assistant_text: str) -> None:
        self.recent_turns.extend(
            [
                MemoryTurn(role="user", content=_single_line(user_text)),
                MemoryTurn(role="assistant", content=_single_line(assistant_text)),
            ]
        )
        self._compress_history()
        self.save()

    def reset(self) -> None:
        self.summary = ""
        self.recent_turns = []
        self.save()

    def _compress_history(self) -> None:
        max_turns = self.recent_exchange_limit * 2
        if len(self.recent_turns) <= max_turns:
            return

        overflow = self.recent_turns[:-max_turns]
        self.recent_turns = self.recent_turns[-max_turns:]
        folded = self._fold_turns(overflow)
        if not folded:
            return

        combined = f"{self.summary} {folded}".strip() if self.summary else folded
        self.summary = combined[-self.summary_char_limit :]

    def _fold_turns(self, turns: list[MemoryTurn]) -> str:
        if not turns:
            return ""

        lines: list[str] = []
        pending_user: str | None = None
        for turn in turns:
            snippet = textwrap.shorten(" ".join(turn.content.split()), width=120, placeholder="...")
            if turn.role == "user":
                pending_user = snippet
            elif turn.role == "assistant":
                if pending_user:
                    lines.append(f"User asked about '{pending_user}'. Alfred replied '{snippet}'.")
                    pending_user = None
                else:
                    lines.append(f"Alfred said '{snippet}'.")

        if pending_user:
            lines.append(f"User asked about '{pending_user}'.")

        return " ".join(lines)


def _single_line(text: str) -> str:
    return " ".join(text.split()).strip()

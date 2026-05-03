from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    response_mode: str = "default"
    synthesize_audio: bool = True
    turn_id: str | None = None
    turn_started_at_ms: float | None = None

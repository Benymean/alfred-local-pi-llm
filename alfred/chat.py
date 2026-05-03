from __future__ import annotations

from .chat_backends import HailoChatBackend, MockChatBackend
from .chat_engine import AlfredChatEngine
from .chat_runtime import _num_predict_for_profile
from .chat_text import _reply_ends_cleanly, _trim_truncated_reply
from .chat_types import AssistantReply, ChatBackend, ChatRequestProfile


__all__ = [
    "AlfredChatEngine",
    "AssistantReply",
    "ChatBackend",
    "ChatRequestProfile",
    "HailoChatBackend",
    "MockChatBackend",
    "_num_predict_for_profile",
    "_reply_ends_cleanly",
    "_trim_truncated_reply",
]

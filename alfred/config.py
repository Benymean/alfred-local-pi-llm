from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_path(name: str, default_path: Path) -> Path:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default_path
    return Path(raw).expanduser()


@dataclass(slots=True)
class AlfredSettings:
    assistant_name: str = "Alfred"
    llm_url: str = field(default_factory=lambda: os.environ.get("ALFRED_LLM_URL", "http://127.0.0.1:8000/api/chat"))
    llm_model: str = field(default_factory=lambda: os.environ.get("ALFRED_LLM_MODEL", "qwen3:1.7b"))
    llm_temperature: float = field(default_factory=lambda: float(os.environ.get("ALFRED_LLM_TEMPERATURE", "0.55")))
    llm_num_predict: int = field(default_factory=lambda: int(os.environ.get("ALFRED_LLM_NUM_PREDICT", "96")))
    llm_num_ctx: int = field(default_factory=lambda: int(os.environ.get("ALFRED_LLM_NUM_CTX", "3072")))
    llm_timeout_seconds: float = field(default_factory=lambda: float(os.environ.get("ALFRED_LLM_TIMEOUT_SECONDS", "180")))
    llm_keep_alive: str | None = field(
        default_factory=lambda: ((os.environ.get("ALFRED_LLM_KEEP_ALIVE") or "").strip() or None)
    )
    llm_use_no_think: bool = field(default_factory=lambda: _env_flag("ALFRED_LLM_USE_NO_THINK", True))
    voice_llm_num_predict: int = field(default_factory=lambda: int(os.environ.get("ALFRED_VOICE_LLM_NUM_PREDICT", "72")))
    voice_detail_llm_num_predict: int = field(
        default_factory=lambda: int(os.environ.get("ALFRED_VOICE_DETAIL_LLM_NUM_PREDICT", "96"))
    )
    voice_reply_max_words: int = field(default_factory=lambda: int(os.environ.get("ALFRED_VOICE_REPLY_MAX_WORDS", "45")))
    voice_reply_max_sentences: int = field(default_factory=lambda: int(os.environ.get("ALFRED_VOICE_REPLY_MAX_SENTENCES", "2")))
    voice_detail_max_words: int = field(
        default_factory=lambda: int(os.environ.get("ALFRED_VOICE_DETAIL_MAX_WORDS", "72"))
    )
    voice_detail_max_sentences: int = field(
        default_factory=lambda: int(os.environ.get("ALFRED_VOICE_DETAIL_MAX_SENTENCES", "4"))
    )
    memory_path: Path = field(
        default_factory=lambda: _env_path(
            "ALFRED_MEMORY_PATH",
            PROJECT_ROOT / ".alfred-state" / "alfred_memory_touch.json",
        )
    )
    transcript_char_threshold: int = field(default_factory=lambda: int(os.environ.get("ALFRED_TEXT_THRESHOLD", "140")))
    recent_exchange_limit: int = field(default_factory=lambda: int(os.environ.get("ALFRED_RECENT_EXCHANGES", "6")))
    summary_char_limit: int = field(default_factory=lambda: int(os.environ.get("ALFRED_SUMMARY_CHAR_LIMIT", "1600")))
    piper_cmd: Path = field(default_factory=lambda: _env_path("ALFRED_PIPER_CMD", PROJECT_ROOT / "piper" / "piper"))
    piper_model: Path = field(default_factory=lambda: _env_path("ALFRED_PIPER_MODEL", PROJECT_ROOT / "piper" / "bmo.onnx"))
    tts_tempo: float = field(default_factory=lambda: float(os.environ.get("ALFRED_TTS_TEMPO", "1.0")))
    whisper_cmd: Path = field(
        default_factory=lambda: _env_path("ALFRED_WHISPER_CMD", PROJECT_ROOT / "whisper.cpp" / "build" / "bin" / "whisper-cli")
    )
    whisper_mode: str = field(default_factory=lambda: os.environ.get("ALFRED_WHISPER_MODE", "auto").strip().lower())
    whisper_model: Path = field(
        default_factory=lambda: _env_path("ALFRED_WHISPER_MODEL", PROJECT_ROOT / "models" / "ggml-base.en.bin")
    )
    whisper_fast_model: Path = field(
        default_factory=lambda: _env_path("ALFRED_WHISPER_FAST_MODEL", PROJECT_ROOT / "models" / "ggml-tiny.en.bin")
    )
    ffmpeg_cmd: str = field(default_factory=lambda: os.environ.get("ALFRED_FFMPEG_CMD", "ffmpeg"))
    audio_temp_dir: Path = field(default_factory=lambda: _env_path("ALFRED_AUDIO_TEMP_DIR", PROJECT_ROOT / ".alfred-audio"))

    def ensure_runtime_paths(self) -> None:
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.audio_temp_dir.mkdir(parents=True, exist_ok=True)

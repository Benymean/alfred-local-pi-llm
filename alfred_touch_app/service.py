from __future__ import annotations

from dataclasses import asdict
import logging
import os
from pathlib import Path
import queue
import random
import threading
import time
import uuid
import sys
from typing import Iterator

from fastapi import HTTPException
import requests

from alfred.audio import WhisperCppSTT, resolve_executable
from alfred.chat import (
    AlfredChatEngine,
    HailoChatBackend,
    MockChatBackend,
    _num_predict_for_profile,
    _reply_ends_cleanly,
    _trim_truncated_reply,
)
from alfred.chat_text import _clean_stream_sentence_for_speech
from alfred.config import AlfredSettings
from alfred.memory import AlfredMemory

from .api_models import ChatRequest
from .paths import EARLY_ACK_PHRASES, ROOT_DIR
from .streaming import SentenceChunker, join_stream_text, ndjson_event, reply_log_text
from .tts import PiperFileSynthesizer, StreamingTtsWorker


logger = logging.getLogger(__name__)


def _normalized_stream_text(text: str) -> str:
    return " ".join(text.split()).strip()


def _missing_tts_tail(final_text: str, spoken_parts: list[str]) -> str:
    final_compact = _normalized_stream_text(final_text)
    spoken_compact = _normalized_stream_text(" ".join(spoken_parts))
    if not final_compact or not spoken_compact:
        return final_compact if final_compact and not spoken_compact else ""
    if final_compact == spoken_compact:
        return ""
    if final_compact.startswith(spoken_compact):
        tail = final_compact[len(spoken_compact) :].lstrip()
        return tail if any(char.isalnum() for char in tail) else ""
    return ""


class AlfredTouchService:
    def __init__(self):
        self.started_at = time.time()
        self.last_error: str | None = None
        self.last_error_at: float | None = None
        self._restart_requested = False
        self.settings = AlfredSettings()
        if "ALFRED_MEMORY_PATH" not in os.environ:
            self.settings.memory_path = self._resolve_local_path(
                os.environ.get("ALFRED_TOUCH_MEMORY_PATH", ".alfred-state/alfred_memory_touch.json")
            )
        self.settings.ensure_runtime_paths()

        self.web_audio_dir = self.settings.audio_temp_dir / "touch-web"
        self.web_audio_dir.mkdir(parents=True, exist_ok=True)

        backend_name = os.environ.get("ALFRED_TOUCH_BACKEND", "live").strip().lower()
        memory = AlfredMemory.load(
            self.settings.memory_path,
            recent_exchange_limit=self.settings.recent_exchange_limit,
            summary_char_limit=self.settings.summary_char_limit,
        )
        backend = MockChatBackend(self.settings.assistant_name) if backend_name == "mock" else HailoChatBackend(self.settings)
        self.chat_engine = AlfredChatEngine(self.settings, backend, memory)
        self.selected_whisper_model, self.selected_whisper_mode = self._resolve_whisper_model()
        self.stt = WhisperCppSTT(
            self.settings.whisper_cmd,
            self.selected_whisper_model,
            ffmpeg_cmd=self.settings.ffmpeg_cmd,
        )
        self.synthesizer = PiperFileSynthesizer(
            self.settings.piper_cmd,
            self.settings.piper_model,
            self.web_audio_dir,
            ffmpeg_cmd=self.settings.ffmpeg_cmd,
            tempo=self.settings.tts_tempo,
        )
        self.ack_audio_cache = self._prime_ack_audio_cache()
        self._chat_lock = threading.Lock()
        logger.info(
            "Alfred touch config: model=%s llm_num_predict=%s voice_num_predict=%s voice_detail_num_predict=%s num_ctx=%s keep_alive=%s no_think=%s voice_words=%s detail_words=%s whisper_mode=%s whisper_model=%s tts_tempo=%s",
            self.settings.llm_model,
            self.settings.llm_num_predict,
            self.settings.voice_llm_num_predict,
            self.settings.voice_detail_llm_num_predict,
            self.settings.llm_num_ctx,
            self.settings.llm_keep_alive,
            self.settings.llm_use_no_think,
            self.settings.voice_reply_max_words,
            self.settings.voice_detail_max_words,
            self.selected_whisper_mode,
            self.selected_whisper_model,
            self.settings.tts_tempo,
        )

    def bootstrap_payload(self) -> dict:
        return {
            "assistant_name": self.settings.assistant_name,
            "recent_turns": [asdict(turn) for turn in self.chat_engine.memory.recent_turns[-12:]],
            "memory_path": str(self.settings.memory_path),
            "voice_replies_default": True,
        }

    def health_payload(self) -> dict:
        llm_status = "unknown"
        llm_error = None
        try:
            base_url = self.settings.llm_url.replace("/api/chat", "")
            response = requests.get(f"{base_url}/api/tags", timeout=2)
            llm_status = "online" if response.status_code == 200 else f"error ({response.status_code})"
        except Exception as exc:  # pragma: no cover - depends on local runtime
            llm_status = "offline"
            llm_error = str(exc)

        return {
            "assistant_name": self.settings.assistant_name,
            "backend_status": "restarting" if self._restart_requested else "online",
            "llm_model": self.settings.llm_model,
            "llm_status": llm_status,
            "llm_error": llm_error,
            "stt_ready": bool(resolve_executable(self.settings.whisper_cmd, "whisper-cli")) and self.selected_whisper_model.exists(),
            "stt_mode": self.selected_whisper_mode,
            "stt_model": str(self.selected_whisper_model),
            "tts_ready": bool(resolve_executable(self.settings.piper_cmd, "piper")) and self.settings.piper_model.exists(),
            "uptime_seconds": int(time.time() - self.started_at),
            "last_error": self.last_error,
            "last_error_at": self.last_error_at,
        }

    def reply(self, request: ChatRequest) -> dict:
        cleaned = request.message.strip()
        if not cleaned:
            self._record_error("Chat request failed because the message was empty.")
            raise HTTPException(status_code=400, detail="Message cannot be empty.")

        response_mode = request.response_mode if request.response_mode in {"default", "voice", "text", "text-brief"} else "default"
        turn_id = (request.turn_id or "").strip() or f"turn-{uuid.uuid4().hex[:8]}"
        turn_started_at_ms = request.turn_started_at_ms
        request_started_at = time.perf_counter()
        num_predict = self._effective_num_predict(cleaned, response_mode)

        logger.info(
            "[perf %s] chat start mode=%s chars=%d num_predict=%d synthesize_audio=%s text=%r",
            turn_id,
            response_mode,
            len(cleaned),
            num_predict,
            request.synthesize_audio,
            cleaned[:160],
        )
        llm_started_at = time.perf_counter()
        with self._chat_lock:
            reply = self.chat_engine.reply(cleaned, response_mode=response_mode)
        llm_seconds = time.perf_counter() - llm_started_at
        logger.info(
            "[perf %s] llm done in %.2fs words=%d chars=%d",
            turn_id,
            llm_seconds,
            len(reply.text.split()),
            len(reply.text),
        )
        logger.info("[perf %s] answer: %r", turn_id, reply_log_text(reply.text))

        audio_url = None
        tts_seconds = 0.0
        if request.synthesize_audio:
            logger.info("[perf %s] tts start chars=%d", turn_id, len(reply.text))
            tts_started_at = time.perf_counter()
            audio_path = self.synthesizer.synthesize(reply.text)
            tts_seconds = time.perf_counter() - tts_started_at
            if audio_path is not None:
                audio_url = f"/alfred-audio/{audio_path.name}"
                logger.info("[perf %s] tts done in %.2fs file=%s", turn_id, tts_seconds, audio_path.name)
            else:
                logger.info("[perf %s] tts skipped or unavailable after %.2fs", turn_id, tts_seconds)

        request_seconds = time.perf_counter() - request_started_at
        end_to_end_seconds = None
        if turn_started_at_ms:
            end_to_end_seconds = max(0.0, (time.time() * 1000 - turn_started_at_ms) / 1000.0)
        logger.info(
            "[perf %s] chat total %.2fs%s",
            turn_id,
            request_seconds,
            f" end_to_end={end_to_end_seconds:.2f}s" if end_to_end_seconds is not None else "",
        )
        llm_backend_metrics = getattr(self.chat_engine.backend, "last_metrics", None)

        return {
            "response": reply.text,
            "audio_url": audio_url,
            "show_text": reply.show_text,
            "reason": reply.reason,
            "turn_id": turn_id,
            "timings": {
                "llm_seconds": round(llm_seconds, 3),
                "tts_seconds": round(tts_seconds, 3),
                "request_seconds": round(request_seconds, 3),
                "end_to_end_seconds": round(end_to_end_seconds, 3) if end_to_end_seconds is not None else None,
                "llm_backend": llm_backend_metrics or None,
            },
            "recent_turns": [asdict(turn) for turn in self.chat_engine.memory.recent_turns[-12:]],
        }

    def reply_stream(self, request: ChatRequest) -> Iterator[bytes]:
        cleaned = request.message.strip()
        if not cleaned:
            self._record_error("Streaming chat request failed because the message was empty.")
            raise HTTPException(status_code=400, detail="Message cannot be empty.")

        response_mode = request.response_mode if request.response_mode in {"voice", "text", "text-brief"} else "voice"
        turn_id = (request.turn_id or "").strip() or f"turn-{uuid.uuid4().hex[:8]}"
        turn_started_at_ms = request.turn_started_at_ms
        request_started_at = time.perf_counter()
        num_predict = self._effective_num_predict(cleaned, response_mode)
        profile = self.chat_engine.profile_for(cleaned, response_mode=response_mode)

        def generate() -> Iterator[bytes]:
            logger.info(
                "[perf %s] stream start mode=%s chars=%d num_predict=%d synthesize_audio=%s text=%r",
                turn_id,
                response_mode,
                len(cleaned),
                num_predict,
                request.synthesize_audio,
                cleaned[:160],
            )
            yield ndjson_event({"type": "start", "turn_id": turn_id})

            llm_started_at = time.perf_counter()
            tts_worker = StreamingTtsWorker(self.synthesizer, llm_started_at) if request.synthesize_audio else None
            first_sentence_event = threading.Event()
            ack_stop_event = threading.Event()
            ack_thread: threading.Thread | None = None
            if tts_worker is not None:
                tts_worker.start()
                ack_thread = threading.Thread(
                    target=self._maybe_enqueue_early_ack,
                    args=(tts_worker, first_sentence_event, ack_stop_event, cleaned, profile),
                    daemon=True,
                )
                ack_thread.start()

            chunker = SentenceChunker()
            full_parts: list[str] = []
            spoken_answer_parts: list[str] = []
            sentence_count = 0
            first_sentence_seconds: float | None = None
            llm_queue: queue.Queue[dict] = queue.Queue()
            llm_done = False

            def llm_worker() -> None:
                try:
                    with self._chat_lock:
                        for chunk in self.chat_engine.stream_reply(cleaned, response_mode=response_mode):
                            llm_queue.put({"type": "chunk", "chunk": chunk})
                    llm_queue.put({"type": "done"})
                except Exception as exc:
                    llm_queue.put({"type": "error", "message": str(exc)})

            llm_thread = threading.Thread(target=llm_worker, daemon=True)
            llm_thread.start()

            try:
                while not llm_done:
                    try:
                        llm_event = llm_queue.get(timeout=0.05)
                    except queue.Empty:
                        llm_event = None

                    if llm_event is not None:
                        if llm_event["type"] == "error":
                            raise RuntimeError(llm_event["message"])
                        if llm_event["type"] == "done":
                            llm_done = True
                        elif llm_event["type"] == "chunk":
                            chunk = llm_event.get("chunk", "")
                            if chunk:
                                full_parts.append(chunk)
                                partial_text = join_stream_text(full_parts)
                                if partial_text:
                                    yield ndjson_event({"type": "partial", "turn_id": turn_id, "text": partial_text})

                                for sentence in chunker.push(chunk):
                                    sentence = _clean_stream_sentence_for_speech(sentence, self.settings.assistant_name)
                                    if not sentence:
                                        continue
                                    sentence_count += 1
                                    if first_sentence_seconds is None:
                                        first_sentence_seconds = time.perf_counter() - llm_started_at
                                        first_sentence_event.set()
                                        logger.info("[perf %s] first sentence ready in %.2fs", turn_id, first_sentence_seconds)
                                    logger.info(
                                        "[perf %s] answer chunk %d: %r",
                                        turn_id,
                                        sentence_count,
                                        reply_log_text(sentence, limit=220),
                                    )
                                    full_text = join_stream_text(full_parts)
                                    spoken_answer_parts.append(sentence)
                                    if tts_worker is not None:
                                        tts_worker.enqueue(sentence, full_text)
                                    else:
                                        yield ndjson_event(
                                            {
                                                "type": "sentence",
                                                "turn_id": turn_id,
                                                "index": sentence_count,
                                                "text": sentence,
                                                "full_text": full_text,
                                                "audio_url": None,
                                                "tts_seconds": 0.0,
                                            }
                                        )

                    if tts_worker is not None:
                        for event in tts_worker.drain_ready_events():
                            yield ndjson_event({"turn_id": turn_id, **event})

                leftover = chunker.flush()
                if leftover and self.chat_engine.last_reply_hit_length_limit():
                    trimmed_leftover = _trim_truncated_reply(leftover)
                    if not _reply_ends_cleanly(trimmed_leftover):
                        logger.info("[perf %s] dropped trailing fragment after length stop", turn_id)
                        leftover = ""
                    else:
                        leftover = trimmed_leftover
                if leftover:
                    leftover = _clean_stream_sentence_for_speech(leftover, self.settings.assistant_name)
                if leftover:
                    sentence_count += 1
                    if first_sentence_seconds is None:
                        first_sentence_seconds = time.perf_counter() - llm_started_at
                        first_sentence_event.set()
                        logger.info("[perf %s] first sentence ready in %.2fs", turn_id, first_sentence_seconds)
                    logger.info(
                        "[perf %s] answer chunk %d: %r",
                        turn_id,
                        sentence_count,
                        reply_log_text(leftover, limit=220),
                    )
                    full_text = join_stream_text(full_parts)
                    spoken_answer_parts.append(leftover)
                    if tts_worker is not None:
                        tts_worker.enqueue(leftover, full_text)
                    else:
                        yield ndjson_event(
                            {
                                "type": "sentence",
                                "turn_id": turn_id,
                                "index": sentence_count,
                                "text": leftover,
                                "full_text": full_text,
                                "audio_url": None,
                                "tts_seconds": 0.0,
                            }
                        )

                ack_stop_event.set()
                if ack_thread is not None:
                    ack_thread.join(timeout=0.1)
                llm_thread.join(timeout=0.1)
                llm_seconds = time.perf_counter() - llm_started_at
                full_text = join_stream_text(full_parts)
                reply = self.chat_engine.finalize_streamed_reply(cleaned, full_text)
                missing_tail = _missing_tts_tail(reply.text, spoken_answer_parts)
                if tts_worker is not None and missing_tail:
                    logger.info(
                        "[perf %s] appending final audio tail: %r",
                        turn_id,
                        reply_log_text(missing_tail, limit=220),
                    )
                    tts_worker.enqueue(missing_tail, reply.text, kind="tail")
            except HTTPException:
                raise
            except Exception as exc:
                self._record_error(f"Streaming voice reply failed: {exc}")
                logger.exception("Streaming voice reply failed")
                ack_stop_event.set()
                if tts_worker is not None:
                    tts_worker.close()
                if ack_thread is not None:
                    ack_thread.join(timeout=0.1)
                yield ndjson_event({"type": "error", "turn_id": turn_id, "message": "Streaming chat failed."})
                return

            logger.info(
                "[perf %s] llm stream done in %.2fs words=%d chars=%d",
                turn_id,
                llm_seconds,
                len(reply.text.split()),
                len(reply.text),
            )
            logger.info("[perf %s] answer: %r", turn_id, reply_log_text(reply.text))

            tts_total_seconds = 0.0
            first_audio_seconds: float | None = None
            first_content_audio_seconds: float | None = None
            if tts_worker is not None:
                tts_worker.close()
                while tts_worker.is_alive():
                    event = tts_worker.wait_for_event(timeout=0.1)
                    if event is None:
                        continue
                    yield ndjson_event({"turn_id": turn_id, **event})
                try:
                    tts_worker.join()
                except Exception as exc:
                    self._record_error(f"Streaming TTS failed: {exc}")
                    yield ndjson_event({"type": "error", "turn_id": turn_id, "message": "Streaming TTS failed."})
                    return
                for event in tts_worker.drain_ready_events():
                    yield ndjson_event({"turn_id": turn_id, **event})
                tts_total_seconds = tts_worker.total_tts_seconds
                first_audio_seconds = tts_worker.first_audio_seconds
                first_content_audio_seconds = tts_worker.first_content_audio_seconds
                if first_audio_seconds is not None:
                    logger.info("[perf %s] first audio chunk ready in %.2fs", turn_id, first_audio_seconds)
                if first_content_audio_seconds is not None:
                    logger.info(
                        "[perf %s] first answer audio chunk ready in %.2fs",
                        turn_id,
                        first_content_audio_seconds,
                    )

            request_seconds = time.perf_counter() - request_started_at
            end_to_end_seconds = None
            if turn_started_at_ms:
                end_to_end_seconds = max(0.0, (time.time() * 1000 - turn_started_at_ms) / 1000.0)
            llm_backend_metrics = getattr(self.chat_engine.backend, "last_metrics", None)
            logger.info(
                "[perf %s] stream total %.2fs%s",
                turn_id,
                request_seconds,
                f" end_to_end={end_to_end_seconds:.2f}s" if end_to_end_seconds is not None else "",
            )
            yield ndjson_event(
                {
                    "type": "done",
                    "turn_id": turn_id,
                    "response": reply.text,
                    "show_text": reply.show_text,
                    "reason": reply.reason,
                    "recent_turns": [asdict(turn) for turn in self.chat_engine.memory.recent_turns[-12:]],
                    "timings": {
                        "llm_seconds": round(llm_seconds, 3),
                        "tts_seconds": round(tts_total_seconds, 3),
                        "request_seconds": round(request_seconds, 3),
                        "end_to_end_seconds": round(end_to_end_seconds, 3) if end_to_end_seconds is not None else None,
                        "first_sentence_seconds": round(first_sentence_seconds, 3) if first_sentence_seconds is not None else None,
                        "first_audio_seconds": round(first_audio_seconds, 3) if first_audio_seconds is not None else None,
                        "first_content_audio_seconds": round(first_content_audio_seconds, 3)
                        if first_content_audio_seconds is not None
                        else None,
                        "llm_backend": llm_backend_metrics or None,
                    },
                }
            )
            self.cleanup_old_audio()

        return generate()

    def reset_memory(self) -> dict:
        with self._chat_lock:
            self.chat_engine.memory.reset()
        logger.info("Touch chat memory reset")
        return {
            "ok": True,
            "assistant_name": self.settings.assistant_name,
            "recent_turns": [],
        }

    def test_speaker(self) -> dict:
        text = "This is Alfred. Speaker test complete."
        audio_path = self.synthesizer.synthesize(text)
        if audio_path is None:
            self._record_error("Speaker test failed because no audio file could be generated.")
            raise HTTPException(status_code=500, detail="Speaker test audio could not be generated.")
        return {
            "ok": True,
            "text": text,
            "audio_url": f"/alfred-audio/{audio_path.name}",
        }

    def schedule_restart(self) -> dict:
        if self._restart_requested:
            return {"ok": True, "status": "already-restarting"}
        self._restart_requested = True
        logger.info("Scheduling Alfred touch backend restart")
        threading.Thread(target=self._restart_process, daemon=True).start()
        return {"ok": True, "status": "restarting"}

    def transcribe_upload(
        self,
        temp_path: Path,
        *,
        turn_id: str | None = None,
        turn_started_at_ms: float | None = None,
    ) -> tuple[str, dict[str, float | None | str]]:
        perf_turn_id = turn_id or f"turn-{uuid.uuid4().hex[:8]}"
        started_at = time.perf_counter()
        size = temp_path.stat().st_size if temp_path.exists() else 0
        logger.info("[perf %s] stt start file=%s bytes=%d", perf_turn_id, temp_path.name, size)
        text = (self.stt.transcribe(str(temp_path)) or "").strip()
        stt_seconds = time.perf_counter() - started_at
        end_to_end_seconds = None
        if turn_started_at_ms:
            end_to_end_seconds = max(0.0, (time.time() * 1000 - turn_started_at_ms) / 1000.0)
        logger.info(
            "[perf %s] stt done in %.2fs%s text=%r",
            perf_turn_id,
            stt_seconds,
            f" end_to_end={end_to_end_seconds:.2f}s" if end_to_end_seconds is not None else "",
            text[:120],
        )
        return text, {
            "turn_id": perf_turn_id,
            "stt_seconds": round(stt_seconds, 3),
            "end_to_end_seconds": round(end_to_end_seconds, 3) if end_to_end_seconds is not None else None,
        }

    def cleanup_old_audio(self, max_age_seconds: int = 900) -> None:
        try:
            now = time.time()
            for path in self.web_audio_dir.glob("reply_*.wav"):
                if now - path.stat().st_mtime > max_age_seconds:
                    path.unlink(missing_ok=True)
        except Exception as exc:  # pragma: no cover - cleanup best-effort
            logger.warning("Audio cleanup error: %s", exc)

    def _resolve_local_path(self, raw_path: str) -> Path:
        path = Path(raw_path).expanduser()
        if path.is_absolute():
            return path
        return ROOT_DIR / path

    def _resolve_whisper_model(self) -> tuple[Path, str]:
        mode = self.settings.whisper_mode
        fast_model = self.settings.whisper_fast_model
        accurate_model = self.settings.whisper_model

        if mode == "fast":
            if fast_model.exists():
                return fast_model, "fast"
            logger.warning(
                "Requested fast Whisper mode, but tiny model is missing at %s. Falling back to accurate mode. "
                "Run ./scripts/setup_alfred_audio.sh on the Pi to install it.",
                fast_model,
            )
            return accurate_model, "accurate-fallback"
        if mode == "accurate":
            return accurate_model, "accurate"
        if fast_model.exists():
            return fast_model, "fast-auto"
        return accurate_model, "accurate-auto"

    def _prime_ack_audio_cache(self) -> dict[str, str]:
        cache: dict[str, str] = {}
        if not resolve_executable(self.settings.piper_cmd, "piper"):
            return cache
        if not self.settings.piper_model.exists():
            return cache
        for phrase in EARLY_ACK_PHRASES:
            slug = uuid.uuid5(uuid.NAMESPACE_URL, phrase).hex[:12]
            output_path = self.web_audio_dir / f"ack_{slug}.wav"
            if not output_path.exists():
                created = self.synthesizer.synthesize(phrase, output_path=output_path)
                if created is None:
                    continue
            cache[phrase] = f"/alfred-audio/{output_path.name}"
        if cache:
            logger.info("Primed %d cached early-ack audio clips", len(cache))
        return cache

    def _effective_num_predict(self, cleaned: str, response_mode: str) -> int:
        profile = self.chat_engine.profile_for(cleaned, response_mode=response_mode)
        return _num_predict_for_profile(self.settings, profile, response_mode)

    def _early_ack_delay(self, cleaned: str, profile) -> float | None:
        normalized = " ".join(cleaned.split())
        if not normalized:
            return None
        if profile.social and not profile.wants_detail:
            return None
        if profile.wants_detail:
            return 2.4
        if profile.factual:
            return 2.6
        if len(normalized.split()) >= 8 or len(normalized) >= 42:
            return 2.8
        return None

    def _choose_early_ack(self) -> str:
        return random.choice(EARLY_ACK_PHRASES)

    def _maybe_enqueue_early_ack(
        self,
        worker: StreamingTtsWorker,
        first_sentence_event: threading.Event,
        stop_event: threading.Event,
        cleaned: str,
        profile,
    ) -> None:
        delay = self._early_ack_delay(cleaned, profile)
        if delay is None:
            return
        if stop_event.wait(delay) or first_sentence_event.is_set():
            return
        phrase = self._choose_early_ack()
        logger.info("Early ack triggered after %.2fs: %r", delay, phrase)
        cached_audio_url = self.ack_audio_cache.get(phrase)
        if cached_audio_url:
            worker.enqueue_prerendered(phrase, phrase, cached_audio_url, kind="ack")
            return
        worker.enqueue(phrase, phrase, kind="ack")

    def _record_error(self, message: str) -> None:
        self.last_error = message
        self.last_error_at = time.time()
        logger.warning("Alfred touch issue: %s", message)

    def _restart_process(self) -> None:
        time.sleep(0.35)
        try:
            python_exe = sys.executable
            args = [
                python_exe,
                "-m",
                "uvicorn",
                "alfred_touch:app",
                "--host",
                os.environ.get("ALFRED_TOUCH_HOST", "0.0.0.0"),
                "--port",
                os.environ.get("ALFRED_TOUCH_PORT", "8081"),
            ]
            os.execvpe(python_exe, args, os.environ.copy())
        except Exception as exc:
            self._restart_requested = False
            self._record_error(f"Backend restart failed: {exc}")
            logger.exception("Backend restart failed")

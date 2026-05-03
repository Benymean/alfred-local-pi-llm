from __future__ import annotations

import logging
from pathlib import Path
import queue
import subprocess
import threading
import time
import uuid

from alfred.audio import clean_text_for_speech, resolve_executable


logger = logging.getLogger(__name__)


class PiperFileSynthesizer:
    def __init__(self, piper_cmd: Path, model_path: Path, output_dir: Path, *, ffmpeg_cmd: str = "ffmpeg", tempo: float = 1.0):
        self.piper_cmd = Path(piper_cmd)
        self.model_path = Path(model_path)
        self.output_dir = output_dir
        self.ffmpeg_cmd = ffmpeg_cmd
        self.tempo = max(0.5, min(1.5, float(tempo)))

    def synthesize(self, text: str, *, output_path: Path | None = None) -> Path | None:
        clean_text = clean_text_for_speech(text)
        if not clean_text or not any(char.isalnum() for char in clean_text):
            return None

        piper_exe = resolve_executable(self.piper_cmd, "piper")
        if not piper_exe:
            logger.warning("Piper binary not found. Browser audio will be unavailable.")
            return None
        if not self.model_path.exists():
            logger.warning("Piper model not found at %s. Browser audio will be unavailable.", self.model_path)
            return None

        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_path or (self.output_dir / f"reply_{uuid.uuid4().hex[:10]}.wav")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                [piper_exe, "--model", str(self.model_path), "--output_file", str(output_path)],
                input=clean_text.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            logger.error("Piper file synthesis failed: %s", exc.stderr.decode(errors="replace").strip())
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None
        if abs(self.tempo - 1.0) > 0.01 and not self._apply_tempo(output_path):
            return None
        return output_path

    def _apply_tempo(self, output_path: Path) -> bool:
        ffmpeg_exe = resolve_executable(self.ffmpeg_cmd, "ffmpeg")
        if not ffmpeg_exe:
            logger.warning("ffmpeg not found; skipping TTS tempo adjustment.")
            return True

        adjusted_path = output_path.with_name(f"{output_path.stem}_tempo.wav")
        try:
            subprocess.run(
                [
                    ffmpeg_exe,
                    "-y",
                    "-i",
                    str(output_path),
                    "-filter:a",
                    f"atempo={self.tempo:.3f}",
                    str(adjusted_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            adjusted_path.replace(output_path)
            return True
        except subprocess.CalledProcessError as exc:
            logger.error("ffmpeg tempo adjustment failed: %s", exc.stderr.decode(errors="replace").strip())
            try:
                adjusted_path.unlink(missing_ok=True)
                output_path.unlink(missing_ok=True)
            except OSError:
                pass
            return False


class StreamingTtsWorker:
    def __init__(self, synthesizer: PiperFileSynthesizer, stream_started_at: float):
        self.synthesizer = synthesizer
        self.stream_started_at = stream_started_at
        self.total_tts_seconds = 0.0
        self.first_audio_seconds: float | None = None
        self.first_content_audio_seconds: float | None = None
        self._sequence = 0
        self._input: queue.Queue[dict | None] = queue.Queue()
        self._events: queue.Queue[dict | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._started = False
        self._error: Exception | None = None

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread.start()

    def enqueue(self, sentence: str, full_text: str, *, kind: str = "sentence") -> None:
        cleaned = " ".join(sentence.split()).strip()
        if not cleaned:
            return
        self._sequence += 1
        self._input.put(
            {
                "index": self._sequence,
                "sentence": cleaned,
                "full_text": full_text,
                "kind": kind,
            }
        )

    def enqueue_prerendered(self, sentence: str, full_text: str, audio_url: str, *, kind: str = "ack") -> None:
        cleaned = " ".join(sentence.split()).strip()
        if not cleaned or not audio_url:
            return
        self._sequence += 1
        self._input.put(
            {
                "index": self._sequence,
                "sentence": cleaned,
                "full_text": full_text,
                "kind": kind,
                "audio_url": audio_url,
                "prerendered": True,
            }
        )

    def close(self) -> None:
        if self._started:
            self._input.put(None)

    def join(self) -> None:
        if self._started:
            self._thread.join()
        if self._error:
            raise self._error

    def is_alive(self) -> bool:
        return self._started and self._thread.is_alive()

    def drain_ready_events(self) -> list[dict]:
        ready: list[dict] = []
        while True:
            try:
                item = self._events.get_nowait()
            except queue.Empty:
                break
            if item is not None:
                ready.append(item)
        return ready

    def wait_for_event(self, timeout: float = 0.1) -> dict | None:
        try:
            return self._events.get(timeout=timeout)
        except queue.Empty:
            return None

    def _run(self) -> None:
        try:
            while True:
                payload = self._input.get()
                if payload is None:
                    self._events.put(None)
                    return

                sentence = payload["sentence"]
                full_text = payload["full_text"]
                index = int(payload["index"])
                kind = payload.get("kind", "sentence")
                tts_seconds = 0.0
                audio_url = payload.get("audio_url")

                if not payload.get("prerendered"):
                    tts_started_at = time.perf_counter()
                    audio_path = self.synthesizer.synthesize(sentence)
                    tts_seconds = time.perf_counter() - tts_started_at
                    self.total_tts_seconds += tts_seconds
                    if audio_path is not None:
                        audio_url = f"/alfred-audio/{audio_path.name}"

                if audio_url and self.first_audio_seconds is None:
                    self.first_audio_seconds = time.perf_counter() - self.stream_started_at
                if audio_url and kind != "ack" and self.first_content_audio_seconds is None:
                    self.first_content_audio_seconds = time.perf_counter() - self.stream_started_at

                self._events.put(
                    {
                        "type": "sentence",
                        "index": index,
                        "kind": kind,
                        "text": sentence,
                        "full_text": full_text,
                        "audio_url": audio_url,
                        "tts_seconds": round(tts_seconds, 3),
                    }
                )
        except Exception as exc:
            logger.exception("Streaming TTS worker failed")
            self._error = exc
            self._events.put({"type": "error", "message": f"Streaming TTS failed: {exc}"})
            self._events.put(None)

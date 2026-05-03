from __future__ import annotations

import logging
from pathlib import Path
import re
import shutil
import subprocess
import time


logger = logging.getLogger(__name__)


def resolve_executable(candidate: Path | str, *fallback_names: str) -> str | None:
    candidate_text = str(candidate)
    candidate_path = Path(candidate_text).expanduser()
    if candidate_path.exists():
        return str(candidate_path)

    resolved = shutil.which(candidate_text)
    if resolved:
        return resolved

    for name in fallback_names:
        resolved = shutil.which(name)
        if resolved:
            return resolved

    return None


class WhisperCppSTT:
    def __init__(self, whisper_cmd: Path, model_path: Path, ffmpeg_cmd: str = "ffmpeg"):
        self.whisper_cmd = Path(whisper_cmd)
        self.model_path = Path(model_path)
        self.ffmpeg_cmd = ffmpeg_cmd

    def transcribe(self, audio_path: str) -> str:
        source_path = Path(audio_path)
        if not source_path.exists():
            logger.error("Audio file not found: %s", source_path)
            return ""

        whisper_exe = resolve_executable(self.whisper_cmd, "whisper-cli")
        if not whisper_exe:
            logger.error("whisper.cpp binary not found. Configured value: %s", self.whisper_cmd)
            return ""

        ffmpeg_exe = resolve_executable(self.ffmpeg_cmd, "ffmpeg")
        if not ffmpeg_exe:
            logger.error("ffmpeg is not installed or not in PATH. Configured value: %s", self.ffmpeg_cmd)
            return ""

        if not self.model_path.exists():
            logger.error("Whisper model not found at %s", self.model_path)
            return ""

        temp_wav = source_path.with_name(f"{source_path.name}_16k.wav")
        started_at = time.perf_counter()
        try:
            convert_started_at = time.perf_counter()
            subprocess.run(
                [ffmpeg_exe, "-y", "-i", str(source_path), "-ar", "16000", "-ac", "1", str(temp_wav)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            convert_seconds = time.perf_counter() - convert_started_at

            cmd = [whisper_exe, "-m", str(self.model_path), "-f", str(temp_wav), "-nt"]
            logger.info("Running whisper.cpp transcription: %s", " ".join(cmd))
            whisper_started_at = time.perf_counter()
            output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8", errors="replace").strip()
            whisper_seconds = time.perf_counter() - whisper_started_at
            total_seconds = time.perf_counter() - started_at
            logger.info(
                "STT completed in %.2fs (ffmpeg %.2fs, whisper %.2fs)",
                total_seconds,
                convert_seconds,
                whisper_seconds,
            )
            return clean_transcript(output)
        except subprocess.CalledProcessError as exc:
            logger.error("Whisper transcription failed: %s", exc)
            return ""
        finally:
            try:
                temp_wav.unlink(missing_ok=True)
            except OSError:
                pass


def clean_text_for_speech(text: str) -> str:
    cleaned = replace_years_with_words(text)
    cleaned = re.sub(r"^(alfred|assistant)\s*(?:says)?\s*[:\-]\s*", "", cleaned.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\{.*?\}", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.replace("\n", " ").replace("\r", " ")
    cleaned = cleaned.replace("*", "")
    cleaned = re.sub(r"[_~`#\-]", "", cleaned)
    cleaned = re.sub(r"\bkm/h\b", "kilometers per hour", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bmph\b", "miles per hour", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"([a-zA-Z])\/([a-zA-Z])", r"\1 per \2", cleaned)
    cleaned = re.sub(r"http[s]?://\S+", "", cleaned)
    cleaned = re.sub(r"[^\x00-\x7F\xC0-\xFF\u0100-\u017F\u0180-\u024F\u1E00-\u1EFF\u2018-\u201F\u2028-\u202F]", "", cleaned)
    return " ".join(cleaned.split()).strip()


def clean_transcript(text: str) -> str:
    output = re.sub(r"\[.*?\]", "", text).strip()
    lowered = output.lower()
    hallucinations = {
        "[silence]",
        "(silence)",
        "you",
        "thanks for watching!",
        "[blank_audio]",
        "thank you.",
        "thank you",
        "thanks.",
    }
    is_parenthetical = bool(re.match(r"^\s*[\(\[].*[\)\]]\s*$", output.strip()))
    if is_parenthetical or lowered in hallucinations or not re.search(r"[a-zA-Z0-9]", lowered):
        logger.info("Whisper hallucination filtered: %r", output)
        return ""
    return output


def replace_years_with_words(text: str) -> str:
    def number_to_words(value: int) -> str:
        units = [
            "",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
        ]
        tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
        if 0 <= value < 20:
            return units[value]
        return (tens[value // 10] + " " + units[value % 10]).strip()

    def year_to_words(match: re.Match[str]) -> str:
        year = int(match.group(0))
        if 1000 <= year <= 1999:
            first_half = year // 100
            second_half = year % 100
            if second_half == 0:
                return f"{number_to_words(first_half)} hundred"
            if second_half < 10:
                return f"{number_to_words(first_half)} oh {number_to_words(second_half)}"
            return f"{number_to_words(first_half)} {number_to_words(second_half)}"
        if 2000 <= year <= 2009:
            second_half = year % 100
            if second_half == 0:
                return "two thousand"
            return f"two thousand and {number_to_words(second_half)}"
        if 2010 <= year <= 2099:
            first_half = year // 100
            second_half = year % 100
            if second_half == 0:
                return f"{number_to_words(first_half)} hundred"
            if second_half < 10:
                return f"{number_to_words(first_half)} oh {number_to_words(second_half)}"
            return f"{number_to_words(first_half)} {number_to_words(second_half)}"
        return match.group(0)

    return re.sub(r"\b(1[0-9]{3}|20[0-9]{2})\b", year_to_words, text)

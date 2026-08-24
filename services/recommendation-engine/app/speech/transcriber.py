"""Faster-Whisper speech-to-text ONLY (Phase 3 22-28).

Responsibility boundary: audio -> text. No RAG, no intent handling, no
recommendations, no TTS. Raw recordings are processed in memory and never
written to disk; only the transcript leaves this module.

Configuration (all optional):
    WHISPER_MODEL         default "base"      (tiny|base|small|medium...)
    WHISPER_DEVICE        default "cpu"       (cpu|auto)
    WHISPER_COMPUTE_TYPE  default "int8"      (int8|int8_float32|float16...)

The heavy faster-whisper dependency is imported lazily so the rest of the
service (and the test suite) runs without it installed.
"""
from __future__ import annotations

import io
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

MAX_AUDIO_BYTES = 25 * 1024 * 1024


class TranscriptionUnavailable(RuntimeError):
    """Raised when Whisper is not configured/importable in this environment."""


class WhisperTranscriber:
    def __init__(
        self,
        model_size: str,
        device: str,
        compute_type: str,
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._model: object | None = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from faster_whisper import WhisperModel
            except ImportError as error:
                raise TranscriptionUnavailable(
                    "whisper_model_unavailable"
                ) from error
            started = time.perf_counter()
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
            logger.info(
                "faster-whisper model=%s device=%s compute=%s loaded in %.1fs",
                self._model_size,
                self._device,
                self._compute_type,
                time.perf_counter() - started,
            )
        return self._model

    def transcribe(self, audio_bytes: bytes) -> tuple[str, str | None, int]:
        """Returns (text, language, duration_ms). Audio is never persisted."""
        if not audio_bytes or len(audio_bytes) > MAX_AUDIO_BYTES:
            raise ValueError("invalid_audio")
        model = self._load()
        start = time.perf_counter()
        try:
            segments, info = model.transcribe(
                io.BytesIO(audio_bytes),
                beam_size=1,
                vad_filter=True,
            )
            texts = [segment.text.strip() for segment in segments]
        except Exception as error:  # noqa: BLE001 - decoder failures are data errors
            logger.warning("transcription failed: %s", type(error).__name__)
            raise ValueError("transcription_failed") from error
        text = " ".join(t for t in texts if t).strip()
        duration_ms = int((time.perf_counter() - start) * 1000)
        language = getattr(info, "language", None)
        # `audio_bytes` becomes unreachable on return - garbage collected.
        return text, language, duration_ms


_transcriber: WhisperTranscriber | None = None


def get_transcriber() -> WhisperTranscriber:
    """Configured singleton; raises TranscriptionUnavailable when disabled."""
    global _transcriber
    if _transcriber is None:
        if os.getenv("WHISPER_ENABLED", "").lower() not in {"1", "true", "yes"}:
            raise TranscriptionUnavailable("whisper_not_configured")
        _transcriber = WhisperTranscriber(
            model_size=os.getenv("WHISPER_MODEL", "base"),
            device=os.getenv("WHISPER_DEVICE", "cpu"),
            compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        )
    return _transcriber


def reset_transcriber() -> None:
    global _transcriber
    _transcriber = None


__all__ = [
    "TranscriptionUnavailable",
    "WhisperTranscriber",
    "get_transcriber",
    "reset_transcriber",
]

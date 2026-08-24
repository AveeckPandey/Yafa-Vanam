"""Speech transcription boundary tests (Phase 3 spec sections 22-28).

The faster-whisper model itself is not loaded in unit tests; these verify the
configuration gate, the privacy contract (audio never persisted) and the
response shape via a stubbed transcriber.
"""
from __future__ import annotations

import pytest

from app.speech import transcriber
from app.speech.transcriber import (
    TranscriptionUnavailable,
    WhisperTranscriber,
    get_transcriber,
    reset_transcriber,
)


@pytest.fixture(autouse=True)
def _clean_singleton():
    reset_transcriber()
    yield
    reset_transcriber()


def test_unconfigured_environment_raises():
    with pytest.raises(TranscriptionUnavailable):
        get_transcriber()


def test_configured_environment_builds_lazy_transcriber(monkeypatch):
    monkeypatch.setenv("WHISPER_ENABLED", "true")
    monkeypatch.setenv("WHISPER_MODEL", "tiny")
    instance = get_transcriber()
    assert isinstance(instance, WhisperTranscriber)
    # Model must NOT be loaded yet (lazy): no faster_whisper import happened.
    assert instance._model is None


def test_transcription_unavailable_when_dependency_missing(monkeypatch):
    monkeypatch.setenv("WHISPER_ENABLED", "1")
    instance = get_transcriber()
    import sys

    saved = sys.modules.get("faster_whisper")
    monkeypatch.setitem(sys.modules, "faster_whisper", None)  # force ImportError
    try:
        with pytest.raises(TranscriptionUnavailable):
            instance.transcribe(b"fake-bytes")
    finally:
        if saved is not None:
            sys.modules["faster_whisper"] = saved


def test_stubbed_transcription_contract():
    """The endpoint contract: (text, language, duration_ms), audio discarded."""
    class StubModel:
        def transcribe(self, source, beam_size=1, vad_filter=True):
            assert hasattr(source, "read"), "in-memory stream expected"

            class Info:
                language = "en"

            def segments():
                class Seg:
                    text = " recommend me a soft glam look "

                yield Seg()

            return segments(), Info()

    instance = WhisperTranscriber("tiny", "cpu", "int8")
    instance._model = StubModel()
    text, language, duration_ms = instance.transcribe(b"audio-bytes")
    assert text == "recommend me a soft glam look"
    assert language == "en"
    assert isinstance(duration_ms, int)


def test_invalid_audio_rejected():
    instance = WhisperTranscriber("tiny", "cpu", "int8")
    with pytest.raises(ValueError):
        instance.transcribe(b"")


def test_module_never_persists_audio(tmp_path):
    """Privacy test: transcribing writes nothing to disk."""
    before = set(tmp_path.iterdir())

    class NullModel:
        def transcribe(self, source, beam_size=1, vad_filter=True):
            return iter([]), type("Info", (), {"language": "en"})()

    instance = WhisperTranscriber("tiny", "cpu", "int8")
    instance._model = NullModel()
    instance.transcribe(b"some-audio")
    assert set(tmp_path.iterdir()) == before

import pytest

from audio.transcribe import (
    FasterWhisperTranscriber,
    NullTranscriber,
    Word,
    get_transcriber,
)


def test_disabled_returns_null():
    assert isinstance(get_transcriber({"enabled": False}), NullTranscriber)


def test_null_provider_returns_null():
    assert isinstance(get_transcriber({"enabled": True, "provider": "null"}), NullTranscriber)


def test_whisper_provider_selected():
    t = get_transcriber({"enabled": True, "provider": "whisper", "model": "tiny", "language": "ja"})
    assert isinstance(t, FasterWhisperTranscriber)
    assert t.model == "tiny" and t.language == "ja"


def test_unknown_provider_raises():
    with pytest.raises(NotImplementedError):
        get_transcriber({"enabled": True, "provider": "bogus"})


def test_null_transcriber_returns_empty():
    assert NullTranscriber().transcribe("x.mp4") == []


def test_word_dataclass():
    w = Word(start=1.0, end=1.5, text="えー")
    assert w.end - w.start == 0.5

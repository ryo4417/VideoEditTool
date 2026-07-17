import json

import pytest

from core.models import MediaInfo, TimeRange
from quality import ai_assist
from quality.ai_assist import NullAssessor, OllamaAssessor, get_assessor
from quality.checker import QualityChecker


def _report():
    media = MediaInfo(path="x.mp4", duration=10.0)
    return QualityChecker().check(media, [], [TimeRange(0, 10)])


def test_disabled_returns_null():
    assert isinstance(get_assessor({"enabled": False}), NullAssessor)


def test_null_provider_returns_null():
    assert isinstance(get_assessor({"enabled": True, "provider": "null"}), NullAssessor)


def test_ollama_provider_selected():
    a = get_assessor({"enabled": True, "provider": "ollama", "model": "qwen2.5", "host": "http://h:1"})
    assert isinstance(a, OllamaAssessor)
    assert a.model == "qwen2.5" and a.host == "http://h:1"


def test_unknown_provider_raises():
    with pytest.raises(NotImplementedError):
        get_assessor({"enabled": True, "provider": "bogus"})


def test_prompt_contains_metrics():
    p = OllamaAssessor()._build_prompt(_report())
    assert "削除率" in p and "JSON" in p


def test_parse_valid_json():
    a = OllamaAssessor()._parse(json.dumps(
        {"score": 82, "suggestions": ["間を詰める"], "missed_edits": ["冒頭の無音"]}))
    assert a.score == 82.0
    assert a.suggestions == ["間を詰める"] and a.missed_edits == ["冒頭の無音"]
    assert a.provider == "ollama"


def test_parse_invalid_json_degrades():
    a = OllamaAssessor()._parse("これはJSONではない")
    assert a.score is None and a.error


def test_assess_with_mocked_http(monkeypatch):
    a = OllamaAssessor(model="m")
    monkeypatch.setattr(a, "_call", lambda prompt: json.dumps({"score": 70, "suggestions": ["s"]}))
    result = a.assess(MediaInfo(path="x.mp4", duration=10.0), [], [TimeRange(0, 10)], _report())
    assert result.score == 70.0 and result.suggestions == ["s"]


def test_assess_connection_error_is_graceful(monkeypatch):
    import urllib.error
    a = OllamaAssessor()

    def boom(prompt):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(a, "_call", boom)
    result = a.assess(MediaInfo(path="x.mp4", duration=10.0), [], [TimeRange(0, 10)], _report())
    assert result.error and result.score is None

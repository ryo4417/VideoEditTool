"""GPT/エージェント指摘の堅牢化（設定検証・出力先制限・AI出力制限）の検証。"""
import json

import pytest

from core.config import validate_config
from quality.ai_assist import OllamaAssessor
from ui.web.server import _safe_output_dir, _BASE_DIR


def test_negative_numeric_config_rejected():
    errors = validate_config({"timeline": {"min_segment_sec": -5}})
    assert any("負値は不可" in e for e in errors)
    assert validate_config({"timeline": {"min_segment_sec": 0.3}}) == []


def test_ai_timeout_is_valid_key():
    assert validate_config({"ai": {"enabled": True, "timeout": 30}}) == []


def test_output_dir_confined_to_base():
    # 作業ディレクトリ配下は許可
    assert _safe_output_dir(str(_BASE_DIR / "out")) is not None
    # 外部への書き込みは拒否
    with pytest.raises(ValueError):
        _safe_output_dir("C:\\Windows\\Temp\\evil")


def test_ai_score_clamped_and_capped():
    a = OllamaAssessor()._parse(json.dumps({
        "score": 250,
        "suggestions": [f"s{i}" for i in range(30)],
    }))
    assert a.score == 100.0                       # 0-100 にクランプ
    assert len(a.suggestions) == 10               # 件数上限


def test_ai_negative_score_clamped():
    a = OllamaAssessor()._parse(json.dumps({"score": -20}))
    assert a.score == 0.0

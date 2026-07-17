import pytest

from core.config import ConfigError, load_config, validate_config


def test_valid_config_passes():
    assert validate_config(
        {
            "analysis": {"silence": {"enabled": True, "noise_threshold_db": -30}},
            "rules": {"silence": {"enabled": True, "min_cut_sec": 0.5}},
            "timeline": {"merge_gap_sec": 0.2, "min_segment_sec": 0.3},
            "export": {"format": "json"},
        }
    ) == []


def test_unknown_section_detected():
    errors = validate_config({"analisys": {}})  # typo
    assert any("未知のセクション" in e for e in errors)


def test_unknown_key_in_fixed_section():
    errors = validate_config({"export": {"formatt": "json"}})
    assert any("未知のキー" in e and "export.formatt" in e for e in errors)


def test_type_violation():
    errors = validate_config({"timeline": {"merge_gap_sec": "fast"}})
    assert any("型違反" in e for e in errors)


def test_bool_not_accepted_as_number():
    errors = validate_config({"quality": {"max_removed_ratio": True}})
    assert any("型違反" in e for e in errors)


def test_invalid_format_value():
    errors = validate_config({"export": {"format": "mp3"}})
    assert any("不正な export.format" in e for e in errors)


def test_enabled_must_be_bool_in_open_section():
    errors = validate_config({"rules": {"silence": {"enabled": "yes"}}})
    assert any("enabled" in e for e in errors)


def test_open_section_allows_arbitrary_plugin_keys():
    # 未登録名でも検証は通す（拡張性優先。存在チェックは RuleEngine 側）
    assert validate_config({"rules": {"my_future_rule": {"enabled": False, "x": 1}}}) == []


def test_load_config_raises_on_bad_default(monkeypatch):
    import core.config as cfg
    monkeypatch.setattr(cfg, "_load_yaml", lambda p: {"unknown_section": 1})
    with pytest.raises(ConfigError):
        load_config()

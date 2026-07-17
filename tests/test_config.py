from core.config import Config, _deep_merge, load_config


def test_deep_merge_overrides_nested():
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    override = {"a": {"y": 20}, "c": 4}
    merged = _deep_merge(base, override)
    assert merged == {"a": {"x": 1, "y": 20}, "b": 3, "c": 4}
    # 元の base は変更されない
    assert base["a"]["y"] == 2


def test_config_dot_access():
    cfg = Config({"rules": {"silence": {"min_cut_sec": 0.5}}})
    assert cfg.get("rules.silence.min_cut_sec") == 0.5
    assert cfg.get("rules.missing.key", 99) == 99


def test_load_default_config():
    cfg = load_config()
    assert cfg.get("rules.silence.enabled") is True


def test_profile_overrides_default():
    default = load_config()
    yt = load_config("youtube")
    assert yt.get("rules.silence.min_cut_sec") < default.get("rules.silence.min_cut_sec")

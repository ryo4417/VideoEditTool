from core.config import load_config
from ui.web.server import Handler


def test_toggles_enable_selected_rules_and_transcript():
    cfg = load_config()
    Handler._apply_toggles(cfg, {"rules": ["silence,filler"], "transcript": ["1"]})
    assert cfg.get("rules.silence.enabled") is True
    assert cfg.get("rules.filler.enabled") is True
    assert cfg.get("rules.duplicate.enabled") is False
    assert cfg.get("analysis.transcript.enabled") is True


def test_no_rules_param_leaves_defaults():
    cfg = load_config()
    Handler._apply_toggles(cfg, {})
    # 既定: silence 有効 / filler 無効 / transcript 無効
    assert cfg.get("rules.silence.enabled") is True
    assert cfg.get("rules.filler.enabled") is False
    assert cfg.get("analysis.transcript.enabled") is False


def test_empty_rules_disables_all_when_transcript_only():
    cfg = load_config()
    Handler._apply_toggles(cfg, {"rules": ["duplicate"], "transcript": ["1"]})
    assert cfg.get("rules.silence.enabled") is False
    assert cfg.get("rules.duplicate.enabled") is True

from audio.transcribe import Word
from core.models import AnalysisResult, EditAction, MediaInfo
from rules.restate_rule import RestateRule


def _analysis(words):
    media = MediaInfo(path="x.mp4", duration=100.0, has_audio=True)
    r = AnalysisResult(media=media)
    r.data["words"] = words
    return r


def test_similar_adjacent_phrase_is_restate():
    # 「私 は 思う」→「私 が 思う」: 2/3 共有・非一致 → 前半をカット
    words = [
        Word(0.0, 0.4, "私"), Word(0.4, 0.8, "は"), Word(0.8, 1.4, "思う"),
        Word(1.4, 1.8, "私"), Word(1.8, 2.2, "が"), Word(2.2, 2.8, "思う"),
    ]
    cands = RestateRule({"sim_threshold": 0.5}).apply(_analysis(words))
    assert len(cands) == 1
    assert cands[0].action == EditAction.CUT
    assert cands[0].time_range.start == 0.0 and cands[0].time_range.end == 1.4


def test_exact_duplicate_is_not_restate():
    # 完全一致は duplicate の領域 → restate では拾わない
    words = [
        Word(0, 0.4, "私"), Word(0.4, 0.8, "は"),
        Word(0.8, 1.2, "私"), Word(1.2, 1.6, "は"),
    ]
    assert RestateRule({"min_words": 2}).apply(_analysis(words)) == []


def test_dissimilar_phrases_not_cut():
    words = [
        Word(0, 0.4, "犬"), Word(0.4, 0.8, "が"),
        Word(0.8, 1.2, "空"), Word(1.2, 1.6, "青"),
    ]
    assert RestateRule({"sim_threshold": 0.5}).apply(_analysis(words)) == []


def test_shared_particle_only_is_not_restate():
    # 「今日は」「明日は」: 共有は は(機能語)のみ → 言い直しではない（誤カット防止）
    words = [
        Word(0, 0.4, "今日"), Word(0.4, 0.8, "は"),
        Word(0.8, 1.2, "明日"), Word(1.2, 1.6, "は"),
    ]
    assert RestateRule().apply(_analysis(words)) == []


def test_shared_copula_only_is_not_restate():
    # 「これです」「それです」: 共有は です(機能語)のみ → 対象外
    words = [
        Word(0, 0.4, "これ"), Word(0.4, 0.8, "です"),
        Word(0.8, 1.2, "それ"), Word(1.2, 1.6, "です"),
    ]
    assert RestateRule().apply(_analysis(words)) == []

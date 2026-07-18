"""フィラー除去ルール（内容ベース・複数語句・サブワード分割耐性）。

文字起こしの単語列から、フィラー語（「えー」「あの」「um」「you know」等）を
検出して CUT 候補にする。対象語は config 管理（複数語のフレーズも可）。

Whisper は日本語を字/サブワード単位に割ることがあり（例「あの」→「あ」「の」）、
1トークン単位のスライド照合だと空振りするため、**正規化した単語を連結した文字列**上で
照合し、マッチが**単語境界にちょうど揃う**場合のみ採用する（語内部の部分一致は誤爆させない）。
"""
from __future__ import annotations

from typing import List

from core.models import AnalysisResult, EditAction, EditCandidate, TimeRange
from core.registry import RULES
from core.rule import BaseRule
from rules._text import join_words, normalize_word

# 既定のフィラー（config.rules.filler.words で上書き可能）。多語句も可。
# 「ええ/ええと」等は whisper が「えー/えーと」をそう表記する揺れへの対応。
DEFAULT_FILLERS = [
    "えー", "えーと", "えっと", "ええ", "ええと", "あのー", "あの", "あのう",
    "あー", "まあ", "まぁ", "その", "そのー", "そのう", "なんか", "こう",
    "um", "uh", "er", "ah", "hmm", "you know",
]


@RULES.register("filler")
class FillerRule(BaseRule):
    def apply(self, analysis: AnalysisResult) -> List[EditCandidate]:
        words = analysis.data.get("words", [])
        if not words:
            return []
        # 対象フィラーを正規化（空白除去）した文字列に。長い順に見る。
        fillers = sorted(
            {normalize_word("".join(str(f).split())) for f in self.opt("words", DEFAULT_FILLERS)} - {""},
            key=len, reverse=True,
        )
        if not fillers:
            return []
        padding = float(self.opt("padding_sec", 0.0))

        # 正規化した各単語を連結し、各文字→単語index の対応を作る。
        norm = [normalize_word(w.text) for w in words]
        concat, char_word = "", []
        for wi, nw in enumerate(norm):
            for ch in nw:
                concat += ch
                char_word.append(wi)
        if not concat:
            return []

        def _boundary_start(a: int) -> bool:
            return a == 0 or char_word[a] != char_word[a - 1]

        def _boundary_end(b: int) -> bool:
            return b == len(concat) or char_word[b] != char_word[b - 1]

        used_words: set = set()
        matches = []  # (start_word, end_word)
        for f in fillers:
            pos = 0
            while True:
                p = concat.find(f, pos)
                if p < 0:
                    break
                end = p + len(f)
                pos = end
                # 単語境界にちょうど一致する時だけ採用（語内部の部分一致は除外）。
                if not (_boundary_start(p) and _boundary_end(end)):
                    continue
                wa, wb = char_word[p], char_word[end - 1]
                if any(wi in used_words for wi in range(wa, wb + 1)):
                    continue
                matches.append((wa, wb))
                used_words.update(range(wa, wb + 1))

        matches.sort()
        candidates: List[EditCandidate] = []
        for wa, wb in matches:
            start = max(0.0, words[wa].start - padding)
            end_t = words[wb].end + padding
            phrase = join_words([words[wi].text for wi in range(wa, wb + 1)])
            candidates.append(
                EditCandidate(TimeRange(start, end_t), EditAction.CUT, "filler", reason=f"フィラー「{phrase}」")
            )
        return candidates

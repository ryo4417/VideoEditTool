"""重複除去ルール（内容ベース）。

文字起こしの単語列から、直後に同じ語句が繰り返される箇所（言い直しの前半、
録り直しの重複など）を検出し、最初の1回を CUT 候補にする。
語句長の範囲は config で管理する（ハードコード禁止）。
"""
from __future__ import annotations

import re
from typing import List

from core.models import AnalysisResult, EditAction, EditCandidate, TimeRange
from core.registry import RULES
from core.rule import BaseRule

DEFAULT_MIN_WORDS = 1
DEFAULT_MAX_WORDS = 6


def _normalize(text: str) -> str:
    return re.sub(r"[\s、。,.!?！？]+", "", text).lower()


@RULES.register("duplicate")
class DuplicateRule(BaseRule):
    def apply(self, analysis: AnalysisResult) -> List[EditCandidate]:
        words = analysis.data.get("words", [])
        n = len(words)
        if n < 2:
            return []

        norm = [_normalize(w.text) for w in words]
        min_w = int(self.opt("min_words", DEFAULT_MIN_WORDS))
        max_w = int(self.opt("max_words", DEFAULT_MAX_WORDS))

        candidates: List[EditCandidate] = []
        i = 0
        while i < n:
            matched = False
            for w in range(max_w, min_w - 1, -1):
                if i + 2 * w > n:
                    continue
                first, second = norm[i:i + w], norm[i + w:i + 2 * w]
                if first == second and all(first):
                    phrase = "".join(words[j].text for j in range(i, i + w))
                    candidates.append(
                        EditCandidate(
                            time_range=TimeRange(words[i].start, words[i + w - 1].end),
                            action=EditAction.CUT,
                            rule="duplicate",
                            reason=f"重複「{phrase}」",
                        )
                    )
                    i += w  # コピー側から継続（3連続以上も順次拾う）
                    matched = True
                    break
            if not matched:
                i += 1
        return candidates

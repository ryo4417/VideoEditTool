"""言い直しルール — 方式B: 類似句方式。

隣接する語句が「完全一致ではないが高い割合で語を共有する」場合、
言い直し（同じ内容を少し変えて言い直した前半）とみなし、最初の試行を
CUT 候補にする。完全一致は duplicate ルールの領域なので除外する。
語数範囲・類似度しきい値は config 管理。
"""
from __future__ import annotations

import re
from typing import List

from core.models import AnalysisResult, EditAction, EditCandidate, TimeRange
from core.registry import RULES
from core.rule import BaseRule

DEFAULT_MIN_WORDS = 2
DEFAULT_MAX_WORDS = 6
DEFAULT_SIM_THRESHOLD = 0.6

# 助詞・語尾など機能語。これらの共有だけでは「言い直し」と判定しない
# （例:「今日は」「明日は」は は の共有のみ→言い直しではない）。
FUNCTION_WORDS = {
    "は", "が", "を", "に", "へ", "と", "で", "も", "の", "や", "から", "まで",
    "です", "ます", "だ", "た", "て", "し", "か", "ね", "よ", "な", "ん",
}


def _normalize(text: str) -> str:
    return re.sub(r"[\s、。,.!?！？]+", "", text).lower()


@RULES.register("restate")
class RestateRule(BaseRule):
    """方式B: 隣接する類似句の前半をカット。"""

    def apply(self, analysis: AnalysisResult) -> List[EditCandidate]:
        words = analysis.data.get("words", [])
        n = len(words)
        if n < 4:
            return []

        norm = [_normalize(w.text) for w in words]
        min_w = int(self.opt("min_words", DEFAULT_MIN_WORDS))
        max_w = int(self.opt("max_words", DEFAULT_MAX_WORDS))
        sim = float(self.opt("sim_threshold", DEFAULT_SIM_THRESHOLD))

        candidates: List[EditCandidate] = []
        i = 0
        while i < n:
            matched = False
            for w in range(max_w, min_w - 1, -1):
                if i + 2 * w > n:
                    continue
                a, b = norm[i:i + w], norm[i + w:i + 2 * w]
                if not all(a) or not all(b) or a == b:
                    continue  # 空・完全一致(=duplicate)は対象外
                shared = set(a) & set(b)
                # 機能語（助詞・語尾）だけの共有は言い直しではない。
                if not (shared - FUNCTION_WORDS):
                    continue
                overlap = len(shared) / w
                if overlap >= sim:
                    phrase = "".join(words[j].text for j in range(i, i + w))
                    candidates.append(
                        EditCandidate(
                            time_range=TimeRange(words[i].start, words[i + w - 1].end),
                            action=EditAction.CUT,
                            rule="restate",
                            reason=f"言い直し（類似 {overlap:.0%}「{phrase}」）",
                        )
                    )
                    i += w
                    matched = True
                    break
            if not matched:
                i += 1
        return candidates

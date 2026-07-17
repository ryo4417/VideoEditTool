"""フィラー除去ルール（内容ベース）。

文字起こしの単語列（AnalysisResult.data["words"]）から、フィラー語
（「えー」「あの」「um」等）を検出して CUT 候補にする。
対象語は config で管理し、コードを変えずに追加・変更できる（ハードコード禁止）。
"""
from __future__ import annotations

import re
from typing import List

from core.models import AnalysisResult, EditAction, EditCandidate, TimeRange
from core.registry import RULES
from core.rule import BaseRule

# 既定のフィラー語（config.rules.filler.words で上書き可能）。
DEFAULT_FILLERS = ["えー", "えーと", "えっと", "あのー", "あの", "あー", "まあ", "その", "um", "uh", "er"]


def _normalize(text: str) -> str:
    # 前後の記号・空白を除去して比較用に正規化。
    return re.sub(r"[\s、。,.!?！？]+", "", text).lower()


@RULES.register("filler")
class FillerRule(BaseRule):
    def apply(self, analysis: AnalysisResult) -> List[EditCandidate]:
        words = analysis.data.get("words", [])
        if not words:
            return []

        fillers = {_normalize(f) for f in self.opt("words", DEFAULT_FILLERS)}
        padding = float(self.opt("padding_sec", 0.0))

        candidates: List[EditCandidate] = []
        for w in words:
            if _normalize(w.text) in fillers:
                start = max(0.0, w.start - padding)
                end = w.end + padding
                candidates.append(
                    EditCandidate(
                        time_range=TimeRange(start, end),
                        action=EditAction.CUT,
                        rule="filler",
                        reason=f"フィラー「{w.text}」",
                    )
                )
        return candidates

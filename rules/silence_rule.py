"""無音カットルール。

"silence" 特徴を読み、一定長を超える無音を CUT 候補にする。
発話の直前直後に余白（padding）を残せるようにする。
"""
from __future__ import annotations

from typing import List

from core.models import AnalysisResult, EditAction, EditCandidate, TimeRange
from core.registry import RULES
from core.rule import BaseRule

DEFAULT_MIN_CUT_SEC = 0.5
DEFAULT_KEEP_PADDING_SEC = 0.1


@RULES.register("silence")
class SilenceRule(BaseRule):
    def apply(self, analysis: AnalysisResult) -> List[EditCandidate]:
        min_cut = float(self.opt("min_cut_sec", DEFAULT_MIN_CUT_SEC))
        padding = float(self.opt("keep_padding_sec", DEFAULT_KEEP_PADDING_SEC))

        candidates: List[EditCandidate] = []
        for silence in analysis.get("silence"):
            # 前後に padding を残して内側だけカットする。
            cut_start = silence.start + padding
            cut_end = silence.end - padding
            if cut_end <= cut_start:
                continue  # padding や負のconfigで逆転/ゼロになる区間は無条件スキップ
            if cut_end - cut_start < min_cut:
                continue
            candidates.append(
                EditCandidate(
                    time_range=TimeRange(cut_start, cut_end),
                    action=EditAction.CUT,
                    rule="silence",
                    reason=f"無音 {silence.duration:.2f}s (>{min_cut}s)",
                )
            )
        return candidates

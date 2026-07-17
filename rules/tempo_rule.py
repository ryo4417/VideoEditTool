"""テンポ調整ルール（間の短縮）。

長い無音（間）の「超過分」だけをカットし、目標の間（target_pause_sec）を残す。
無音を全て消す silence ルールと違い、自然な間を残してテンポを整える。
速度変更（再エンコード）ではなくカットで実現し、カットリスト/NLE出力と整合する。

無音の "silence" 特徴を使う（analysis.silence を有効にしておく）。
"""
from __future__ import annotations

from typing import List

from core.models import AnalysisResult, EditAction, EditCandidate, TimeRange
from core.registry import RULES
from core.rule import BaseRule

DEFAULT_TARGET_PAUSE_SEC = 0.4
DEFAULT_MIN_GAP_SEC = 0.6


@RULES.register("tempo")
class TempoRule(BaseRule):
    def apply(self, analysis: AnalysisResult) -> List[EditCandidate]:
        target = float(self.opt("target_pause_sec", DEFAULT_TARGET_PAUSE_SEC))
        min_gap = float(self.opt("min_gap_sec", DEFAULT_MIN_GAP_SEC))

        candidates: List[EditCandidate] = []
        for gap in analysis.get("silence"):
            if gap.duration <= max(min_gap, target):
                continue
            # 間の先頭に target 分だけ残し、残りをカット。
            cut_start = gap.start + target
            cut_end = gap.end
            if cut_end - cut_start <= 0:
                continue
            candidates.append(
                EditCandidate(
                    time_range=TimeRange(cut_start, cut_end),
                    action=EditAction.CUT,
                    rule="tempo",
                    reason=f"テンポ: {gap.duration:.2f}sの間を{target}sに短縮",
                )
            )
        return candidates

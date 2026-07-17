"""品質チェッカー（AIなしベースライン）。

編集結果からルールベースで「編集レポート」を生成する（仕様書 §9）。
AIは使わず、まず動く土台を提供する。将来 config.ai.enabled=true のとき
AI補助（採点・改善案）でこのレポートを拡張する（別ブランチで開発予定）。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from core.models import EditAction, EditCandidate, MediaInfo, TimeRange

DEFAULT_MAX_REMOVED_RATIO = 0.6      # これを超える削除率は警告
DEFAULT_WARN_MIN_SEGMENT_SEC = 0.5   # これ未満の残り区間は警告


@dataclass
class QualityReport:
    source: str
    total_duration: float
    kept_duration: float
    removed_duration: float
    removed_ratio: float
    num_cuts: int
    num_segments: int
    shortest_segment: float
    longest_segment: float
    warnings: List[str] = field(default_factory=list)
    ai_assisted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class QualityChecker:
    def __init__(self, options: Dict[str, Any] | None = None):
        options = options or {}
        self.max_removed_ratio = float(
            options.get("max_removed_ratio", DEFAULT_MAX_REMOVED_RATIO)
        )
        self.warn_min_segment = float(
            options.get("warn_min_segment_sec", DEFAULT_WARN_MIN_SEGMENT_SEC)
        )

    def check(
        self,
        media: MediaInfo,
        candidates: List[EditCandidate],
        keep_segments: List[TimeRange],
    ) -> QualityReport:
        kept = sum(s.duration for s in keep_segments)
        total = media.duration
        removed = max(0.0, total - kept)
        ratio = (removed / total) if total > 0 else 0.0
        durations = [s.duration for s in keep_segments]

        warnings: List[str] = []
        if ratio > self.max_removed_ratio:
            warnings.append(
                f"削除率が高い: {ratio:.0%} (>{self.max_removed_ratio:.0%})。カットしすぎの可能性。"
            )
        if not keep_segments:
            warnings.append("残る区間がありません（全カット）。設定を確認してください。")
        short = [d for d in durations if d < self.warn_min_segment]
        if short:
            warnings.append(
                f"短い残り区間が {len(short)} 件あります (<{self.warn_min_segment}s)。細切れの可能性。"
            )

        return QualityReport(
            source=media.path,
            total_duration=round(total, 3),
            kept_duration=round(kept, 3),
            removed_duration=round(removed, 3),
            removed_ratio=round(ratio, 4),
            num_cuts=sum(1 for c in candidates if c.action == EditAction.CUT),
            num_segments=len(keep_segments),
            shortest_segment=round(min(durations), 3) if durations else 0.0,
            longest_segment=round(max(durations), 3) if durations else 0.0,
            warnings=warnings,
        )

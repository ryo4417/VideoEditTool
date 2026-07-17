"""共通データ構造。

全モジュールが共有する不変（に近い）データ型を定義する。
処理ロジックは持たせず、データ表現に責務を限定する。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


@dataclass(frozen=True)
class TimeRange:
    """秒単位の時間区間 [start, end)。"""

    start: float
    end: float

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"end({self.end}) < start({self.start})")

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def overlaps(self, other: "TimeRange") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass
class MediaInfo:
    """入力メディアのメタ情報（ffprobe 由来）。"""

    path: str
    duration: float
    has_audio: bool = False
    has_video: bool = False
    width: int = 0
    height: int = 0
    fps: float = 0.0


@dataclass
class AnalysisResult:
    """解析結果のコンテナ。

    features は「特徴名 -> 区間リスト」の汎用辞書。
    アナライザは既存キーに縛られず新しい特徴を追加できる（拡張ポイント）。
    例: {"silence": [...], "speech": [...]}
    """

    media: MediaInfo
    features: Dict[str, List[TimeRange]] = field(default_factory=dict)

    def add(self, feature: str, ranges: List[TimeRange]) -> None:
        self.features.setdefault(feature, []).extend(ranges)

    def get(self, feature: str) -> List[TimeRange]:
        return self.features.get(feature, [])


class EditAction(str, Enum):
    CUT = "cut"
    KEEP = "keep"


@dataclass
class EditCandidate:
    """編集候補。ルールが生成し、確認・書き出しで使う。"""

    time_range: TimeRange
    action: EditAction
    rule: str
    reason: str = ""
    confidence: float = 1.0


def complement_ranges(
    ranges: List[TimeRange], total: float, start: float = 0.0
) -> List[TimeRange]:
    """[start, total] 区間から ranges を除いた補集合を返す。

    無音→発話、カット→残す区間 のように「区間の反転」を共通化する。
    """
    ordered = sorted(ranges, key=lambda r: r.start)
    segments: List[TimeRange] = []
    cursor = start
    for r in ordered:
        s = max(r.start, start)
        if s > cursor:
            segments.append(TimeRange(cursor, s))
        cursor = max(cursor, min(r.end, total))
    if cursor < total:
        segments.append(TimeRange(cursor, total))
    return segments


@dataclass
class Timeline:
    """編集タイムライン。カット区間から残す区間（keep）を導出する。"""

    media: MediaInfo
    cuts: List[TimeRange] = field(default_factory=list)

    def keep_segments(self) -> List[TimeRange]:
        """カットの補集合 = 残す区間。"""
        return complement_ranges(self.cuts, self.media.duration)

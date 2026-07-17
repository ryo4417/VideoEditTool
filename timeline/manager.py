"""タイムライン管理。

編集候補（CUT）からタイムラインを構築し、
残す区間（keep）の整形（近接マージ・短区間除去）を行う。
"""
from __future__ import annotations

from typing import List

from core.models import (
    EditAction,
    EditCandidate,
    MediaInfo,
    TimeRange,
    Timeline,
)

DEFAULT_MERGE_GAP_SEC = 0.2
DEFAULT_MIN_SEGMENT_SEC = 0.3


class TimelineManager:
    def __init__(self, options: dict | None = None):
        options = options or {}
        self.merge_gap = float(options.get("merge_gap_sec", DEFAULT_MERGE_GAP_SEC))
        self.min_segment = float(options.get("min_segment_sec", DEFAULT_MIN_SEGMENT_SEC))

    def build(self, media: MediaInfo, candidates: List[EditCandidate]) -> Timeline:
        cuts = [c.time_range for c in candidates if c.action == EditAction.CUT]
        return Timeline(media=media, cuts=cuts)

    def refine_keep_segments(self, timeline: Timeline) -> List[TimeRange]:
        """keep 区間を近接マージし、短すぎる区間を除去する。"""
        segments = timeline.keep_segments()
        merged = self._merge_close(segments)
        return [s for s in merged if s.duration >= self.min_segment]

    def _merge_close(self, segments: List[TimeRange]) -> List[TimeRange]:
        if not segments:
            return []
        ordered = sorted(segments, key=lambda r: r.start)
        merged = [ordered[0]]
        for seg in ordered[1:]:
            last = merged[-1]
            if seg.start - last.end <= self.merge_gap:
                merged[-1] = TimeRange(last.start, max(last.end, seg.end))
            else:
                merged.append(seg)
        return merged

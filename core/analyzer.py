"""アナライザ基底クラス。

各アナライザは独立し、交換可能（仕様書 §8）。
入力メディアを解析し、AnalysisResult に特徴を書き込む責務だけを持つ。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from core.models import AnalysisResult, MediaInfo


class BaseAnalyzer(ABC):
    """解析プラグインの共通インタフェース。"""

    #: features 辞書に書き込む特徴名
    feature: str = ""

    def __init__(self, options: Dict[str, Any] | None = None):
        self.options = options or {}

    @abstractmethod
    def analyze(self, media: MediaInfo, result: AnalysisResult) -> None:
        """media を解析し、result に特徴を追記する。"""
        raise NotImplementedError

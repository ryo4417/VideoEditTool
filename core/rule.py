"""編集ルール基底クラス。

ルールは解析結果から編集候補（EditCandidate）を生成する。
無音・重複・言い直し・テンポ・フィラー等は、この基底を継承して独立実装する
（仕様書 §6）。内容は固定せず、後から自由に追加できる。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from core.models import AnalysisResult, EditCandidate


class BaseRule(ABC):
    """編集ルールの共通インタフェース。"""

    def __init__(self, options: Dict[str, Any] | None = None):
        self.options = options or {}

    def opt(self, key: str, default: Any = None) -> Any:
        """設定値を取得（マジックナンバー禁止のため既定値も明示）。"""
        return self.options.get(key, default)

    @abstractmethod
    def apply(self, analysis: AnalysisResult) -> List[EditCandidate]:
        """解析結果から編集候補を生成して返す。"""
        raise NotImplementedError

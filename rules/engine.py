"""ルールエンジン。

config の rules セクションを読み、enabled なルールだけを
レジストリから生成して順に適用し、編集候補を集約する。
コードを変えずに config で ON/OFF・追加ができる（仕様書 §7）。
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.models import AnalysisResult, EditCandidate
from core.registry import RULES
from core.rule import BaseRule


class RuleEngine:
    def __init__(self, rules_config: Dict[str, Any]):
        self._rules: List[BaseRule] = []
        for name, options in (rules_config or {}).items():
            options = options or {}
            if not options.get("enabled", False):
                continue
            if name not in RULES.names():
                # 未登録のルールは無視せず気づけるようにする。
                raise KeyError(f"未登録のルール: '{name}' (登録済み: {RULES.names()})")
            self._rules.append(RULES.create(name, options))

    @property
    def active_rules(self) -> List[str]:
        return [type(r).__name__ for r in self._rules]

    def run(self, analysis: AnalysisResult) -> List[EditCandidate]:
        candidates: List[EditCandidate] = []
        for rule in self._rules:
            candidates.extend(rule.apply(analysis))
        return candidates

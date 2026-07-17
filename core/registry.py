"""プラグインレジストリ。

アナライザ・ルールを名前で登録／取得する仕組み。
新しい解析やルールは、このレジストリに登録するだけで
エンジン側のコードを変更せずに追加できる（仕様書 §6, §8「後から追加可能」）。
"""
from __future__ import annotations

from typing import Callable, Dict, Type, TypeVar

T = TypeVar("T")


class Registry:
    """名前 -> クラス の登録簿。"""

    def __init__(self, kind: str):
        self._kind = kind
        self._items: Dict[str, Type] = {}

    def register(self, name: str) -> Callable[[Type[T]], Type[T]]:
        def decorator(cls: Type[T]) -> Type[T]:
            if name in self._items:
                raise ValueError(f"{self._kind} '{name}' は既に登録済みです")
            self._items[name] = cls
            return cls
        return decorator

    def create(self, name: str, *args, **kwargs):
        if name not in self._items:
            raise KeyError(f"未登録の{self._kind}: '{name}' (登録済み: {sorted(self._items)})")
        return self._items[name](*args, **kwargs)

    def names(self):
        return sorted(self._items)


# グローバルなレジストリ（アナライザ用／ルール用）。
ANALYZERS = Registry("analyzer")
RULES = Registry("rule")

"""ルール共通のテキスト処理（filler/duplicate/restate で共有）。

- normalize_word: 比較用の正規化（記号・空白除去 + lower）
- join_words: 表示用に語を結合（英語など空白言語は空白を復元、日本語は詰める）

core には置かない（core は他モジュールに依存しない一方向のため、rules 内で共有）。
"""
from __future__ import annotations

import re
from typing import List

_PUNCT = re.compile(r"[\s、。,.!?！？]+")
_WORDISH = re.compile(r"[0-9A-Za-z]")


def normalize_word(text: str) -> str:
    return _PUNCT.sub("", text).lower()


def join_words(texts: List[str]) -> str:
    """語を人間が読める形に結合する。

    直前の末尾と次の先頭が両方ASCII語字なら空白を挿入（英語: I think）、
    それ以外は詰める（日本語: 今日は）。
    """
    out = ""
    for t in texts:
        # 直前が語字または句読点、次が語字なら空白を入れる（英語 "know, let" を自然に）。
        if out and (_WORDISH.match(out[-1]) or out[-1] in ",.;:!?") and _WORDISH.match(t[:1] or " "):
            out += " " + t
        else:
            out += t
    return out

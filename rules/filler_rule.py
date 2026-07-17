"""フィラー除去ルール（内容ベース・複数語句対応）。

文字起こしの単語列から、フィラー語（「えー」「あの」「um」「you know」等）を
検出して CUT 候補にする。対象語は config 管理で、**複数語のフレーズも指定可能**
（例: "you know"）。単語1語ずつしか照合しない実装だと句が空振りするため、
連続する単語列に対してスライド照合する。
"""
from __future__ import annotations

from typing import List

from core.models import AnalysisResult, EditAction, EditCandidate, TimeRange
from core.registry import RULES
from core.rule import BaseRule
from rules._text import join_words, normalize_word

# 既定のフィラー（config.rules.filler.words で上書き可能）。多語句も可。
DEFAULT_FILLERS = [
    "えー", "えーと", "えっと", "あのー", "あの", "あー", "まあ", "その",
    "um", "uh", "er", "ah", "hmm", "you know",
]


@RULES.register("filler")
class FillerRule(BaseRule):
    def apply(self, analysis: AnalysisResult) -> List[EditCandidate]:
        words = analysis.data.get("words", [])
        n = len(words)
        if n == 0:
            return []

        # フィラーを「正規化済みトークン列」の集合にする（多語句対応）。
        seqs = set()
        for f in self.opt("words", DEFAULT_FILLERS):
            seq = tuple(s for s in (normalize_word(w) for w in str(f).split()) if s)
            if seq:
                seqs.add(seq)
        if not seqs:
            return []
        max_len = max(len(s) for s in seqs)
        padding = float(self.opt("padding_sec", 0.0))

        norm = [normalize_word(w.text) for w in words]
        candidates: List[EditCandidate] = []
        i = 0
        while i < n:
            matched = False
            for L in range(min(max_len, n - i), 0, -1):
                if tuple(norm[i:i + L]) in seqs:
                    start = max(0.0, words[i].start - padding)
                    end = words[i + L - 1].end + padding
                    phrase = join_words([words[j].text for j in range(i, i + L)])
                    candidates.append(
                        EditCandidate(
                            time_range=TimeRange(start, end),
                            action=EditAction.CUT,
                            rule="filler",
                            reason=f"フィラー「{phrase}」",
                        )
                    )
                    i += L
                    matched = True
                    break
            if not matched:
                i += 1
        return candidates

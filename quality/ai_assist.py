"""AI補助による品質評価（ローカルLLM）。

仕様書 §9: AIは補助のみ（品質採点・編集漏れ確認・改善案）。必須ではなく、
AIが使えない環境でも編集は無音/ルールベースで完結する。

ローカルLLM は Ollama（http://localhost:11434, オフライン）を用いる。
追加依存を避けるため HTTP は標準ライブラリ(urllib)で呼ぶ。
差し替え可能なインタフェースにし、既定は NullAssessor（何もしない）。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AIAssessment:
    score: float | None = None                       # 0-100 の品質スコア（任意）
    suggestions: List[str] = field(default_factory=list)
    missed_edits: List[str] = field(default_factory=list)
    provider: str = "null"
    error: str = ""


class AIQualityAssessor(ABC):
    @abstractmethod
    def assess(self, media, candidates, keep_segments, report) -> AIAssessment:
        raise NotImplementedError


class NullAssessor(AIQualityAssessor):
    """AI無効時のフォールバック。"""

    def assess(self, media, candidates, keep_segments, report) -> AIAssessment:
        return AIAssessment(provider="null")


class OllamaAssessor(AIQualityAssessor):
    """ローカル Ollama による品質評価。"""

    def __init__(self, model: str = "llama3.1", host: str = "http://localhost:11434",
                 timeout: float = 60.0):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    def assess(self, media, candidates, keep_segments, report) -> AIAssessment:
        prompt = self._build_prompt(report)
        try:
            text = self._call(prompt)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            # AIは補助。失敗しても編集は成立するので、エラーを載せて空で返す。
            return AIAssessment(provider="ollama", error=f"Ollama接続失敗: {e}")
        return self._parse(text)

    def _build_prompt(self, report) -> str:
        r = report.to_dict() if hasattr(report, "to_dict") else dict(report)
        facts = (
            f"総尺={r.get('total_duration')}秒, 残時間={r.get('kept_duration')}秒, "
            f"削除率={r.get('removed_ratio')}, カット数={r.get('num_cuts')}, "
            f"残区間数={r.get('num_segments')}, 警告={r.get('warnings')}"
        )
        return (
            "あなたは動画編集の品質レビュアーです。以下のカット編集結果を評価し、"
            "必ず次のJSONのみを出力してください（前後に文章を付けない）:\n"
            '{"score": 0-100の整数, "suggestions": ["改善案", ...], '
            '"missed_edits": ["編集漏れの疑い", ...]}\n'
            f"編集結果: {facts}\n"
        )

    def _call(self, prompt: str) -> str:
        payload = json.dumps({
            "model": self.model, "prompt": prompt, "stream": False, "format": "json",
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/generate", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body.get("response", "")

    def _parse(self, text: str) -> AIAssessment:
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return AIAssessment(provider="ollama", error="LLM応答をJSONとして解釈できませんでした",
                                suggestions=[text.strip()[:200]] if text else [])
        score = data.get("score")
        return AIAssessment(
            provider="ollama",
            score=float(score) if isinstance(score, (int, float)) else None,
            suggestions=[str(s) for s in data.get("suggestions", []) if s],
            missed_edits=[str(s) for s in data.get("missed_edits", []) if s],
        )


def get_assessor(ai_config: Dict[str, Any]) -> AIQualityAssessor:
    """config.ai から Assessor を選ぶ。enabled=false / provider=null なら NullAssessor。"""
    if not ai_config.get("enabled", False):
        return NullAssessor()
    provider = ai_config.get("provider", "null")
    if provider == "null":
        return NullAssessor()
    if provider == "ollama":
        return OllamaAssessor(
            model=ai_config.get("model", "llama3.1"),
            host=ai_config.get("host", "http://localhost:11434"),
        )
    raise NotImplementedError(f"未対応のAIプロバイダ: '{provider}'")

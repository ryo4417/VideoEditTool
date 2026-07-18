"""発話内容の文字起こし（ローカル Whisper）。

オフライン完結（仕様書 §9 の「AIが使えない環境でも編集できる」）を守るため、
差し替え可能な Transcriber インタフェースにし、既定は NullTranscriber（何もしない）。
ローカル Whisper は faster-whisper を用いる（重い依存のため任意インストール）。

文字起こしは「補助」であり、無効でも編集は無音ベースで完結する。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Word:
    """単語（またはトークン）と時間。"""

    start: float
    end: float
    text: str


class Transcriber(ABC):
    @abstractmethod
    def transcribe(self, media_path: str) -> List[Word]:
        raise NotImplementedError


class NullTranscriber(Transcriber):
    """文字起こし無効時のフォールバック。"""

    def transcribe(self, media_path: str) -> List[Word]:
        return []


# モデルは重いので (name, device, compute_type) ごとに使い回す（連続解析の高速化）。
_MODEL_CACHE: Dict[tuple, Any] = {}


def _get_model(name: str, device: str, compute_type: str):
    key = (name, device, compute_type)
    if key not in _MODEL_CACHE:
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError(
                "faster-whisper が未インストールです。"
                "`pip install faster-whisper` を実行してください（ローカルWhisper用）。"
            ) from e
        _MODEL_CACHE[key] = WhisperModel(name, device=device, compute_type=compute_type)
    return _MODEL_CACHE[key]


class FasterWhisperTranscriber(Transcriber):
    """ローカル Whisper（faster-whisper）による文字起こし。

    依存は遅延 import。未インストールなら分かりやすく失敗させる。
    モデルはプロセス内でキャッシュして使い回す。
    """

    def __init__(
        self,
        model: str = "base",
        language: Optional[str] = None,
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        self.model = model
        self.language = language
        self.device = device
        self.compute_type = compute_type

    def transcribe(self, media_path: str) -> List[Word]:
        wm = _get_model(self.model, self.device, self.compute_type)
        # vad_filter: 無音/BGM区間での幻聴（存在しない発話の生成）を抑える。
        segments, _info = wm.transcribe(
            media_path, language=self.language, word_timestamps=True, vad_filter=True
        )
        words: List[Word] = []
        for seg in segments:
            for w in (getattr(seg, "words", None) or []):
                if w.start is None or w.end is None:
                    continue  # まれにタイムスタンプ欠落があるため防御
                words.append(Word(start=float(w.start), end=float(w.end), text=w.word.strip()))
        return words


def get_transcriber(cfg: Dict[str, Any]) -> Transcriber:
    """config.analysis.transcript から Transcriber を選ぶ。

    enabled=false または provider=null なら NullTranscriber。
    """
    if not cfg.get("enabled", False):
        return NullTranscriber()
    provider = cfg.get("provider", "whisper")
    if provider == "null":
        return NullTranscriber()
    if provider in ("whisper", "faster-whisper"):
        return FasterWhisperTranscriber(
            model=cfg.get("model", "small"),
            language=cfg.get("language"),
            device=cfg.get("device", "cpu"),
            compute_type=cfg.get("compute_type", "int8"),
        )
    raise NotImplementedError(f"未対応の文字起こしプロバイダ: '{provider}'")

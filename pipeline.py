"""処理パイプライン（アプリ配線層）。

仕様書 §5 の基本フローを実装する:
    読み込み -> 解析 -> 編集候補生成 -> (確認) -> 書き出し

core（純粋な共通層）には依存させず、各モジュールをここで組み合わせる。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from core import ffmpeg
from core.config import Config
from core.models import AnalysisResult, EditCandidate, MediaInfo, TimeRange
from core.registry import ANALYZERS
from export import exporters
from plugins.builtin import load_builtins
from quality.checker import QualityChecker, QualityReport
from rules.engine import RuleEngine
from timeline.manager import TimelineManager


@dataclass
class PipelineResult:
    media: MediaInfo
    analysis: AnalysisResult
    candidates: List[EditCandidate]
    keep_segments: List[TimeRange]
    report: QualityReport
    outputs: List[str] = field(default_factory=list)


class Pipeline:
    def __init__(self, config: Config):
        load_builtins()
        self.config = config

    def run(self, input_path: str, output_dir: str | None = None) -> PipelineResult:
        # 1. 読み込み
        media = ffmpeg.probe(input_path)

        # 2. 解析（config で enabled のアナライザのみ）
        analysis = AnalysisResult(media=media)
        for name, options in self._enabled(self.config.section("analysis")):
            analyzer = ANALYZERS.create(name, options)
            analyzer.analyze(media, analysis)

        # 3. 編集候補生成
        engine = RuleEngine(self.config.section("rules"))
        candidates = engine.run(analysis)

        # 4. タイムライン構築・整形（確認用の keep 区間）
        tl_manager = TimelineManager(self.config.section("timeline"))
        timeline = tl_manager.build(media, candidates)
        keep_segments = tl_manager.refine_keep_segments(timeline)

        # 4.5 品質チェック（AIなしベースライン。確認・レポート用）
        checker = QualityChecker(self.config.section("quality"))
        report = checker.check(media, candidates, keep_segments)

        # 5. 書き出し
        outputs = self._export(media, candidates, keep_segments, report, output_dir)

        return PipelineResult(
            media=media,
            analysis=analysis,
            candidates=candidates,
            keep_segments=keep_segments,
            report=report,
            outputs=outputs,
        )

    @staticmethod
    def _enabled(section: Dict[str, Any]):
        for name, options in (section or {}).items():
            options = options or {}
            if options.get("enabled", False):
                yield name, options

    def _export(
        self,
        media: MediaInfo,
        candidates: List[EditCandidate],
        keep_segments: List[TimeRange],
        report: QualityReport,
        output_dir: str | None,
    ) -> List[str]:
        export_cfg = self.config.section("export")
        out_dir = Path(output_dir or export_cfg.get("output_dir", "output"))
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(media.path).stem

        outputs: List[str] = []
        if self.config.get("quality.report", False):
            outputs.append(
                exporters.export_report(report.to_dict(), str(out_dir / f"{stem}.report.json"))
            )
        fmt = export_cfg.get("format", "json")
        if fmt == "json":
            outputs.append(
                exporters.export_json(
                    media, candidates, keep_segments, str(out_dir / f"{stem}.json")
                )
            )
        elif fmt == "edl":
            outputs.append(
                exporters.export_edl(media, keep_segments, str(out_dir / f"{stem}.edl"))
            )
        elif fmt == "html":
            outputs.append(
                exporters.export_html(
                    media, candidates, keep_segments, report.to_dict(),
                    str(out_dir / f"{stem}.html"),
                )
            )
        elif fmt == "fcpxml":
            outputs.append(
                exporters.export_fcpxml(media, keep_segments, str(out_dir / f"{stem}.fcpxml"))
            )
        else:
            raise ValueError(f"未対応の export format: {fmt}")

        if export_cfg.get("render", False) and keep_segments:
            ext = export_cfg.get("render_ext", "mp4")
            outputs.append(
                exporters.render(media, keep_segments, str(out_dir / f"{stem}_edited.{ext}"))
            )
        return outputs

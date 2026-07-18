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
from quality.ai_assist import NullAssessor, get_assessor
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

    def analyze(self, input_path: str) -> PipelineResult:
        """読み込み→解析→候補→整形→品質チェックまで（書き出しはしない）。

        GUI など「確認してから書き出す」用途はこれを使う。
        """
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

        # 4-4.5 タイムライン整形 + 品質チェック
        keep_segments, report = self._keep_and_report(media, candidates)

        # silence と tempo のカットが実際に重なった時だけ警告（設定だけの空振り警告は出さない）。
        sil = [c.time_range for c in candidates if c.rule == "silence"]
        tmp = [c.time_range for c in candidates if c.rule == "tempo"]
        if any(a.overlaps(b) for a in sil for b in tmp):
            report.warnings.append(
                "silence と tempo のカットが重複しています（無音の扱いが競合する可能性）。"
            )

        # 4.6 AI補助（任意・ローカルLLM）。無効時は何もしない＝ベースラインのまま。
        #     AIは補助のため、失敗しても編集は成立させる（警告に載せるだけ）。
        assessor = get_assessor(self.config.section("ai"))
        if not isinstance(assessor, NullAssessor):
            assessment = assessor.assess(media, candidates, keep_segments, report)
            report.ai_assisted = True
            report.ai_score = assessment.score
            report.ai_suggestions = assessment.suggestions + assessment.missed_edits
            if assessment.error:
                report.warnings.append(f"AI補助: {assessment.error}")

        return PipelineResult(
            media=media,
            analysis=analysis,
            candidates=candidates,
            keep_segments=keep_segments,
            report=report,
        )

    def run(self, input_path: str, output_dir: str | None = None) -> PipelineResult:
        result = self.analyze(input_path)
        result.outputs = self._export(
            result.media, result.candidates, result.keep_segments, result.report, output_dir
        )
        return result

    def export_result(self, result: PipelineResult, output_dir: str | None = None) -> List[str]:
        """既に解析済みの result を（現在の config の形式で）書き出す。"""
        return self._export(
            result.media, result.candidates, result.keep_segments, result.report, output_dir
        )

    def _keep_and_report(self, media: MediaInfo, candidates: List[EditCandidate]):
        """候補（CUT）から keep 区間と品質レポートを算出する。"""
        tl_manager = TimelineManager(self.config.section("timeline"))
        timeline = tl_manager.build(media, candidates)
        keep_segments = tl_manager.refine_keep_segments(timeline)
        checker = QualityChecker(self.config.section("quality"))
        report = checker.check(media, candidates, keep_segments)
        return keep_segments, report

    def build_from_cuts(self, result: PipelineResult, cut_ranges) -> PipelineResult:
        """明示的なカット区間 [(start, end), ...] から結果を再構築する（GUI手編集用）。"""
        from core.models import EditAction, EditCandidate, TimeRange
        cands = []
        for s, e in cut_ranges:
            s, e = float(s), float(e)
            if e > s:
                cands.append(EditCandidate(TimeRange(s, e), EditAction.CUT, "manual", reason="手編集"))
        keep_segments, report = self._keep_and_report(result.media, cands)
        return PipelineResult(
            media=result.media, analysis=result.analysis, candidates=cands,
            keep_segments=keep_segments, report=report,
        )

    def recompute(self, result: PipelineResult, enabled_indices: List[int]) -> PipelineResult:
        """候補の採否（index の集合）に基づいて keep/report を再計算した結果を返す。

        GUI で候補をトグルしたときに使う。元の result は変更しない。
        """
        chosen = [result.candidates[i] for i in enabled_indices if 0 <= i < len(result.candidates)]
        keep_segments, report = self._keep_and_report(result.media, chosen)
        return PipelineResult(
            media=result.media,
            analysis=result.analysis,
            candidates=chosen,
            keep_segments=keep_segments,
            report=report,
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
        # stem_suffix でプロファイル別などに出力名を分けられる（上書き衝突回避）。
        stem = Path(media.path).stem + str(export_cfg.get("stem_suffix", ""))

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
                exporters.render(
                    media, keep_segments, str(out_dir / f"{stem}_edited.{ext}"),
                    audio_fade_sec=float(export_cfg.get("click_fade_sec", 0.0)),
                )
            )
        return outputs

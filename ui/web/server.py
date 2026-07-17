"""ローカルWeb GUI サーバ（標準ライブラリのみ）。

UIと処理を分離（仕様書 §4）: ここは HTTP 境界と JSON 変換だけを担当し、
編集ロジックは pipeline / 各モジュールに委譲する。追加の重い依存は入れない。

起動:
    python -m ui.web.server            # http://127.0.0.1:8000 を開く
    python -m ui.web.server --port 8080 --no-browser
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from core.config import ConfigError, load_config
from core.ffmpeg import FFmpegNotFound
from core.models import EditCandidate
from pipeline import Pipeline, PipelineResult

_STATIC = Path(__file__).parent / "static"

# 直近の解析結果をパス単位でキャッシュ（書き出し時に再解析＝再Whisperを避ける）。
_CACHE: dict[str, PipelineResult] = {}
_CACHE_LOCK = threading.Lock()


def _candidate_json(i: int, c: EditCandidate) -> dict:
    return {
        "index": i,
        "action": c.action.value,
        "rule": c.rule,
        "start": round(c.time_range.start, 3),
        "end": round(c.time_range.end, 3),
        "reason": c.reason,
    }


def _result_json(result: PipelineResult) -> dict:
    m = result.media
    return {
        "media": {
            "path": m.path, "name": Path(m.path).name, "duration": m.duration,
            "width": m.width, "height": m.height, "fps": m.fps,
            "has_audio": m.has_audio, "has_video": m.has_video,
        },
        "candidates": [_candidate_json(i, c) for i, c in enumerate(result.candidates)],
        "keep_segments": [{"start": s.start, "end": s.end} for s in result.keep_segments],
        "report": result.report.to_dict(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "VideoEditToolGUI/0.1"

    # --- ルーティング ---
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        params = parse_qs(parsed.query)
        try:
            if route == "/" or route == "/index.html":
                self._serve_static("index.html")
            elif route == "/api/analyze":
                self._api_analyze(params)
            elif route == "/media":
                self._serve_media(params)
            elif route == "/api/waveform":
                self._api_waveform(params)
            elif (_STATIC / Path(route).name).is_file() and route.count("/") == 1:
                # /app.js などの静的ファイル（basename のみ・ディレクトリ横断は不可）
                self._serve_static(Path(route).name)
            else:
                self._error(HTTPStatus.NOT_FOUND, f"not found: {route}")
        except (ConfigError, FileNotFoundError, FFmpegNotFound) as e:
            self._error(HTTPStatus.BAD_REQUEST, str(e))
        except Exception as e:  # noqa: BLE001  最低限のガード（GUIを落とさない）
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(e).__name__}: {e}")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/export":
                self._api_export()
            else:
                self._error(HTTPStatus.NOT_FOUND, f"not found: {parsed.path}")
        except (ConfigError, FileNotFoundError, FFmpegNotFound, ValueError) as e:
            self._error(HTTPStatus.BAD_REQUEST, str(e))
        except Exception as e:  # noqa: BLE001
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(e).__name__}: {e}")

    # --- API ---
    def _api_analyze(self, params: dict) -> None:
        path = _one(params, "path")
        profile = _one(params, "profile") or None
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(f"ファイルが見つかりません: {path}")
        config = load_config(profile)
        self._apply_toggles(config, params)
        result = Pipeline(config).analyze(path)
        with _CACHE_LOCK:
            _CACHE[path] = result
        self._json(_result_json(result))

    @staticmethod
    def _apply_toggles(config, params: dict) -> None:
        """GUIの解析オプション（rules / transcript）を config に反映する。"""
        transcript = _one(params, "transcript") == "1"
        rules_param = _one(params, "rules")
        if transcript:
            config.data.setdefault("analysis", {}).setdefault("transcript", {})["enabled"] = True
        if rules_param:
            requested = {r for r in rules_param.split(",") if r}
            for name, opts in config.section("rules").items():
                if isinstance(opts, dict):
                    opts["enabled"] = name in requested

    def _api_waveform(self, params: dict) -> None:
        path = _one(params, "path")
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(f"ファイルが見つかりません: {path}")
        buckets = int(_one(params, "buckets") or 400)
        from core import ffmpeg
        self._json({"peaks": ffmpeg.extract_waveform(path, buckets=buckets)})

    def _api_export(self) -> None:
        body = self._read_json()
        path = body.get("path")
        fmt = body.get("format", "json")
        render = bool(body.get("render", False))
        enabled = body.get("enabled_indices")
        profile = body.get("profile") or None
        output_dir = body.get("output_dir") or None

        with _CACHE_LOCK:
            cached = _CACHE.get(path)
        if cached is None:
            raise ValueError("先に解析してください（キャッシュ無し）")

        config = load_config(profile)
        config.data.setdefault("export", {})["format"] = fmt
        if render:
            config.data.setdefault("export", {})["render"] = True
        pipe = Pipeline(config)

        target = cached
        if isinstance(enabled, list):
            target = pipe.recompute(cached, [int(i) for i in enabled])
        outputs = pipe.export_result(target, output_dir)
        self._json({"outputs": outputs})

    # --- 静的/メディア配信 ---
    def _serve_static(self, name: str) -> None:
        file = _STATIC / name
        if not file.is_file():
            self._error(HTTPStatus.NOT_FOUND, f"missing static: {name}")
            return
        data = file.read_bytes()
        ctype = mimetypes.guess_type(str(file))[0] or "application/octet-stream"
        self._raw(HTTPStatus.OK, data, ctype)

    def _serve_media(self, params: dict) -> None:
        """<video> 用にローカル動画を Range 対応で配信する。"""
        path = _one(params, "path")
        if not path or not os.path.isfile(path):
            self._error(HTTPStatus.NOT_FOUND, "media not found")
            return
        size = os.path.getsize(path)
        ctype = mimetypes.guess_type(path)[0] or "video/mp4"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        status = HTTPStatus.OK
        if rng and rng.startswith("bytes="):
            part = rng.split("=", 1)[1].split("-")
            start = int(part[0]) if part[0] else 0
            end = int(part[1]) if len(part) > 1 and part[1] else size - 1
            end = min(end, size - 1)
            status = HTTPStatus.PARTIAL_CONTENT
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            self.wfile.write(f.read(length))

    # --- 低レベルヘルパ ---
    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def _json(self, obj: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._raw(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json")

    def _raw(self, status: HTTPStatus, data: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8" if "json" in ctype or "html" in ctype else ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json({"error": message}, status)

    def log_message(self, *args) -> None:  # 既定の逐次ログを抑制
        return


def _one(params: dict, key: str) -> str:
    values = params.get(key)
    return values[0] if values else ""


def serve(port: int = 8000, open_browser: bool = True) -> None:
    address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(address, Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"VideoEditTool GUI: {url}  (Ctrl+C で終了)")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n終了します。")
    finally:
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VideoEditTool ローカルGUI")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="ブラウザを自動で開かない")
    args = parser.parse_args(argv)
    serve(port=args.port, open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

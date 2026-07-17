"""試用サンプル動画を生成する（音のトーン + 無音ギャップ）。

使い方: python scripts/make_sample.py [出力パス]
既定で ./sample.mp4 を作る。ffmpeg が必要。
"""
import os
import subprocess
import sys


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "sample.mp4"
    # 12秒。3-5秒 と 8-9秒 を無音（volume 0）にしたテスト動画。
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=duration=12:size=640x360:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
        "-af", "volume='if(between(t,3,5)+between(t,8,9),0,1)':eval=frame",
        "-shortest", "-c:v", "libx264", "-c:a", "aac", out,
    ]
    subprocess.run(cmd, check=True)
    print("生成しました:", os.path.abspath(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import xml.etree.ElementTree as ET

from core.models import MediaInfo, TimeRange
from export.exporters import build_fcpxml


def test_fcpxml_is_wellformed_and_has_clips():
    media = MediaInfo(path="dir/sample.mp4", duration=10.0, has_video=True,
                      has_audio=True, width=1280, height=720, fps=25.0)
    keep = [TimeRange(0, 4), TimeRange(6, 10)]
    doc = build_fcpxml(media, keep)

    # DOCTYPE を除いて整形式XMLとしてパースできること
    body = doc.split("<!DOCTYPE fcpxml>\n", 1)[1]
    root = ET.fromstring(body)
    assert root.tag == "fcpxml"

    clips = root.findall(".//asset-clip")
    assert len(clips) == 2
    # 有理数(フレーム)表記。fps=25 で keep [0,4),[6,10)
    assert clips[0].get("start") == "0/25s"
    assert clips[1].get("start") == "150/25s"   # 6s * 25
    assert clips[1].get("offset") == "100/25s"  # 1つ目の長さ 4s * 25
    # 各クリップの offset+duration が次の offset に一致（ギャップ/重複なし）
    o0, d0 = clips[0].get("offset"), clips[0].get("duration")
    assert o0 == "0/25s" and d0 == "100/25s"


def test_fcpxml_frameduration_from_fps():
    media = MediaInfo(path="x.mp4", duration=5.0, fps=30.0)
    doc = build_fcpxml(media, [TimeRange(0, 5)])
    assert 'frameDuration="1/30s"' in doc

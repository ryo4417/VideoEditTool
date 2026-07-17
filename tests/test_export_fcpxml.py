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
    # 2つ目のクリップの offset は1つ目の duration(4s)分ずれる
    assert clips[1].get("offset") == "4.000s"
    assert clips[0].get("start") == "0.000s"
    assert clips[1].get("start") == "6.000s"


def test_fcpxml_frameduration_from_fps():
    media = MediaInfo(path="x.mp4", duration=5.0, fps=30.0)
    doc = build_fcpxml(media, [TimeRange(0, 5)])
    assert 'frameDuration="1/30s"' in doc

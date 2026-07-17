from core.ffmpeg import _parse_silence_log


def test_parse_silence_log():
    stderr = """
[silencedetect @ 0x1] silence_start: 1.234
[silencedetect @ 0x1] silence_end: 3.456 | silence_duration: 2.222
[silencedetect @ 0x1] silence_start: 10.0
[silencedetect @ 0x1] silence_end: 11.5 | silence_duration: 1.5
"""
    ranges = _parse_silence_log(stderr)
    assert len(ranges) == 2
    assert (round(ranges[0].start, 3), round(ranges[0].end, 3)) == (1.234, 3.456)
    assert (ranges[1].start, ranges[1].end) == (10.0, 11.5)


def test_parse_empty_log():
    assert _parse_silence_log("no silence here") == []

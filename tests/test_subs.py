from app.subs import parse_subtitles

SRT = """1
00:00:01,000 --> 00:00:02,500
Hola món

2
00:00:03,000 --> 00:00:04,000
Adeu <i>amic</i>
"""

VTT = """WEBVTT

00:01.000 --> 00:02.500
Hola món

00:00:03.000 --> 00:00:04.000
Adeu
"""


def test_parse_srt():
    segs = parse_subtitles(SRT)
    assert segs[0] == {"start": 1.0, "end": 2.5, "text": "Hola món"}
    assert segs[1]["text"] == "Adeu amic"  # tags stripped


def test_parse_vtt():
    segs = parse_subtitles(VTT)
    assert segs[0]["start"] == 1.0 and segs[0]["end"] == 2.5
    assert segs[1]["start"] == 3.0

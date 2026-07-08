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


def test_clean_auto_collapses_rolling_captions():
    # ventana rodante típica de YouTube: cada cue repite la línea anterior
    segs = [
        {"start": 0.0, "end": 2.0, "text": "hola a tothom"},
        {"start": 2.0, "end": 2.1, "text": "hola a tothom"},          # duplicado
        {"start": 2.1, "end": 4.0, "text": "hola a tothom com esteu"},
        {"start": 4.0, "end": 6.0, "text": "com esteu molt bé gràcies"},
        {"start": 6.0, "end": 6.5, "text": "   "},                    # vacío
    ]
    from app import subs as subs_mod
    out = subs_mod.clean_auto(segs)
    assert [s["text"] for s in out] == \
        ["hola a tothom", "com esteu", "molt bé gràcies"]
    assert out[0]["end"] == 2.1        # el duplicado extendió el final

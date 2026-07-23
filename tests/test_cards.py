"""Generación de media de la tarjeta: el GIF de streams sale de una ventana
local descargada (si no, decodificar HD desde el stream agota el timeout y la
tarjeta cae a solo-imagen)."""
import json
from unittest.mock import patch

import app.main as main


def _session(tmp_path, source_type):
    main.CON = main.db.connect(tmp_path / "t.db")
    segs = [{"start": 2000.0, "end": 2003.0, "text": "Aquesta és una prova",
             "words": [], "tokens": main.nlp.naive_tokenize("Aquesta és una prova")}]
    return main.db.create_session(
        main.CON, title="s", source_type=source_type,
        media_path="http://x/v.mp4" if source_type == "stream" else "/local/v.mp4",
        srt_source="whisper", model_size="small", duration_secs=3000,
        transcript_json=json.dumps(segs))


def test_stream_card_uses_local_window_for_gif(tmp_path):
    sid = _session(tmp_path, "stream")
    s = main.db.get_session(main.CON, sid)
    calls = {}
    with patch.object(main.media, "download_window",
                      side_effect=lambda *a, **k: calls.setdefault("win", a)), \
         patch.object(main.media, "cut_audio"), \
         patch.object(main.media, "snapshot",
                      side_effect=lambda *a, **k: calls.setdefault("snap", a)), \
         patch.object(main.media, "animated_clip",
                      side_effect=lambda *a, **k: calls.setdefault("gif", a)), \
         patch.object(main.stream, "stream_url", return_value=(None, [], False)):
        p = main._build_preview(s, 0, "Aquesta")
    # se descargó la ventana y el GIF sale de ella con tiempos relativos (start=0)
    assert "win" in calls, "no se descargó la ventana del stream"
    gif_src, gif_start, gif_end = calls["gif"][0], calls["gif"][1], calls["gif"][2]
    assert gif_src.endswith("-win.mp4")
    assert gif_start == 0.0 and 0 < gif_end <= 6.5
    assert p["clip_file"].endswith(".gif")


def test_local_card_does_not_download_window(tmp_path):
    sid = _session(tmp_path, "local")
    s = main.db.get_session(main.CON, sid)
    calls = {}
    with patch.object(main.media, "download_window",
                      side_effect=AssertionError("no debería descargar ventana en local")), \
         patch.object(main.media, "cut_audio"), \
         patch.object(main.media, "snapshot"), \
         patch.object(main.media, "animated_clip",
                      side_effect=lambda *a, **k: calls.setdefault("gif", a)):
        main._build_preview(s, 0, "Aquesta")
    # el GIF usa la fuente y los tiempos originales
    gif_src, gif_start = calls["gif"][0], calls["gif"][1]
    assert gif_src == "/local/v.mp4"
    assert gif_start == 2000.0

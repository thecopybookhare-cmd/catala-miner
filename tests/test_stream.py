from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as main
from app import stream


def test_progressive_filters_dash_and_audio_only():
    info = {"formats": [
        {"format_id": "dash-a", "height": None, "vcodec": "none",
         "acodec": "mp4a", "protocol": "http_dash_segments",
         "format_note": "DASH audio", "url": "u"},
        {"format_id": "360p", "height": 360, "vcodec": None, "acodec": None,
         "protocol": "https", "format_note": None, "url": "u360"},
        {"format_id": "576p", "height": 576, "vcodec": None, "acodec": None,
         "protocol": "https", "format_note": None, "url": "u576"},
        {"format_id": "dash-v", "height": 720, "vcodec": "avc1",
         "acodec": "none", "protocol": "http_dash_segments",
         "format_note": "DASH video", "url": "u"},
        {"format_id": "18", "height": 360, "vcodec": "avc1", "acodec": "mp4a",
         "protocol": "https", "format_note": "360p", "url": "u18"},
    ]}
    out = stream._progressive(info)
    heights = [f["height"] for f in out]
    assert heights == [360, 576]               # progresivos, dedup por altura, DASH fuera
    assert all(f["url"].startswith("u") for f in out)


def test_is_direct():
    assert stream.is_direct("https://x.com/a.mp4")
    assert stream.is_direct("https://x.com/a.m3u8?t=1")
    assert not stream.is_direct("https://youtube.com/watch?v=abc")


_FAKE_INFO = {"title": "T", "duration": 10, "formats": [
    {"height": 360, "vcodec": "avc1", "acodec": "mp4a",
     "protocol": "https", "format_note": "360p", "url": "u360"}]}


def test_resolve_caches_within_ttl():
    stream._CACHE.clear()
    calls = {"n": 0}

    def fake_extract(url):
        calls["n"] += 1
        return _FAKE_INFO
    with patch("app.stream._extract", side_effect=fake_extract):
        r1 = stream.resolve("https://x/v")
        r2 = stream.resolve("https://x/v")
    assert r1 and r1 == r2
    assert calls["n"] == 1                      # la 2ª vez viene de la caché
    stream._CACHE.clear()


def test_resolve_does_not_cache_failures():
    stream._CACHE.clear()
    calls = {"n": 0}

    def boom(url):
        calls["n"] += 1
        raise RuntimeError("x")
    with patch("app.stream._extract", side_effect=boom):
        assert stream.resolve("https://y/v") == {}
        assert stream.resolve("https://y/v") == {}
    assert calls["n"] == 2                       # los fallos reintentan, no se cachean


def _client(tmp_path):
    main.CON = main.db.connect(tmp_path / "t.db")
    return TestClient(main.app)


def _wait(jid):
    import time
    t0 = time.time()
    while time.time() - t0 < 10:
        j = main.jobs.get(jid)
        if j["status"] in ("done", "error"):
            return j
        time.sleep(0.05)
    raise TimeoutError


@patch("app.main.stream.resolve")
def test_stream_session_creates_and_reresolves(mock_resolve, tmp_path):
    mock_resolve.return_value = {
        "title": "Merlí Cap7", "duration": 3024.0,
        "formats": [{"height": 360, "label": "360p", "url": "u360"},
                    {"height": 576, "label": "576p", "url": "u576"}],
        "best_url": "u576", "best_height": 576,
        "subs_url": "", "subs_auto": False}
    c = _client(tmp_path)
    r = c.post("/api/sessions/stream",
               json={"url": "https://www.3cat.cat/3cat/x/video/1/"}).json()
    j = _wait(r["job_id"])
    assert j["status"] == "done", j.get("message")
    sid = j["result"]["session_id"]
    d = c.get("/api/sessions/" + sid).json()
    assert d["source_type"] == "stream"
    assert d["media_url"] == ""                # el frontend pide URL fresca
    assert d["title"] == "Merlí Cap7"
    # URL fresca + cambio de altura
    with patch("app.main.stream.stream_url",
               return_value=("fresh576", [{"height": 360, "label": "360p"},
                                          {"height": 576, "label": "576p"}])):
        u = c.get(f"/api/sessions/{sid}/stream-url").json()
        assert u["url"] == "fresh576"
        assert {h["height"] for h in u["heights"]} == {360, 576}


@patch("app.main.stream.resolve", return_value={})
def test_stream_session_error_when_unresolvable(_m, tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/sessions/stream",
               json={"url": "https://site.com/pagina"}).json()
    j = _wait(r["job_id"])
    assert j["status"] == "error"
    assert "Importar" in j["message"]

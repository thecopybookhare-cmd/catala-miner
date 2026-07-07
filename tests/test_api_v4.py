import json
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as main


def client(tmp_path):
    main.CON = main.db.connect(tmp_path / "t.db")
    return TestClient(main.app)


# ---------- sesiones por URL ----------

@patch("app.main.media.duration", return_value=120.5)
def test_url_session_streams_directly(_dur, tmp_path):
    c = client(tmp_path)
    url = "https://cdn.example.com/videos/merli.mp4?token=abc"
    r = c.post("/api/sessions/url", json={"url": url}).json()
    sid = r["session_id"]
    d = c.get("/api/sessions/" + sid).json()
    assert d["source_type"] == "url"
    assert d["media_url"] == url            # streaming directo, sin proxy
    assert d["title"] == "merli.mp4"
    assert d["duration_secs"] == 120.5


@patch("app.main.media.duration", return_value=0.0)
def test_url_session_rejects_unreadable(_dur, tmp_path):
    c = client(tmp_path)
    r = c.post("/api/sessions/url",
               json={"url": "https://example.com/nada.mp4"})
    assert r.status_code == 400


def test_url_session_rejects_non_http(tmp_path):
    c = client(tmp_path)
    r = c.post("/api/sessions/url", json={"url": "file:///etc/passwd"})
    assert r.status_code == 400


# ---------- configuración ----------

def test_settings_defaults_and_merge(tmp_path):
    c = client(tmp_path)
    s = c.get("/api/settings").json()
    assert s["deck"] == "Català::Mining"
    assert s["keymap"]["next"] == "d"
    # POST parcial: cambia una clave y una tecla, el resto persiste
    r = c.post("/api/settings",
               json={"sub_scale": 1.3, "keymap": {"next": "l"}}).json()
    assert r["sub_scale"] == 1.3
    assert r["keymap"]["next"] == "l"
    assert r["keymap"]["prev"] == "a"      # intacta
    assert c.get("/api/settings").json()["sub_scale"] == 1.3


def test_settings_rejects_bad_keymap_and_unknown(tmp_path):
    c = client(tmp_path)
    # tecla duplicada con otra acción
    assert c.post("/api/settings",
                  json={"keymap": {"next": "a"}}).status_code == 400
    assert c.post("/api/settings", json={"invent": 1}).status_code == 400

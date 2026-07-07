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

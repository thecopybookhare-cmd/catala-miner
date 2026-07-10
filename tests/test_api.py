from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as main


def client(tmp_path):
    main.CON = main.db.connect(tmp_path / "t.db")
    return TestClient(main.app)


def test_health_and_empty_sessions(tmp_path):
    c = client(tmp_path)
    assert c.get("/api/health").json()["ok"] is True
    assert c.get("/api/sessions").json() == []


@patch("app.main.translate.translate", side_effect=lambda t: "ES:" + t)
@patch("app.main.media.cut_audio")
@patch("app.main.media.snapshot")
def test_card_preview_uses_context(_snap, _cut, _tr, tmp_path):
    import json
    c = client(tmp_path)
    sid = main.db.create_session(
        main.CON, title="V", source_type="local", media_path="/x.mp4",
        srt_source="whisper", model_size="small", duration_secs=10,
        transcript_json=json.dumps([{"start": 1.0, "end": 2.0,
                                     "text": "El gos corre",
                                     "words": [], "logprob": 0.0,
                                     "tokens": []}]))
    r = c.post("/api/cards/preview",
               json={"session_id": sid, "segment_index": 0,
                     "selection": "gos"})
    body = r.json()
    assert body["frase_es"] == "ES:El gos corre"
    assert body["paraula_es"] == "ES:gos"
    assert body["audio_file"].endswith(".mp3")
    assert body["image_file"].endswith(".jpg")

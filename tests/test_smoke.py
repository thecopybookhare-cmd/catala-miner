import shutil
import subprocess
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
import app.main as main


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="no ffmpeg")
@patch("app.main.translate.translate", side_effect=lambda t: "[es] " + t)
def test_upload_preview_card_flow(_tr, tmp_path):
    main.CON = main.db.connect(tmp_path / "t.db")
    c = TestClient(main.app)
    wav = tmp_path / "clip.wav"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=330:duration=4", str(wav)],
                   check=True, capture_output=True)
    with wav.open("rb") as f:
        r = c.post("/api/sessions/upload",
                   files={"file": ("clip.wav", f, "audio/wav")}).json()
    sid = r["session_id"]
    # inject a fake transcript (whisper itself not exercised here)
    import json
    segs = [{"start": 0.5, "end": 2.0, "text": "Bon dia a tothom",
             "words": [], "logprob": -0.3,
             "tokens": main.nlp.naive_tokenize("Bon dia a tothom")}]
    main.db.update_transcript(main.CON, sid, json.dumps(segs), "small", "whisper")

    p = c.post("/api/cards/preview",
               json={"session_id": sid, "segment_index": 0,
                     "selection": "tothom"}).json()
    assert p["frase_es"].startswith("[es]")
    assert (main.config.MEDIA_DIR / p["audio_file"]).exists()

    r = c.post("/api/cards", json={
        "session_id": sid, "segment_index": 0, "paraula": p["paraula"],
        "lema": p["lema"], "pos": p["pos"], "paraula_es": p["paraula_es"],
        "frase": p["frase"], "frase_es": p["frase_es"],
        "freq_rank": p["freq_rank"], "audio_file": p["audio_file"],
        "image_file": p["image_file"], "font": p["font"]}).json()
    assert r["card_id"]
    assert r["pending"] >= 0

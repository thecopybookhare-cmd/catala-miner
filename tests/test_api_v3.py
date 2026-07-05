import json
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as main


def client(tmp_path):
    main.CON = main.db.connect(tmp_path / "t.db")
    return TestClient(main.app)


def _seg_session(text="Ets molt intel·ligent, tu."):
    return main.db.create_session(
        main.CON, title="V", source_type="local", media_path="/x.mp4",
        srt_source="whisper", model_size="small", duration_secs=10,
        transcript_json=json.dumps([{"start": 1.0, "end": 2.0, "text": text,
                                     "words": [], "logprob": 0.0,
                                     "tokens": []}]))


def test_senses_prefer_lemma_over_surface():
    d = main.dictionary.Dictionary(
        {"ets": [("ETS", "n")], "ser": [("ser", "vbser"), ("estar", "vblex")]})
    assert main._senses("ets", "ser", d)[0][0] == "ser"
    # multi-palabra: superficie primero
    d2 = main.dictionary.Dictionary({"poc a poc": [("despacio", "adv")]})
    assert main._senses("poc a poc", "poc a poc", d2) == [("despacio", "adv")]


def test_active_sense_matches_sentence_translation():
    senses = [("estar", "vblex"), ("perro", "n")]
    assert main._active_sense(senses, "El perro corre por ahí.", "") == 1
    assert main._active_sense(senses, "nada que ver", "perro") == 1
    assert main._active_sense(senses, "nada", "nada") == 0
    assert main._active_sense([], "x", "x") == -1


@patch("app.main.ipa.ipa", return_value="/əts/")
@patch("app.main.translate.sentence", side_effect=lambda t: "ES:" + t)
@patch("app.main.translate.translate",
       side_effect=lambda t: "eres" if t == "ets" else "T:" + t)
def test_lookup_word_es_uses_lowercase_form(_tr, _sen, _ipa, tmp_path,
                                            monkeypatch):
    from app import forms
    c = client(tmp_path)
    monkeypatch.setattr(forms, "known_exact", lambda w: False)
    monkeypatch.setattr(forms, "knows_lower", lambda w: w.lower() == "ets")
    r = c.post("/api/lookup",
               json={"selection": "Ets",
                     "sentence": "Ets molt intel·ligent, tu."}).json()
    assert r["word_es"] == "eres"
    assert r["ipa"] == "/əts/"
    assert "active" in r

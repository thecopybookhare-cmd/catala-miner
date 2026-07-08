import json
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as main


def client(tmp_path):
    main.CON = main.db.connect(tmp_path / "t.db")
    return TestClient(main.app)


# ---------- sesiones por URL ----------

def _wait_job(jid, timeout=10):
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = main.jobs.get(jid)
        if j["status"] in ("done", "error"):
            return j
        time.sleep(0.05)
    raise TimeoutError(jid)


@patch("app.main.media.duration", return_value=120.5)
def test_url_session_streams_directly(_dur, tmp_path):
    c = client(tmp_path)
    url = "https://cdn.example.com/videos/merli.mp4?token=abc"
    r = c.post("/api/sessions/url", json={"url": url}).json()
    j = _wait_job(r["job_id"])
    assert j["status"] == "done", j["message"]
    sid = j["result"]["session_id"]
    d = c.get("/api/sessions/" + sid).json()
    assert d["source_type"] == "url"
    assert d["media_url"] == url            # streaming directo, sin proxy
    assert d["title"] == "merli.mp4"
    assert d["duration_secs"] == 120.5


@patch("app.main.media.duration", return_value=0.0)
def test_url_session_rejects_unreadable(_dur, tmp_path):
    c = client(tmp_path)
    r = c.post("/api/sessions/url",
               json={"url": "https://example.com/nada.mp4"}).json()
    j = _wait_job(r["job_id"])
    assert j["status"] == "error"
    assert "no se pudo leer" in j["message"]


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


# ---------- ejemplos / tts / define ----------

def _mk_session(title, text, lemma):
    return main.db.create_session(
        main.CON, title=title, source_type="local", media_path="/x.mp4",
        srt_source="srt", model_size="-", duration_secs=10,
        transcript_json=json.dumps([{
            "start": 1.0, "end": 2.0, "text": text, "text_es": "",
            "words": [], "logprob": 0.0,
            "tokens": [{"t": text.split()[0], "lemma": lemma, "pos": "NOUN",
                        "is_word": True, "zipf": 4.0}]}]))


def test_examples_from_own_content_excludes_current(tmp_path):
    c = client(tmp_path)
    sid_a = _mk_session("A", "El gos corre", "gos")
    _mk_session("B", "Un gos petit", "gos")
    r = c.get(f"/api/examples?lemma=gos&session_id={sid_a}&index=0").json()
    texts = [e["text"] for e in r["examples"]]
    assert "Un gos petit" in texts
    assert "El gos corre" not in texts          # frase actual excluida


@patch("app.tts.shutil.which", return_value=None)
def test_tts_degrades_without_espeak(_which, tmp_path):
    c = client(tmp_path)
    assert c.get("/api/tts?text=gos").json() == {"file": ""}


def test_define_gated_by_online_setting(tmp_path):
    c = client(tmp_path)
    # online_enabled False por defecto -> ni siquiera hace la peticion
    assert c.get("/api/define?word=gos").json() == {"text": ""}


@patch("requests.get")
def test_define_extracts_catalan_section(mock_get, tmp_path):
    c = client(tmp_path)
    c.post("/api/settings", json={"online_enabled": True})
    mock_get.return_value.json.return_value = {
        "query": {"pages": {"1": {"extract":
            "== Català ==\nNom. Animal domèstic.\n== Espanyol ==\notro"}}}}
    r = c.get("/api/define?word=gos").json()
    assert "Animal domèstic" in r["text"]
    assert "otro" not in r["text"]


# ---------- export / import ----------

def test_export_import_roundtrip(tmp_path):
    c = client(tmp_path)
    main.db.set_word_status(main.CON, "gos", "known")
    main.db.set_word_status(main.CON, "casa", "learning")
    exp = c.get("/api/words/export")
    assert "attachment" in exp.headers["content-disposition"]
    data = exp.json()
    assert data["statuses"] == {"gos": "known", "casa": "learning"}

    # DB nueva: importar restaura
    main.CON = main.db.connect(tmp_path / "t2.db")
    r = c.post("/api/words/import",
               json={"statuses": data["statuses"]}).json()
    assert r["imported"] == 2 and r["skipped"] == 0
    assert main.db.word_statuses(main.CON) == data["statuses"]


def test_import_respects_local_without_overwrite(tmp_path):
    c = client(tmp_path)
    main.db.set_word_status(main.CON, "gos", "known")
    r = c.post("/api/words/import",
               json={"statuses": {"gos": "ignored", "nou": "learning",
                                  "malo": "invent"}}).json()
    assert r["imported"] == 1                      # solo "nou"
    assert r["skipped"] == 2                       # gos (local) + malo (inválido)
    assert main.db.word_statuses(main.CON)["gos"] == "known"


# ---------- vocabulario (Language Reactor) ----------

def test_vocab_ranks_lemmatizes_and_caches(monkeypatch):
    from app import vocab, forms
    monkeypatch.setattr(vocab, "_RANKS", None)
    monkeypatch.setattr(forms, "lookup",
                        lambda w: [("ser", "VERB")] if w in ("és", "sóc") else [])
    monkeypatch.setattr("wordfreq.top_n_list",
                        lambda lang, n: ["és", "sóc", "casa"])
    r = vocab.ranks()
    assert r["ser"] == 1          # primera aparición gana ("sóc" no lo pisa)
    assert r["casa"] == 3
    assert "sóc" not in r


def test_bulk_known_respects_existing(tmp_path, monkeypatch):
    from app import vocab
    monkeypatch.setattr(vocab, "_RANKS", {"ser": 1, "casa": 2, "gos": 3})
    c = client(tmp_path)
    main.db.set_word_status(main.CON, "casa", "learning")
    r = c.post("/api/words/bulk-known", json={"top_n": 2}).json()
    assert r["marked"] == 1                       # solo "ser"
    st = main.db.word_statuses(main.CON)
    assert st["ser"] == "known"
    assert st["casa"] == "learning"               # intacta
    assert "gos" not in st                        # rango 3 > top_n 2

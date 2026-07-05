import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import db, anki
import app.main as main


def client(tmp_path):
    main.CON = db.connect(tmp_path / "t.db")
    return TestClient(main.app)


def _card(con, sid, lema, note_id=None):
    cid = db.create_card(con, session_id=sid, segment_index=0,
                         paraula=lema, lema=lema, pos="NOUN",
                         paraula_es="x", frase="f", frase_es="fe",
                         freq_rank="common", audio_file="", image_file="",
                         font="")
    if note_id:
        db.mark_card_sent(con, cid, note_id)
    return cid


def test_status_roundtrip_and_unknown_deletes(tmp_path):
    con = db.connect(tmp_path / "t.db")
    db.set_word_status(con, "Gos", "known")
    assert db.word_statuses(con) == {"gos": "known"}
    db.set_word_status(con, "gos", "unknown")
    assert db.word_statuses(con) == {}


def test_mark_learning_respects_known_and_ignored(tmp_path):
    con = db.connect(tmp_path / "t.db")
    db.set_word_status(con, "casa", "known")
    db.mark_learning_if_new(con, "casa")
    assert db.word_statuses(con)["casa"] == "known"
    db.set_word_status(con, "taula", "ignored")
    db.mark_learning_if_new(con, "taula")
    assert db.word_statuses(con)["taula"] == "ignored"
    db.mark_learning_if_new(con, "gat")
    assert db.word_statuses(con)["gat"] == "learning"


def test_backfill_from_old_cards(tmp_path):
    con = db.connect(tmp_path / "t.db")
    sid = db.create_session(con, title="V", source_type="local",
                            media_path="/x", srt_source="srt",
                            model_size="-", duration_secs=1,
                            transcript_json="[]")
    _card(con, sid, "vell")
    con.execute("DELETE FROM word_status")  # simulate pre-v0.4 database
    con.commit()
    con2 = db.connect(tmp_path / "t.db")
    assert db.word_statuses(con2)["vell"] == "learning"


def test_api_set_status_and_session_payload(tmp_path):
    c = client(tmp_path)
    sid = db.create_session(main.CON, title="V", source_type="local",
                            media_path="/x", srt_source="srt",
                            model_size="-", duration_secs=1,
                            transcript_json="[]")
    r = c.post("/api/words/status",
               json={"lemma": "Gos", "status": "tracking"}).json()
    assert r == {"ok": True, "lemma": "gos", "status": "tracking"}
    assert c.post("/api/words/status",
                  json={"lemma": "x", "status": "nope"}).status_code == 400
    s = c.get("/api/sessions/" + sid).json()
    assert s["word_statuses"] == {"gos": "tracking"}


@patch("app.main.anki.note_intervals")
@patch("app.main.anki.is_up", return_value=True)
def test_sync_statuses_from_anki(_up, intervals, tmp_path):
    c = client(tmp_path)
    sid = db.create_session(main.CON, title="V", source_type="local",
                            media_path="/x", srt_source="srt",
                            model_size="-", duration_secs=1,
                            transcript_json="[]")
    _card(main.CON, sid, "madur", note_id=111)   # interval 30 -> known
    _card(main.CON, sid, "nou", note_id=222)     # interval 3  -> learning
    _card(main.CON, sid, "brut", note_id=333)    # ignored stays ignored
    db.set_word_status(main.CON, "brut", "ignored")
    intervals.return_value = {111: 30, 222: 3, 333: 40}
    r = c.post("/api/anki/sync-statuses").json()
    st = db.word_statuses(main.CON)
    assert st["madur"] == "known"
    assert st["nou"] == "learning"
    assert st["brut"] == "ignored"
    assert r["synced"] >= 1


@patch("app.anki.invoke")
def test_ensure_note_type_updates_existing_model(invoke):
    invoke.side_effect = lambda action, **kw: (
        ["CatalaMiner"] if action == "modelNames" else None)
    anki.ensure_note_type()
    actions = [c.args[0] for c in invoke.call_args_list]
    assert "updateModelTemplates" in actions
    assert "updateModelStyling" in actions
    assert "{{Frase}}" in anki.FRONT and "{{Audio}}" in anki.FRONT
    assert "{{Imatge}}" in anki.FRONT

import json
from app import db


def test_session_roundtrip(tmp_path):
    con = db.connect(tmp_path / "t.db")
    sid = db.create_session(con, title="Vid", source_type="local",
                            media_path="/x/v.mp4", srt_source="whisper",
                            model_size="small", duration_secs=12.5,
                            transcript_json=json.dumps([{"text": "hola"}]))
    s = db.get_session(con, sid)
    assert s["title"] == "Vid"
    assert json.loads(s["transcript_json"])[0]["text"] == "hola"
    assert [r["id"] for r in db.list_sessions(con)] == [sid]


def test_cards_and_known_lemmas(tmp_path):
    con = db.connect(tmp_path / "t.db")
    sid = db.create_session(con, title="V", source_type="local",
                            media_path="/x", srt_source="srt",
                            model_size="-", duration_secs=1,
                            transcript_json="[]")
    cid = db.create_card(con, session_id=sid, segment_index=0,
                         paraula="gossos", lema="gos", pos="NOUN",
                         paraula_es="perros", frase="Els gossos", frase_es="Los perros",
                         freq_rank="common", audio_file="a.mp3",
                         image_file="i.jpg", font="V @ 0:01")
    assert db.known_lemmas(con) == {"gos"}
    db.mark_card_sent(con, cid, anki_note_id=123)
    assert db.pending_cards(con) == []
    cid2 = db.create_card(con, session_id=sid, segment_index=1,
                          paraula="gat", lema="gat", pos="NOUN",
                          paraula_es="gato", frase="El gat", frase_es="El gato",
                          freq_rank="common", audio_file="b.mp3",
                          image_file="j.jpg", font="V @ 0:02")
    assert [c["id"] for c in db.pending_cards(con)] == [cid2]

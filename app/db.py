import sqlite3
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, source_type TEXT NOT NULL,
  media_path TEXT NOT NULL, srt_source TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'ca', model_size TEXT NOT NULL,
  duration_secs REAL, transcript_json TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cards (
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
  segment_index INTEGER NOT NULL,
  paraula TEXT NOT NULL, lema TEXT NOT NULL, pos TEXT,
  paraula_es TEXT, frase TEXT NOT NULL, frase_es TEXT,
  freq_rank TEXT, audio_file TEXT, image_file TEXT, font TEXT,
  anki_note_id INTEGER, status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL);
"""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    return con


def create_session(con, *, title, source_type, media_path, srt_source,
                   model_size, duration_secs, transcript_json) -> str:
    sid = uuid.uuid4().hex[:12]
    con.execute(
        "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (sid, title, source_type, media_path, srt_source, "ca",
         model_size, duration_secs, transcript_json, _now(), _now()))
    con.commit()
    return sid


def update_transcript(con, sid, transcript_json, model_size, srt_source):
    con.execute(
        "UPDATE sessions SET transcript_json=?, model_size=?, srt_source=?, "
        "updated_at=? WHERE id=?",
        (transcript_json, model_size, srt_source, _now(), sid))
    con.commit()


def get_session(con, sid):
    r = con.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    return dict(r) if r else None


def list_sessions(con):
    rs = con.execute(
        "SELECT id,title,source_type,srt_source,model_size,duration_secs,"
        "created_at FROM sessions ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rs]


def create_card(con, *, session_id, segment_index, paraula, lema, pos,
                paraula_es, frase, frase_es, freq_rank, audio_file,
                image_file, font) -> str:
    cid = uuid.uuid4().hex[:12]
    con.execute(
        "INSERT INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,'pending',?)",
        (cid, session_id, segment_index, paraula, lema, pos, paraula_es,
         frase, frase_es, freq_rank, audio_file, image_file, font, _now()))
    con.commit()
    return cid


def mark_card_sent(con, cid, anki_note_id):
    con.execute("UPDATE cards SET status='sent', anki_note_id=? WHERE id=?",
                (anki_note_id, cid))
    con.commit()


def pending_cards(con):
    rs = con.execute("SELECT * FROM cards WHERE status='pending'").fetchall()
    return [dict(r) for r in rs]


def known_lemmas(con) -> set[str]:
    rs = con.execute("SELECT DISTINCT lema FROM cards").fetchall()
    return {r["lema"] for r in rs}

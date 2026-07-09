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
CREATE TABLE IF NOT EXISTS word_status (
  lemma TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'ca',
  status TEXT NOT NULL,          -- learning | known | ignored | tracking
  updated_at TEXT NOT NULL,      -- absent row = unknown (Migaku default)
  PRIMARY KEY (lemma, language));
"""

WORD_STATUSES = {"unknown", "learning", "known", "ignored", "tracking"}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    # migración: versión del tokenizador con que se guardó la transcripción
    cols = {r["name"] for r in con.execute("PRAGMA table_info(sessions)")}
    if "tok_version" not in cols:
        con.execute("ALTER TABLE sessions ADD COLUMN tok_version "
                    "INTEGER NOT NULL DEFAULT 0")
    # migración multi-idioma: word_status pasa a PK (lemma, language)
    # migración streaming: URL de página + altura para re-resolver
    if "page_url" not in cols:
        con.execute("ALTER TABLE sessions ADD COLUMN page_url TEXT NOT NULL "
                    "DEFAULT ''")
    if "stream_height" not in cols:
        con.execute("ALTER TABLE sessions ADD COLUMN stream_height INTEGER "
                    "NOT NULL DEFAULT 0")
    ws_cols = {r["name"] for r in con.execute("PRAGMA table_info(word_status)")}
    if "language" not in ws_cols:
        con.executescript("""
        CREATE TABLE word_status_v2 (
          lemma TEXT NOT NULL, language TEXT NOT NULL DEFAULT 'ca',
          status TEXT NOT NULL, updated_at TEXT NOT NULL,
          PRIMARY KEY (lemma, language));
        INSERT INTO word_status_v2
          SELECT lemma, 'ca', status, updated_at FROM word_status;
        DROP TABLE word_status;
        ALTER TABLE word_status_v2 RENAME TO word_status;
        """)
    # backfill: lemmas mined before word_status existed become 'learning'
    con.execute(
        "INSERT OR IGNORE INTO word_status "
        "SELECT DISTINCT lema, 'ca', 'learning', ? FROM cards WHERE lema != ''",
        (_now(),))
    con.commit()
    return con


def create_session(con, *, title, source_type, media_path, srt_source,
                   model_size, duration_secs, transcript_json,
                   page_url="", stream_height=0) -> str:
    sid = uuid.uuid4().hex[:12]
    con.execute(
        "INSERT INTO sessions (id, title, source_type, media_path, srt_source,"
        " language, model_size, duration_secs, transcript_json, created_at,"
        " updated_at, page_url, stream_height) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, title, source_type, media_path, srt_source, "ca",
         model_size, duration_secs, transcript_json, _now(), _now(),
         page_url, stream_height))
    con.commit()
    return sid


def update_transcript(con, sid, transcript_json, model_size, srt_source,
                      tok_version=0):
    con.execute(
        "UPDATE sessions SET transcript_json=?, model_size=?, srt_source=?, "
        "tok_version=?, updated_at=? WHERE id=?",
        (transcript_json, model_size, srt_source, tok_version, _now(), sid))
    con.commit()


def get_session(con, sid):
    r = con.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    return dict(r) if r else None


def set_stream_height(con, sid, height):
    con.execute("UPDATE sessions SET stream_height=?, updated_at=? WHERE id=?",
                (height, _now(), sid))
    con.commit()


def list_sessions(con):
    rs = con.execute(
        "SELECT id,title,source_type,srt_source,model_size,duration_secs,"
        "created_at,updated_at,page_url FROM sessions ORDER BY created_at DESC"
    ).fetchall()
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


def mark_card_duplicate(con, cid):
    """Anki refused it as duplicate — drop from queue, don't retry forever."""
    con.execute("UPDATE cards SET status='duplicate' WHERE id=?", (cid,))
    con.commit()


def pending_cards(con):
    rs = con.execute("SELECT * FROM cards WHERE status='pending'").fetchall()
    return [dict(r) for r in rs]


def known_lemmas(con) -> set[str]:
    rs = con.execute("SELECT DISTINCT lema FROM cards").fetchall()
    return {r["lema"] for r in rs}


def set_word_status(con, lemma: str, status: str, lang: str = "ca"):
    lemma = lemma.strip().lower()
    if not lemma:
        return
    if status == "unknown":
        con.execute("DELETE FROM word_status WHERE lemma=? AND language=?",
                    (lemma, lang))
    else:
        con.execute(
            "INSERT INTO word_status VALUES (?,?,?,?) "
            "ON CONFLICT(lemma, language) DO UPDATE SET "
            "status=excluded.status, updated_at=excluded.updated_at",
            (lemma, lang, status, _now()))
    con.commit()


def word_statuses(con, lang: str = "ca") -> dict[str, str]:
    rs = con.execute("SELECT lemma, status FROM word_status "
                     "WHERE language=?", (lang,)).fetchall()
    return {r["lemma"]: r["status"] for r in rs}


def mark_learning_if_new(con, lemma: str, lang: str = "ca"):
    """Card created -> lemma becomes 'learning' unless already known/ignored."""
    cur = con.execute(
        "SELECT status FROM word_status WHERE lemma=? AND language=?",
        (lemma.strip().lower(), lang)).fetchone()
    if cur is None or cur["status"] == "tracking":
        set_word_status(con, lemma, "learning", lang)


def backup_daily(con, app_dir: Path, keep: int = 7):
    """Copia diaria de la DB (API backup de sqlite, segura con WAL);
    conserva las `keep` más recientes."""
    bdir = app_dir / "backups"
    bdir.mkdir(exist_ok=True)
    dest = bdir / time.strftime("app-%Y%m%d.db")
    if not dest.exists():
        out = sqlite3.connect(str(dest))
        with out:
            con.backup(out)
        out.close()
    for p in sorted(bdir.glob("app-*.db"))[:-keep]:
        p.unlink()


def cards_with_notes(con) -> list[dict]:
    rs = con.execute(
        "SELECT lema, anki_note_id FROM cards WHERE anki_note_id IS NOT NULL"
    ).fetchall()
    return [dict(r) for r in rs]

"""Glosas en español del Wikcionario para catalán (extracción kaikki.org,
~4 MB, descarga única, offline después). Complementa al bidix de Apertium
con definiciones más ricas. Degradación total a [] si no está disponible."""
import json
import sqlite3
from pathlib import Path

import requests

from . import config

URL = ("https://kaikki.org/eswiktionary/Catal%C3%A1n/"
       "kaikki.org-dictionary-Catal%C3%A1n.jsonl")
_JSONL_PATH = config.MODELS_DIR / "wikdict-ca.jsonl"
_DB_PATH = config.MODELS_DIR / "wikdict-ca.sqlite"

_CON = None
_TRIED = False


def build(jsonl_text: str, db_path: Path):
    """Vuelca el JSONL de kaikki a un índice sqlite word->glosas."""
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(str(db_path))
    con.execute("CREATE TABLE glosses (word TEXT, pos TEXT, gloss TEXT)")

    def rows():
        seen = set()
        for line in jsonl_text.splitlines():
            try:
                d = json.loads(line)
            except Exception:
                continue
            w = (d.get("word") or "").strip().lower()
            if not w:
                continue
            pos = d.get("pos") or ""
            for s in d.get("senses") or []:
                for g in s.get("glosses") or []:
                    g = " ".join(g.split())
                    key = (w, g.lower())
                    if g and key not in seen:
                        seen.add(key)
                        yield w, pos, g
    con.executemany("INSERT INTO glosses VALUES (?,?,?)", rows())
    con.execute("CREATE INDEX ix_gw ON glosses(word)")
    con.commit()
    con.close()


def _con():
    global _CON, _TRIED
    if _CON is None and not _TRIED:
        _TRIED = True
        try:
            if not _DB_PATH.exists():
                if not _JSONL_PATH.exists():
                    resp = requests.get(URL, timeout=120)
                    resp.raise_for_status()
                    _JSONL_PATH.write_text(resp.text, encoding="utf-8")
                build(_JSONL_PATH.read_text(encoding="utf-8"), _DB_PATH)
            _CON = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        except Exception:
            _CON = None
    return _CON


def lookup(term: str) -> list[tuple[str, str]]:
    """[(glosa_es, pos)] para el término (minúsculas)."""
    con = _con()
    if con is None or not term:
        return []
    rs = con.execute(
        "SELECT gloss, pos FROM glosses WHERE word=? LIMIT 6",
        (term.strip().lower(),)).fetchall()
    return [(r[0], r[1]) for r in rs]

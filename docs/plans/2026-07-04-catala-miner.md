# CatalàMiner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Local Migaku-style app: transcribe Catalan video (Whisper large-v3 fine-tuned for Catalan), browse tokenized subtitles, mine Anki flashcards with segment audio, video frame, and contextual ca→es translation — fully offline.

**Architecture:** Single FastAPI backend (Python 3.12 via `uv` venv) serving a vanilla-JS single page. Heavy work (Whisper, yt-dlp, ffmpeg) runs in background threads with polled job state. Translation = Softcatalà CTranslate2 model; dictionary senses = Apertium bidix XML parsed locally; tokens/lemmas = spaCy `ca_core_news_sm` with regex fallback; frequency = wordfreq. Cards go to Anki via AnkiConnect with a local pending queue.

**Tech Stack:** FastAPI, uvicorn, faster-whisper (`projecte-aina/faster-whisper-large-v3-ca-3catparla` default), ctranslate2 + sentencepiece, yt-dlp, spaCy, wordfreq, requests, SQLite (stdlib), ffmpeg CLI.

**Working dir:** `/Users/tomasplaza/Downloads/Github/catala-miner` — everything below is relative to it. Run tests with `./venv-run pytest` (wrapper created in Task 1).

**Data dir:** `~/Library/Application Support/CatalaMiner/` (db, media, downloads, hf cache).

---

### Task 1: Project scaffold + tooling

**Files:** Create `pyproject.toml`, `.gitignore`, `venv-run`, `app/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "catala-miner"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "python-multipart>=0.0.9",
  "requests>=2.32",
  "faster-whisper>=1.0",
  "ctranslate2>=4.0",
  "sentencepiece>=0.2",
  "huggingface_hub>=0.23",
  "yt-dlp>=2025.1.1",
  "spacy>=3.7",
  "wordfreq>=3.1",
]

[dependency-groups]
dev = ["pytest>=8.0", "httpx>=0.27"]
```

- [ ] **Step 2: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: Create venv and wrapper.** Run:

```bash
cd /Users/tomasplaza/Downloads/Github/catala-miner
brew list uv >/dev/null 2>&1 || brew install uv
uv venv --python 3.12 .venv
uv pip install -p .venv/bin/python -e . --group dev
printf '#!/bin/sh\nexec "$(dirname "$0")/.venv/bin/python" -m "$@"\n' > venv-run && chmod +x venv-run
```

Expected: venv created, deps resolve. If a dep lacks a 3.12 wheel, report — do not silently change versions.

- [ ] **Step 4: Create empty `app/__init__.py`, `tests/__init__.py`. Verify `./venv-run pytest --version` prints pytest 8.x. Commit** `chore: scaffold project`

---

### Task 2: Config module

**Files:** Create `app/config.py`

- [ ] **Step 1: Write `app/config.py`** (no test — constants only)

```python
from pathlib import Path
import os

PORT = 8977
ANKI_URL = "http://127.0.0.1:8765"

APP_DIR = Path.home() / "Library" / "Application Support" / "CatalaMiner"
MEDIA_DIR = APP_DIR / "media"
DL_DIR = APP_DIR / "downloads"
MODELS_DIR = APP_DIR / "models"
DB_PATH = APP_DIR / "app.db"

for d in (APP_DIR, MEDIA_DIR, DL_DIR, MODELS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# HF models cached inside our app dir, not ~/.cache
os.environ.setdefault("HF_HOME", str(MODELS_DIR / "hf"))

WHISPER_MODELS = {
    "catala-large": "projecte-aina/faster-whisper-large-v3-ca-3catparla",
    "large-v3": "large-v3",
    "small": "small",
}
DEFAULT_WHISPER = "catala-large"

TRANSLATE_REPO = "softcatala/translate-cat-spa"
BIDIX_URL = ("https://raw.githubusercontent.com/apertium/apertium-spa-cat/"
             "master/apertium-spa-cat.spa-cat.dix")

NOTE_TYPE = "CatalaMiner"
NOTE_FIELDS = ["Paraula", "ParaulaES", "Frase", "FraseES",
               "Audio", "Imatge", "Font", "Freq"]
```

- [ ] **Step 2: Commit** `feat: config`

---

### Task 3: Database layer (TDD)

**Files:** Create `app/db.py`, `tests/test_db.py`

- [ ] **Step 1: Write failing test `tests/test_db.py`**

```python
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
```

- [ ] **Step 2: Run `./venv-run pytest tests/test_db.py -q`** — expect FAIL (no `app.db`).

- [ ] **Step 3: Write `app/db.py`**

```python
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
```

- [ ] **Step 4: Run `./venv-run pytest tests/test_db.py -q`** — expect 2 passed.
- [ ] **Step 5: Commit** `feat: sqlite layer`

---

### Task 4: SRT/VTT parser (TDD)

**Files:** Create `app/subs.py`, `tests/test_subs.py`

- [ ] **Step 1: Failing test `tests/test_subs.py`**

```python
from app.subs import parse_subtitles

SRT = """1
00:00:01,000 --> 00:00:02,500
Hola món

2
00:00:03,000 --> 00:00:04,000
Adeu <i>amic</i>
"""

VTT = """WEBVTT

00:01.000 --> 00:02.500
Hola món

00:00:03.000 --> 00:00:04.000
Adeu
"""


def test_parse_srt():
    segs = parse_subtitles(SRT)
    assert segs[0] == {"start": 1.0, "end": 2.5, "text": "Hola món"}
    assert segs[1]["text"] == "Adeu amic"  # tags stripped


def test_parse_vtt():
    segs = parse_subtitles(VTT)
    assert segs[0]["start"] == 1.0 and segs[0]["end"] == 2.5
    assert segs[1]["start"] == 3.0
```

- [ ] **Step 2: Run it** — FAIL (no module).

- [ ] **Step 3: Write `app/subs.py`**

```python
import re

_TS = re.compile(
    r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{3})\s*-->\s*"
    r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{3})")
_TAG = re.compile(r"<[^>]+>")


def _secs(h, m, s, ms) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_subtitles(text: str) -> list[dict]:
    """Parse SRT or WebVTT into [{start, end, text}]. Strips markup tags."""
    segs = []
    cur = None
    for line in text.splitlines():
        m = _TS.search(line)
        if m:
            if cur and cur["text"]:
                segs.append(cur)
            g = m.groups()
            cur = {"start": _secs(*g[:4]), "end": _secs(*g[4:]), "text": ""}
        elif cur is not None:
            clean = _TAG.sub("", line).strip()
            if clean and not clean.isdigit():
                cur["text"] = (cur["text"] + " " + clean).strip()
    if cur and cur["text"]:
        segs.append(cur)
    return segs
```

- [ ] **Step 4: Run `./venv-run pytest tests/test_subs.py -q`** — 2 passed.
- [ ] **Step 5: Commit** `feat: srt/vtt parser`

---

### Task 5: Apertium bidix dictionary (TDD)

**Files:** Create `app/dictionary.py`, `tests/test_dictionary.py`

- [ ] **Step 1: Failing test `tests/test_dictionary.py`**

```python
from app.dictionary import parse_bidix, Dictionary

BIDIX = """<?xml version="1.0"?>
<dictionary>
  <section id="main" type="standard">
    <e><p><l>perro<s n="n"/><s n="m"/></l><r>gos<s n="n"/><s n="m"/></r></p></e>
    <e><p><l>can<s n="n"/><s n="m"/></l><r>gos<s n="n"/><s n="m"/></r></p></e>
    <e><p><l>echar<b/>de<b/>menos<s n="vblex"/></l><r>trobar<b/>a<b/>faltar<s n="vblex"/></r></p></e>
    <e r="LR"><p><l>solo<s n="adj"/></l><r>sol<s n="adj"/></r></p></e>
  </section>
</dictionary>"""


def test_lookup_catalan_to_spanish():
    d = Dictionary(parse_bidix(BIDIX))
    assert d.lookup("gos") == [("perro", "n"), ("can", "n")]
    assert d.lookup("trobar a faltar") == [("echar de menos", "vblex")]
    assert d.lookup("GOS") == [("perro", "n"), ("can", "n")]  # case-insensitive
    assert d.lookup("inexistent") == []
```

- [ ] **Step 2: Run it** — FAIL.

- [ ] **Step 3: Write `app/dictionary.py`**

```python
"""Apertium bidix (spa-cat) as a ca->es sense dictionary.

The bidix is downloaded once from GitHub (config.BIDIX_URL) and parsed as
plain XML — Apertium itself is never installed. <l> = Spanish, <r> = Catalan.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from . import config

_BIDIX_PATH = config.MODELS_DIR / "apertium-spa-cat.dix"


def _side_text(el) -> str:
    """Text of <l>/<r>: <b/> is a space; <s n=..> are grammar symbols."""
    parts = [el.text or ""]
    for child in el:
        if child.tag == "b":
            parts.append(" ")
        parts.append(child.tail or "")
    return "".join(parts).strip()


def _first_symbol(el) -> str:
    s = el.find("s")
    return s.get("n", "") if s is not None else ""


def parse_bidix(xml_text: str) -> dict[str, list[tuple[str, str]]]:
    """Return {catalan_lemma_lower: [(spanish, pos), ...]} preserving order."""
    root = ET.fromstring(xml_text)
    index: dict[str, list[tuple[str, str]]] = {}
    for e in root.iter("e"):
        p = e.find("p")
        if p is None:
            continue
        l, r = p.find("l"), p.find("r")
        if l is None or r is None:
            continue
        ca, es = _side_text(r), _side_text(l)
        if not ca or not es:
            continue
        entry = (es, _first_symbol(l))
        bucket = index.setdefault(ca.lower(), [])
        if entry not in bucket:
            bucket.append(entry)
    return index


class Dictionary:
    def __init__(self, index: dict[str, list[tuple[str, str]]]):
        self._index = index

    def lookup(self, term: str) -> list[tuple[str, str]]:
        return self._index.get(term.strip().lower(), [])


def load() -> Dictionary:
    """Load from disk cache, downloading the bidix on first use."""
    if not _BIDIX_PATH.exists():
        resp = requests.get(config.BIDIX_URL, timeout=60)
        resp.raise_for_status()
        _BIDIX_PATH.write_text(resp.text, encoding="utf-8")
    return Dictionary(parse_bidix(_BIDIX_PATH.read_text(encoding="utf-8")))
```

- [ ] **Step 4: Run `./venv-run pytest tests/test_dictionary.py -q`** — 1 passed.
- [ ] **Step 5: Commit** `feat: bidix dictionary`

---

### Task 6: NLP — tokens, lemmas, frequency (TDD on fallback path)

**Files:** Create `app/nlp.py`, `tests/test_nlp.py`

- [ ] **Step 1: Failing test `tests/test_nlp.py`**

```python
from app import nlp


def test_freq_badge_thresholds():
    assert nlp.freq_badge(5.6) == "common"
    assert nlp.freq_badge(4.0) == "medium"
    assert nlp.freq_badge(2.0) == "rare"
    assert nlp.freq_badge(0.0) == "rare"


def test_naive_tokenize_keeps_catalan_clitics():
    toks = nlp.naive_tokenize("N'hi ha molts, oi?")
    words = [t["t"] for t in toks if t["is_word"]]
    assert "N'hi" in words and "ha" in words and "molts" in words
    # punctuation preserved as non-word tokens
    assert any(t["t"] == "," and not t["is_word"] for t in toks)
```

- [ ] **Step 2: Run it** — FAIL.

- [ ] **Step 3: Write `app/nlp.py`**

```python
"""Tokenization, lemmas, POS (spaCy ca) + word frequency (wordfreq).

spaCy's ca_core_news_sm may be missing; degrade to a regex tokenizer with
lemma == lowercased form so the app still works.
"""
import re

_WORD = re.compile(r"[\w·]+(?:['’][\w·]+)*", re.UNICODE)

_NLP = None
_NLP_TRIED = False


def _spacy():
    global _NLP, _NLP_TRIED
    if not _NLP_TRIED:
        _NLP_TRIED = True
        try:
            import spacy
            _NLP = spacy.load("ca_core_news_sm",
                              disable=["parser", "ner"])
        except Exception:
            _NLP = None
    return _NLP


def freq_badge(zipf: float) -> str:
    if zipf >= 5.0:
        return "common"
    if zipf >= 3.3:
        return "medium"
    return "rare"


def zipf(word: str) -> float:
    try:
        from wordfreq import zipf_frequency
        return zipf_frequency(word, "ca")
    except Exception:
        return 0.0


def naive_tokenize(text: str) -> list[dict]:
    toks, i = [], 0
    for m in _WORD.finditer(text):
        if m.start() > i:
            gap = text[i:m.start()]
            if gap.strip():
                toks.append({"t": gap.strip(), "lemma": "", "pos": "",
                             "is_word": False, "zipf": 0.0})
        w = m.group(0)
        toks.append({"t": w, "lemma": w.lower(), "pos": "",
                     "is_word": True, "zipf": zipf(w)})
        i = m.end()
    tail = text[i:].strip()
    if tail:
        toks.append({"t": tail, "lemma": "", "pos": "", "is_word": False,
                     "zipf": 0.0})
    return toks


def tokenize(text: str) -> list[dict]:
    nlp_model = _spacy()
    if nlp_model is None:
        return naive_tokenize(text)
    toks = []
    for tok in nlp_model(text):
        if tok.is_space:
            continue
        is_word = not (tok.is_punct or tok.like_num and tok.is_punct)
        is_word = not tok.is_punct
        toks.append({"t": tok.text,
                     "lemma": tok.lemma_.lower() if is_word else "",
                     "pos": tok.pos_ if is_word else "",
                     "is_word": is_word,
                     "zipf": zipf(tok.text) if is_word else 0.0})
    return toks


def analyze_selection(text: str) -> tuple[str, str]:
    """Return (lemma, pos) for a selected word/expression."""
    words = [t for t in tokenize(text) if t["is_word"]]
    if not words:
        return text.lower(), ""
    if len(words) == 1:
        return words[0]["lemma"], words[0]["pos"]
    return " ".join(w["lemma"] for w in words), "EXPR"
```

- [ ] **Step 4: Run `./venv-run pytest tests/test_nlp.py -q`** — 2 passed. (Note: the double `is_word` assignment in `tokenize` — keep only `is_word = not tok.is_punct`.)
- [ ] **Step 5: Commit** `feat: nlp tokens/lemmas/freq`

---

### Task 7: Translation engine (TDD on detok, lazy model)

**Files:** Create `app/translate.py`, `tests/test_translate.py`

- [ ] **Step 1: Failing test `tests/test_translate.py`**

```python
from app.translate import detok


def test_detok_joins_sentencepiece_pieces():
    assert detok(["▁Los", "▁per", "ros"]) == "Los perros"
    assert detok([]) == ""
```

- [ ] **Step 2: Run it** — FAIL.

- [ ] **Step 3: Write `app/translate.py`**

```python
"""Softcatalà cat->spa neural translation via CTranslate2 + SentencePiece."""
from pathlib import Path

from . import config

_ENGINE = None
_TRIED = False


def detok(pieces: list[str]) -> str:
    return "".join(pieces).replace("▁", " ").strip()


class _Engine:
    def __init__(self, model_dir: Path):
        import ctranslate2
        import sentencepiece as spm
        sp_files = sorted(model_dir.glob("**/*.model"))
        if not sp_files:
            raise FileNotFoundError("no SentencePiece model in " + str(model_dir))
        self.sp = spm.SentencePieceProcessor(model_file=str(sp_files[0]))
        ct2_dir = model_dir
        if not (model_dir / "model.bin").exists():
            cands = list(model_dir.glob("**/model.bin"))
            if not cands:
                raise FileNotFoundError("no CT2 model.bin under " + str(model_dir))
            ct2_dir = cands[0].parent
        self.tr = ctranslate2.Translator(str(ct2_dir), device="cpu")

    def translate(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ""
        toks = self.sp.encode(text, out_type=str)
        res = self.tr.translate_batch([toks], beam_size=2, max_batch_size=1)
        return detok(res[0].hypotheses[0])


def model_dir() -> Path:
    return config.MODELS_DIR / "translate-cat-spa"


def is_downloaded() -> bool:
    return model_dir().exists() and any(model_dir().glob("**/model.bin"))


def download():
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=config.TRANSLATE_REPO,
                      local_dir=str(model_dir()))


def translate(text: str) -> str:
    """Translate ca->es. Returns '' on any failure (never raises to caller)."""
    global _ENGINE, _TRIED
    if _ENGINE is None and not _TRIED:
        _TRIED = True
        try:
            if not is_downloaded():
                download()
            _ENGINE = _Engine(model_dir())
        except Exception:
            _ENGINE = None
    if _ENGINE is None:
        return ""
    try:
        return _ENGINE.translate(text)
    except Exception:
        return ""
```

- [ ] **Step 4: Run `./venv-run pytest tests/test_translate.py -q`** — 1 passed.
- [ ] **Step 5: Commit** `feat: softcatala translation engine`

---

### Task 8: Media (ffmpeg) helpers (TDD on command building; real cut behind skipif)

**Files:** Create `app/media.py`, `tests/test_media.py`

- [ ] **Step 1: Failing test `tests/test_media.py`**

```python
import shutil
import subprocess
import pytest
from app import media


def test_audio_cmd_pads_and_reencodes():
    cmd = media.audio_cmd("/v.mp4", 10.0, 12.0, "/out.mp3", pad=0.25)
    s = " ".join(cmd)
    assert "-ss 9.75" in s and "-t 2.5" in s and "libmp3lame" in s


def test_frame_cmd_midpoint_scale():
    cmd = media.frame_cmd("/v.mp4", 11.0, "/out.jpg")
    s = " ".join(cmd)
    assert "-ss 11.0" in s and "scale=640:-2" in s and "-frames:v 1" in s


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="no ffmpeg")
def test_real_cut(tmp_path):
    src = tmp_path / "tone.wav"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=3", str(src)],
                   check=True, capture_output=True)
    out = tmp_path / "cut.mp3"
    media.cut_audio(str(src), 1.0, 2.0, str(out))
    assert out.exists() and out.stat().st_size > 1000
```

- [ ] **Step 2: Run it** — FAIL.

- [ ] **Step 3: Write `app/media.py`**

```python
"""ffmpeg helpers: card audio cut, video frame, browser-safe remux."""
import subprocess
from pathlib import Path

FFMPEG = "ffmpeg"
BROWSER_OK = {".mp4", ".m4v", ".mov", ".webm", ".mp3", ".m4a", ".wav", ".aac", ".ogg"}


def audio_cmd(src: str, start: float, end: float, out: str,
              pad: float = 0.25) -> list[str]:
    s = max(0.0, start - pad)
    dur = (end - start) + 2 * pad if start - pad >= 0 else (end - start) + pad + start
    dur = round(end + pad - s, 3)
    return [FFMPEG, "-y", "-ss", str(round(s, 3)), "-i", src,
            "-t", str(dur), "-vn", "-c:a", "libmp3lame", "-q:a", "4", out]


def frame_cmd(src: str, ts: float, out: str) -> list[str]:
    return [FFMPEG, "-y", "-ss", str(round(ts, 3)), "-i", src,
            "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "3", out]


def _run(cmd: list[str]):
    subprocess.run(cmd, check=True, capture_output=True)


def cut_audio(src, start, end, out, pad=0.25):
    _run(audio_cmd(src, start, end, out, pad))


def snapshot(src, ts, out):
    _run(frame_cmd(src, ts, out))


def duration(src: str) -> float:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", src],
        capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return 0.0


def ensure_browser_playable(src: Path, out_dir: Path) -> Path:
    """Remux (or transcode) into mp4 if the browser can't play `src`."""
    if src.suffix.lower() in BROWSER_OK:
        return src
    out = out_dir / (src.stem + ".mp4")
    if out.exists():
        return out
    try:
        _run([FFMPEG, "-y", "-i", str(src), "-c", "copy",
              "-movflags", "+faststart", str(out)])
    except subprocess.CalledProcessError:
        _run([FFMPEG, "-y", "-i", str(src), "-c:v", "libx264", "-preset",
              "veryfast", "-crf", "23", "-c:a", "aac",
              "-movflags", "+faststart", str(out)])
    return out
```

Note: in `audio_cmd`, delete the first `dur =` line — the second assignment is the correct one (`end + pad - s`). Keep the function four lines: compute `s`, compute `dur`, return list.

- [ ] **Step 4: Run `./venv-run pytest tests/test_media.py -q`** — 3 passed (or 2 passed + 1 skipped without ffmpeg).
- [ ] **Step 5: Commit** `feat: ffmpeg media helpers`

---

### Task 9: AnkiConnect client + queue (TDD with mocked HTTP)

**Files:** Create `app/anki.py`, `tests/test_anki.py`

- [ ] **Step 1: Failing test `tests/test_anki.py`**

```python
from unittest.mock import patch, MagicMock
from app import anki


def _resp(result=None, error=None):
    m = MagicMock()
    m.json.return_value = {"result": result, "error": error}
    return m


def test_note_payload():
    card = {"paraula": "gos", "paraula_es": "perro", "frase": "El gos",
            "frase_es": "El perro", "audio_file": "a.mp3",
            "image_file": "i.jpg", "font": "V @ 0:01", "freq_rank": "common"}
    note = anki.build_note(card, deck="Català")
    assert note["deckName"] == "Català"
    assert note["modelName"] == "CatalaMiner"
    assert note["fields"]["Audio"] == "[sound:a.mp3]"
    assert note["fields"]["Imatge"] == '<img src="i.jpg">'
    assert note["options"]["allowDuplicate"] is False


@patch("app.anki.requests.post")
def test_invoke_ok_and_error(post):
    post.return_value = _resp(result=["Default"])
    assert anki.invoke("deckNames") == ["Default"]
    post.return_value = _resp(error="boom")
    try:
        anki.invoke("deckNames")
        assert False
    except anki.AnkiError:
        pass


@patch("app.anki.requests.post")
def test_is_up_false_when_down(post):
    post.side_effect = ConnectionError()
    assert anki.is_up() is False
```

- [ ] **Step 2: Run it** — FAIL.

- [ ] **Step 3: Write `app/anki.py`**

```python
"""AnkiConnect client. Anki may be closed: callers keep cards 'pending'."""
import base64
from pathlib import Path

import requests

from . import config


class AnkiError(Exception):
    pass


def invoke(action: str, **params):
    r = requests.post(config.ANKI_URL,
                      json={"action": action, "version": 6, "params": params},
                      timeout=10)
    data = r.json()
    if data.get("error"):
        raise AnkiError(data["error"])
    return data.get("result")


def is_up() -> bool:
    try:
        invoke("version")
        return True
    except Exception:
        return False


CARD_CSS = """.card { font-family: -apple-system, sans-serif; font-size: 22px;
text-align: center; color: #222; background: #fdfdfd; }
.front { font-size: 34px; font-weight: 700; }
.frase { margin-top: 12px; } .es { color: #666; font-size: 18px; }
.font { color: #999; font-size: 13px; margin-top: 10px; }
img { max-width: 90%; border-radius: 8px; margin-top: 10px; }"""

FRONT = '<div class="front">{{Paraula}}</div>'
BACK = """{{FrontSide}}<hr id=answer>
<div class="es">{{ParaulaES}}</div>
<div class="frase">{{Frase}}</div>
<div class="es">{{FraseES}}</div>
{{Imatge}}<br>{{Audio}}
<div class="font">{{Font}} · {{Freq}}</div>"""


def ensure_note_type():
    if config.NOTE_TYPE in invoke("modelNames"):
        return
    invoke("createModel", modelName=config.NOTE_TYPE,
           inOrderFields=config.NOTE_FIELDS, css=CARD_CSS,
           cardTemplates=[{"Name": "Card 1", "Front": FRONT, "Back": BACK}])


def build_note(card: dict, deck: str) -> dict:
    return {
        "deckName": deck,
        "modelName": config.NOTE_TYPE,
        "fields": {
            "Paraula": card["paraula"] or "",
            "ParaulaES": card["paraula_es"] or "",
            "Frase": card["frase"] or "",
            "FraseES": card["frase_es"] or "",
            "Audio": f"[sound:{card['audio_file']}]" if card.get("audio_file") else "",
            "Imatge": f'<img src="{card["image_file"]}">' if card.get("image_file") else "",
            "Font": card.get("font") or "",
            "Freq": card.get("freq_rank") or "",
        },
        "options": {"allowDuplicate": False},
        "tags": ["catala-miner"],
    }


def send_card(card: dict, deck: str) -> int:
    """Upload media + note. Raises AnkiError/requests errors if Anki is down."""
    ensure_note_type()
    if deck not in invoke("deckNames"):
        invoke("createDeck", deck=deck)
    for key in ("audio_file", "image_file"):
        name = card.get(key)
        if name:
            path = config.MEDIA_DIR / name
            if path.exists():
                invoke("storeMediaFile", filename=name,
                       data=base64.b64encode(path.read_bytes()).decode())
    return invoke("addNote", note=build_note(card, deck))
```

- [ ] **Step 4: Run `./venv-run pytest tests/test_anki.py -q`** — 3 passed.
- [ ] **Step 5: Commit** `feat: ankiconnect client`

---

### Task 10: Transcription + jobs

**Files:** Create `app/jobs.py`, `app/transcribe.py` (no unit test — exercised by smoke test in Task 14; model download is GBs)

- [ ] **Step 1: Write `app/jobs.py`**

```python
"""In-memory background job registry, polled by the frontend."""
import threading
import traceback
import uuid

JOBS: dict[str, dict] = {}


def start(target, *args, label="") -> str:
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = {"status": "running", "progress": 0.0, "label": label,
                 "message": "", "result": None}

    def _run():
        try:
            JOBS[jid]["result"] = target(jid, *args)
            JOBS[jid]["status"] = "done"
            JOBS[jid]["progress"] = 1.0
        except Exception as e:  # surfaced to UI
            traceback.print_exc()
            JOBS[jid]["status"] = "error"
            JOBS[jid]["message"] = str(e)

    threading.Thread(target=_run, daemon=True).start()
    return jid


def set_progress(jid: str, p: float, message: str = ""):
    if jid in JOBS:
        JOBS[jid]["progress"] = round(p, 3)
        if message:
            JOBS[jid]["message"] = message


def get(jid: str) -> dict | None:
    return JOBS.get(jid)
```

- [ ] **Step 2: Write `app/transcribe.py`**

```python
"""faster-whisper transcription with word timestamps + spaCy tokens."""
from . import config, jobs, nlp

_MODELS: dict[str, object] = {}


def _model(key: str):
    from faster_whisper import WhisperModel
    if key not in _MODELS:
        _MODELS[key] = WhisperModel(config.WHISPER_MODELS[key],
                                    device="cpu", compute_type="int8")
    return _MODELS[key]


def transcribe(jid: str, media_path: str, model_key: str,
               duration: float) -> list[dict]:
    """Return segments: {start,end,text,logprob,words:[{w,start,end}],tokens:[...]}"""
    jobs.set_progress(jid, 0.01, "Carregant model…")
    model = _model(model_key)
    segments, _info = model.transcribe(
        media_path, language="ca", beam_size=5,
        word_timestamps=True, vad_filter=True)
    out = []
    for seg in segments:
        words = [{"w": w.word.strip(), "start": w.start, "end": w.end}
                 for w in (seg.words or [])]
        out.append({"start": seg.start, "end": seg.end,
                    "text": seg.text.strip(),
                    "logprob": seg.avg_logprob,
                    "words": words,
                    "tokens": nlp.tokenize(seg.text.strip())})
        if duration:
            jobs.set_progress(jid, min(0.99, seg.end / duration),
                              "Transcrivint…")
    return out


def tokens_for_existing(segs: list[dict]) -> list[dict]:
    """Add tokens to segments parsed from an .srt (no word timestamps)."""
    for s in segs:
        s["words"] = []
        s["logprob"] = 0.0
        s["tokens"] = nlp.tokenize(s["text"])
    return segs
```

- [ ] **Step 3: Verify imports compile: `./venv-run pytest -q` (all existing tests still pass) and `.venv/bin/python -c "import app.transcribe, app.jobs"`. Commit** `feat: transcription + job registry`

---

### Task 11: YouTube import

**Files:** Create `app/youtube.py`

- [ ] **Step 1: Write `app/youtube.py`**

```python
"""yt-dlp download: video (<=720p mp4) + Catalan subtitles if available."""
from pathlib import Path

from . import config, jobs


def download(jid: str, url: str) -> dict:
    import yt_dlp

    def hook(d):
        if d.get("status") == "downloading" and d.get("total_bytes"):
            jobs.set_progress(jid, 0.9 * d["downloaded_bytes"] / d["total_bytes"],
                              "Descarregant…")

    opts = {
        "format": "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "outtmpl": str(config.DL_DIR / "%(title).80s-%(id)s.%(ext)s"),
        "writesubtitles": True,
        "subtitleslangs": ["ca"],
        "subtitlesformat": "vtt",
        "noplaylist": True,
        "progress_hooks": [hook],
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        media = Path(ydl.prepare_filename(info))
    sub = media.with_suffix("").with_suffix("")  # strip .ext
    vtt = Path(str(media.with_suffix("")) + ".ca.vtt")
    return {"media_path": str(media),
            "title": info.get("title") or media.stem,
            "subtitles": str(vtt) if vtt.exists() else None,
            "duration": float(info.get("duration") or 0)}
```

Note: remove the unused `sub =` line.

- [ ] **Step 2: Verify import compiles; commit** `feat: youtube import`

---

### Task 12: FastAPI app + card pipeline

**Files:** Create `app/main.py`, `tests/test_api.py`

- [ ] **Step 1: Failing test `tests/test_api.py`** (uses FastAPI TestClient; heavy deps mocked)

```python
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
```

- [ ] **Step 2: Run it** — FAIL.

- [ ] **Step 3: Write `app/main.py`**

```python
"""CatalàMiner — FastAPI backend + static frontend."""
import json
import shutil
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import anki, config, db, dictionary, jobs, media, nlp, subs, translate

app = FastAPI(title="CatalaMiner")
CON = db.connect(config.DB_PATH)
STATIC = Path(__file__).resolve().parent.parent / "static"
_DICT = None
SETTINGS_PATH = config.APP_DIR / "settings.json"


def _dict():
    global _DICT
    if _DICT is None:
        try:
            _DICT = dictionary.load()
        except Exception:
            _DICT = dictionary.Dictionary({})
    return _DICT


def _settings() -> dict:
    if SETTINGS_PATH.exists():
        return json.loads(SETTINGS_PATH.read_text())
    return {"deck": "Català::Mining"}


def _save_settings(s: dict):
    SETTINGS_PATH.write_text(json.dumps(s))


def _fmt_ts(secs: float) -> str:
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ---------- health / sessions ----------

@app.get("/api/health")
def health():
    return {"ok": True, "anki": anki.is_up(),
            "translator": translate.is_downloaded()}


@app.get("/api/sessions")
def sessions():
    return db.list_sessions(CON)


@app.get("/api/sessions/{sid}")
def session_detail(sid: str):
    s = db.get_session(CON, sid)
    if not s:
        return JSONResponse({"error": "not found"}, status_code=404)
    s["transcript"] = json.loads(s.pop("transcript_json"))
    s["known_lemmas"] = sorted(db.known_lemmas(CON))
    s["media_url"] = "/media-file/" + sid
    return s


@app.get("/media-file/{sid}")
def media_file(sid: str):
    s = db.get_session(CON, sid)
    if not s:
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(s["media_path"])


@app.post("/api/sessions/upload")
async def upload(file: UploadFile = File(...)):
    dest = config.DL_DIR / (uuid.uuid4().hex[:6] + "-" + file.filename)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    playable = media.ensure_browser_playable(dest, config.DL_DIR)
    sid = db.create_session(
        CON, title=file.filename, source_type="local",
        media_path=str(playable), srt_source="none", model_size="-",
        duration_secs=media.duration(str(playable)), transcript_json="[]")
    sidecar = _find_sidecar_subs(dest)
    return {"session_id": sid, "has_sidecar_subs": bool(sidecar)}


def _find_sidecar_subs(path: Path) -> Path | None:
    for ext in (".srt", ".vtt", ".ca.srt", ".ca.vtt"):
        p = path.with_suffix(ext)
        if p.exists():
            return p
    return None


class YoutubeReq(BaseModel):
    url: str


@app.post("/api/sessions/youtube")
def youtube_import(req: YoutubeReq):
    from . import youtube

    def work(jid):
        info = youtube.download(jid, req.url)
        playable = media.ensure_browser_playable(
            Path(info["media_path"]), config.DL_DIR)
        sid = db.create_session(
            CON, title=info["title"], source_type="youtube",
            media_path=str(playable), srt_source="none", model_size="-",
            duration_secs=info["duration"], transcript_json="[]")
        if info["subtitles"]:
            segs = subs.parse_subtitles(Path(info["subtitles"]).read_text())
            from .transcribe import tokens_for_existing
            db.update_transcript(CON, sid,
                                 json.dumps(tokens_for_existing(segs)),
                                 "-", "youtube_subs")
        return {"session_id": sid}

    return {"job_id": jobs.start(work, label="youtube")}


class TranscribeReq(BaseModel):
    model: str = config.DEFAULT_WHISPER
    use_sidecar: bool = False


@app.post("/api/sessions/{sid}/transcribe")
def do_transcribe(sid: str, req: TranscribeReq):
    s = db.get_session(CON, sid)
    if not s:
        return JSONResponse({"error": "not found"}, status_code=404)

    def work(jid):
        from . import transcribe as T
        sidecar = _find_sidecar_subs(Path(s["media_path"]))
        if req.use_sidecar and sidecar:
            segs = T.tokens_for_existing(
                subs.parse_subtitles(sidecar.read_text(errors="replace")))
            db.update_transcript(CON, sid, json.dumps(segs), "-", "srt")
        else:
            segs = T.transcribe(jid, s["media_path"], req.model,
                                s["duration_secs"] or 0)
            db.update_transcript(CON, sid, json.dumps(segs), req.model,
                                 "whisper")
        return {"segments": len(segs)}

    return {"job_id": jobs.start(work, label="transcribe")}


@app.get("/api/jobs/{jid}")
def job_status(jid: str):
    j = jobs.get(jid)
    return j or JSONResponse({"error": "not found"}, status_code=404)


# ---------- cards ----------

class PreviewReq(BaseModel):
    session_id: str
    segment_index: int
    selection: str
    pad_before: int = 0   # extend audio N segments back
    pad_after: int = 0


@app.post("/api/cards/preview")
def card_preview(req: PreviewReq):
    s = db.get_session(CON, req.session_id)
    if not s:
        return JSONResponse({"error": "not found"}, status_code=404)
    segs = json.loads(s["transcript_json"])
    seg = segs[req.segment_index]
    start = segs[max(0, req.segment_index - req.pad_before)]["start"]
    end = segs[min(len(segs) - 1, req.segment_index + req.pad_after)]["end"]

    base = uuid.uuid4().hex[:10]
    audio_name, image_name = f"cm-{base}.mp3", f"cm-{base}.jpg"
    audio_ok = image_ok = True
    try:
        media.cut_audio(s["media_path"], start, end,
                        str(config.MEDIA_DIR / audio_name))
    except Exception:
        audio_ok = False
    try:
        media.snapshot(s["media_path"], (seg["start"] + seg["end"]) / 2,
                       str(config.MEDIA_DIR / image_name))
    except Exception:
        image_ok = False

    lemma, pos = nlp.analyze_selection(req.selection)
    z = nlp.zipf(req.selection)
    senses = _dict().lookup(req.selection) or _dict().lookup(lemma)
    return {
        "paraula": req.selection,
        "lema": lemma, "pos": pos,
        "paraula_es": translate.translate(req.selection),
        "senses": [{"es": es, "pos": p} for es, p in senses[:8]],
        "frase": seg["text"],
        "frase_es": translate.translate(seg["text"]),
        "freq_zipf": z, "freq_rank": nlp.freq_badge(z),
        "audio_file": audio_name if audio_ok else "",
        "image_file": image_name if image_ok else "",
        "font": f"{s['title']} @ {_fmt_ts(seg['start'])}",
    }


class CardReq(BaseModel):
    session_id: str
    segment_index: int
    paraula: str
    lema: str
    pos: str = ""
    paraula_es: str = ""
    frase: str
    frase_es: str = ""
    freq_rank: str = ""
    audio_file: str = ""
    image_file: str = ""
    font: str = ""


@app.post("/api/cards")
def create_card(req: CardReq):
    cid = db.create_card(CON, session_id=req.session_id,
                         segment_index=req.segment_index, paraula=req.paraula,
                         lema=req.lema, pos=req.pos, paraula_es=req.paraula_es,
                         frase=req.frase, frase_es=req.frase_es,
                         freq_rank=req.freq_rank, audio_file=req.audio_file,
                         image_file=req.image_file, font=req.font)
    sent = _flush()
    return {"card_id": cid, "sent_now": sent,
            "pending": len(db.pending_cards(CON))}


def _flush() -> int:
    if not anki.is_up():
        return 0
    deck = _settings()["deck"]
    n = 0
    for card in db.pending_cards(CON):
        try:
            note_id = anki.send_card(card, deck)
            db.mark_card_sent(CON, card["id"], note_id)
            n += 1
        except Exception:
            break
    return n


@app.post("/api/anki/flush")
def anki_flush():
    return {"sent": _flush(), "pending": len(db.pending_cards(CON))}


@app.get("/api/anki/status")
def anki_status():
    up = anki.is_up()
    decks = anki.invoke("deckNames") if up else []
    return {"up": up, "decks": decks, "deck": _settings()["deck"],
            "pending": len(db.pending_cards(CON))}


class DeckReq(BaseModel):
    deck: str


@app.post("/api/anki/deck")
def set_deck(req: DeckReq):
    s = _settings()
    s["deck"] = req.deck
    _save_settings(s)
    return {"ok": True}


# media (card audio previews) + frontend
app.mount("/media", StaticFiles(directory=str(config.MEDIA_DIR)), name="media")
app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
```

- [ ] **Step 4: Create placeholder `static/index.html`** containing `<h1>CatalaMiner</h1>` so the static mount works.
- [ ] **Step 5: Run `./venv-run pytest -q`** — all pass.
- [ ] **Step 6: Commit** `feat: fastapi backend + card pipeline`

---

### Task 13: Frontend (single page)

**Files:** Create `static/index.html`, `static/style.css`, `static/app.js` (replace placeholder). No unit tests — verified in Task 14 smoke + manual pass.

- [ ] **Step 1: `static/index.html`**

```html
<!doctype html>
<html lang="ca">
<head>
<meta charset="utf-8">
<title>CatalàMiner</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/style.css">
</head>
<body>
<header>
  <h1 id="brand">🐈 CatalàMiner</h1>
  <div id="anki-badge" class="badge">Anki…</div>
</header>

<main id="home">
  <section class="new-session">
    <label class="filebtn">📁 Obrir arxiu local
      <input type="file" id="file-input" accept="video/*,audio/*,.mkv">
    </label>
    <div class="yt">
      <input type="url" id="yt-url" placeholder="Enganxa URL de YouTube…">
      <button id="yt-btn">⬇️ Importar</button>
    </div>
  </section>
  <section>
    <h2>Sessions</h2>
    <ul id="session-list"></ul>
  </section>
</main>

<main id="player" hidden>
  <button id="back">← Sessions</button>
  <video id="video" controls playsinline></video>
  <div id="transcribe-bar">
    <select id="model-select">
      <option value="catala-large">Whisper large-v3 català (AINA) — màxima qualitat</option>
      <option value="large-v3">Whisper large-v3 genèric</option>
      <option value="small">Whisper small — ràpid</option>
    </select>
    <button id="transcribe-btn">🎙️ Transcriure</button>
    <button id="sidecar-btn" hidden>📜 Usar .srt existent</button>
    <progress id="job-progress" max="1" value="0" hidden></progress>
    <span id="job-msg"></span>
  </div>
  <div id="subs"></div>
</main>

<aside id="card-panel" hidden>
  <h3>Nova targeta</h3>
  <div class="row"><label>Paraula</label><input id="c-paraula"></div>
  <div class="row"><label>Paraula ES</label><input id="c-paraula-es"></div>
  <div id="senses"></div>
  <div class="row"><label>Frase</label><textarea id="c-frase" rows="2"></textarea></div>
  <div class="row"><label>Frase ES</label><textarea id="c-frase-es" rows="2"></textarea></div>
  <div class="row meta"><span id="c-meta"></span></div>
  <div class="row">
    <audio id="c-audio" controls></audio>
    <button id="pad-before" title="Incloure segment anterior">⏪+</button>
    <button id="pad-after" title="Incloure segment següent">+⏩</button>
  </div>
  <img id="c-image" alt="">
  <div class="row actions">
    <button id="c-cancel">Cancel·lar</button>
    <button id="c-send" class="primary">➕ Afegir a Anki (⏎)</button>
  </div>
</aside>

<div id="toast" hidden></div>
<script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: `static/style.css`**

```css
:root { --bg:#14161a; --panel:#1e2127; --fg:#e8e6e3; --dim:#9a9a9a;
  --acc:#ffcc4d; --known:#f5d76e33; --ok:#57c07d; --err:#e06c75; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:16px/1.5 -apple-system, "Segoe UI", sans-serif; }
header { display:flex; justify-content:space-between; align-items:center;
  padding:10px 18px; background:var(--panel); }
h1 { font-size:20px; margin:0; }
.badge { font-size:13px; padding:4px 10px; border-radius:12px;
  background:#333; color:var(--dim); }
.badge.up { background:#1f3d2b; color:var(--ok); }
.badge.pending { background:#4d3800; color:var(--acc); }
main { max-width:900px; margin:0 auto; padding:18px; }
.new-session { display:flex; gap:14px; flex-wrap:wrap; margin-bottom:8px; }
.filebtn { background:var(--panel); padding:10px 16px; border-radius:8px;
  cursor:pointer; }
.filebtn input { display:none; }
.yt { display:flex; gap:6px; flex:1; min-width:280px; }
.yt input { flex:1; background:var(--panel); color:var(--fg);
  border:1px solid #333; border-radius:8px; padding:10px; }
button { background:#2a2e36; color:var(--fg); border:0; border-radius:8px;
  padding:9px 14px; cursor:pointer; font-size:15px; }
button:hover { background:#353a44; }
button.primary { background:var(--acc); color:#222; font-weight:700; }
#session-list { list-style:none; padding:0; }
#session-list li { background:var(--panel); margin:6px 0; padding:12px 14px;
  border-radius:8px; cursor:pointer; display:flex;
  justify-content:space-between; }
#session-list .dim { color:var(--dim); font-size:13px; }
video { width:100%; max-height:46vh; background:#000; border-radius:8px; }
#transcribe-bar { display:flex; gap:8px; align-items:center; margin:10px 0;
  flex-wrap:wrap; }
#transcribe-bar select { background:var(--panel); color:var(--fg);
  border:1px solid #333; border-radius:8px; padding:8px; }
#subs { padding-bottom:40vh; }
.seg { padding:8px 12px; border-radius:8px; margin:2px 0; cursor:default;
  color:var(--dim); }
.seg.active { background:var(--panel); color:var(--fg); }
.seg.lowconf { opacity:.55; font-style:italic; }
.seg .t { cursor:pointer; border-radius:4px; padding:1px 2px; }
.seg .t:hover { background:#3a3f4a; }
.seg .t.known { background:var(--known); }
.seg .t.freq-rare { border-bottom:2px dotted var(--err); }
.seg .t.freq-medium { border-bottom:2px dotted var(--acc); }
.seg .time { font-size:12px; color:#666; margin-right:8px; cursor:pointer; }
#card-panel { position:fixed; top:0; right:0; width:340px; height:100vh;
  overflow-y:auto; background:var(--panel); padding:16px;
  box-shadow:-4px 0 18px #0008; }
#card-panel .row { margin:8px 0; }
#card-panel label { display:block; font-size:12px; color:var(--dim); }
#card-panel input, #card-panel textarea { width:100%; background:#14161a;
  color:var(--fg); border:1px solid #333; border-radius:6px; padding:7px;
  font-size:15px; }
#senses { display:flex; flex-wrap:wrap; gap:6px; }
#senses .sense { background:#2a2e36; border-radius:12px; padding:3px 10px;
  font-size:13px; cursor:pointer; }
#senses .sense:hover { background:var(--acc); color:#222; }
#c-image { width:100%; border-radius:8px; margin-top:8px; }
.meta { color:var(--dim); font-size:13px; }
.actions { display:flex; gap:8px; justify-content:flex-end; }
#toast { position:fixed; bottom:20px; left:50%; transform:translateX(-50%);
  background:var(--panel); border:1px solid #444; padding:10px 18px;
  border-radius:10px; z-index:10; }
#toast.ok { border-color:var(--ok); } #toast.err { border-color:var(--err); }
```

- [ ] **Step 3: `static/app.js`** — complete logic:

```javascript
const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" }, ...opts,
  });
  return r.json();
};
const toast = (msg, cls = "ok") => {
  const t = $("toast");
  t.textContent = msg; t.className = cls; t.hidden = false;
  setTimeout(() => (t.hidden = true), 2600);
};

let SESSION = null, SEGS = [], KNOWN = new Set(), CARD = null, PAD = { b: 0, a: 0 };

// ---------- Anki badge ----------
async function refreshAnki() {
  const s = await api("/api/anki/status");
  const b = $("anki-badge");
  if (s.pending > 0) { b.textContent = `Anki: ${s.pending} en cua`; b.className = "badge pending"; }
  else if (s.up) { b.textContent = "Anki ✓"; b.className = "badge up"; }
  else { b.textContent = "Anki tancat"; b.className = "badge"; }
}
setInterval(async () => { await api("/api/anki/flush", { method: "POST" }).catch(() => {}); refreshAnki(); }, 15000);

// ---------- home ----------
async function loadSessions() {
  const list = await api("/api/sessions");
  $("session-list").innerHTML = list.map((s) =>
    `<li data-id="${s.id}"><span>${s.title}</span>
     <span class="dim">${s.srt_source} · ${s.created_at.slice(0, 10)}</span></li>`).join("");
  for (const li of $("session-list").children)
    li.onclick = () => openSession(li.dataset.id);
}

$("file-input").onchange = async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("file", f);
  toast("Pujant arxiu…");
  const r = await fetch("/api/sessions/upload", { method: "POST", body: fd }).then((x) => x.json());
  await openSession(r.session_id);
  if (r.has_sidecar_subs) $("sidecar-btn").hidden = false;
};

$("yt-btn").onclick = async () => {
  const url = $("yt-url").value.trim();
  if (!url) return;
  const { job_id } = await api("/api/sessions/youtube", { method: "POST", body: JSON.stringify({ url }) });
  const res = await pollJob(job_id, "Descarregant de YouTube…");
  if (res) openSession(res.session_id);
};

// ---------- jobs ----------
async function pollJob(jid, label) {
  $("job-progress").hidden = false;
  $("job-msg").textContent = label;
  while (true) {
    const j = await api("/api/jobs/" + jid);
    $("job-progress").value = j.progress || 0;
    $("job-msg").textContent = j.message || label;
    if (j.status === "done") { $("job-progress").hidden = true; $("job-msg").textContent = ""; return j.result; }
    if (j.status === "error") { $("job-progress").hidden = true; toast("Error: " + j.message, "err"); return null; }
    await new Promise((r) => setTimeout(r, 800));
  }
}

// ---------- player ----------
async function openSession(sid) {
  const s = await api("/api/sessions/" + sid);
  SESSION = s; SEGS = s.transcript; KNOWN = new Set(s.known_lemmas);
  $("home").hidden = true; $("player").hidden = false;
  $("video").src = s.media_url;
  renderSegs();
}
$("back").onclick = () => { $("player").hidden = true; $("home").hidden = false; $("card-panel").hidden = true; loadSessions(); };

$("transcribe-btn").onclick = async () => {
  const model = $("model-select").value;
  const { job_id } = await api(`/api/sessions/${SESSION.id}/transcribe`,
    { method: "POST", body: JSON.stringify({ model }) });
  const res = await pollJob(job_id, "Transcrivint… (la primera vegada descarrega el model)");
  if (res) openSession(SESSION.id);
};
$("sidecar-btn").onclick = async () => {
  const { job_id } = await api(`/api/sessions/${SESSION.id}/transcribe`,
    { method: "POST", body: JSON.stringify({ use_sidecar: true }) });
  const res = await pollJob(job_id, "Carregant subtítols…");
  if (res) openSession(SESSION.id);
};

function fmtTime(t) {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function renderSegs() {
  const el = $("subs");
  if (!SEGS.length) { el.innerHTML = '<p class="dim">Sense transcripció encara — prem 🎙️ Transcriure.</p>'; return; }
  el.innerHTML = SEGS.map((seg, i) => {
    const toks = (seg.tokens && seg.tokens.length)
      ? seg.tokens.map((t) => t.is_word
          ? `<span class="t ${KNOWN.has(t.lemma) ? "known" : ""} freq-${badge(t.zipf)}" data-l="${t.lemma}">${t.t}</span>`
          : `<span>${t.t}</span>`).join(" ")
      : seg.text;
    const low = seg.logprob < -1.0 ? " lowconf" : "";
    return `<div class="seg${low}" id="seg-${i}" data-i="${i}">
      <span class="time">${fmtTime(seg.start)}</span>${toks}</div>`;
  }).join("");
  for (const div of el.querySelectorAll(".seg")) {
    const i = +div.dataset.i;
    div.querySelector(".time").onclick = () => { $("video").currentTime = SEGS[i].start; $("video").play(); };
    for (const tok of div.querySelectorAll(".t"))
      tok.onclick = () => mine(i, window.getSelection().toString().trim() || tok.textContent);
  }
}
const badge = (z) => (z >= 5 ? "common" : z >= 3.3 ? "medium" : "rare");

$("video").addEventListener("timeupdate", () => {
  const t = $("video").currentTime;
  const i = SEGS.findIndex((s) => t >= s.start && t <= s.end);
  document.querySelectorAll(".seg.active").forEach((d) => d.classList.remove("active"));
  if (i >= 0) {
    const div = $("seg-" + i);
    div.classList.add("active");
    div.scrollIntoView({ block: "center", behavior: "smooth" });
  }
});

document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") {
    if (e.key === "Enter" && !e.shiftKey && !$("card-panel").hidden) { e.preventDefault(); sendCard(); }
    return;
  }
  if ($("player").hidden) return;
  const v = $("video");
  const cur = SEGS.findIndex((s) => v.currentTime >= s.start && v.currentTime <= s.end);
  if (e.key === " ") { e.preventDefault(); v.paused ? v.play() : v.pause(); }
  if (e.key === "ArrowLeft") { e.preventDefault(); v.currentTime = SEGS[Math.max(0, cur - 1)]?.start ?? 0; }
  if (e.key === "ArrowRight") { e.preventDefault(); v.currentTime = SEGS[Math.min(SEGS.length - 1, cur + 1)]?.start ?? v.currentTime; }
  if (e.key === "a" && cur >= 0) { v.currentTime = SEGS[cur].start; v.play(); }
  if (e.key === "Enter" && !$("card-panel").hidden) sendCard();
  if (e.key === "Escape") $("card-panel").hidden = true;
});

// ---------- mining ----------
async function mine(segIndex, selection, padB = 0, padA = 0) {
  $("video").pause();
  PAD = { b: padB, a: padA };
  toast("Creant targeta…");
  const p = await api("/api/cards/preview", {
    method: "POST",
    body: JSON.stringify({ session_id: SESSION.id, segment_index: segIndex,
      selection, pad_before: padB, pad_after: padA }),
  });
  CARD = { ...p, session_id: SESSION.id, segment_index: segIndex };
  $("c-paraula").value = p.paraula;
  $("c-paraula-es").value = p.paraula_es;
  $("c-frase").value = p.frase;
  $("c-frase-es").value = p.frase_es;
  $("c-meta").textContent = `${p.lema} · ${p.pos} · ${p.freq_rank} (zipf ${p.freq_zipf.toFixed(1)}) · ${p.font}`;
  $("senses").innerHTML = p.senses.map((s) =>
    `<span class="sense" data-es="${s.es}">${s.es} <small>${s.pos}</small></span>`).join("");
  for (const sp of $("senses").children)
    sp.onclick = () => { $("c-paraula-es").value = sp.dataset.es; };
  $("c-audio").src = p.audio_file ? "/media/" + p.audio_file : "";
  $("c-image").src = p.image_file ? "/media/" + p.image_file : "";
  $("card-panel").hidden = false;
  if (p.audio_file) $("c-audio").play().catch(() => {});
}

$("pad-before").onclick = () => CARD && mine(CARD.segment_index, $("c-paraula").value, PAD.b + 1, PAD.a);
$("pad-after").onclick = () => CARD && mine(CARD.segment_index, $("c-paraula").value, PAD.b, PAD.a + 1);
$("c-cancel").onclick = () => { $("card-panel").hidden = true; };

async function sendCard() {
  if (!CARD) return;
  const body = {
    session_id: CARD.session_id, segment_index: CARD.segment_index,
    paraula: $("c-paraula").value, lema: CARD.lema, pos: CARD.pos,
    paraula_es: $("c-paraula-es").value,
    frase: $("c-frase").value, frase_es: $("c-frase-es").value,
    freq_rank: CARD.freq_rank, audio_file: CARD.audio_file,
    image_file: CARD.image_file, font: CARD.font,
  };
  const r = await api("/api/cards", { method: "POST", body: JSON.stringify(body) });
  $("card-panel").hidden = true;
  KNOWN.add(CARD.lema);
  renderSegs();
  refreshAnki();
  toast(r.sent_now ? "✅ Targeta afegida a Anki" : "🕓 Targeta en cua (obre Anki)", r.sent_now ? "ok" : "err");
}
$("c-send").onclick = sendCard;

// ---------- init ----------
loadSessions();
refreshAnki();
```

- [ ] **Step 4: Serve and eyeball.** Run `.venv/bin/python -m uvicorn app.main:app --port 8977` then open `http://localhost:8977` — home screen renders, no console errors.
- [ ] **Step 5: Commit** `feat: frontend`

---

### Task 14: install.sh, run.sh, README, smoke test

**Files:** Create `install.sh`, `run.sh`, `README.md`, `tests/test_smoke.py`

- [ ] **Step 1: `install.sh`**

```bash
#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
echo "== CatalàMiner install =="
command -v brew >/dev/null || { echo "Necessites Homebrew: https://brew.sh"; exit 1; }
brew list uv >/dev/null 2>&1 || brew install uv
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
[ -d .venv ] || uv venv --python 3.12 .venv
uv pip install -p .venv/bin/python -e . --group dev
echo "-- spaCy català --"
.venv/bin/python -m spacy download ca_core_news_sm || echo "AVÍS: spaCy ca no instal·lat (fallback regex)"
echo "-- Traductor Softcatalà + diccionari (descàrrega única) --"
.venv/bin/python - <<'PY'
from app import translate, dictionary
translate.download() if not translate.is_downloaded() else None
print("traductor:", "ok" if translate.is_downloaded() else "ERROR")
dictionary.load()
print("diccionari: ok")
PY
echo
echo "Fet! Arrenca amb ./run.sh"
echo "Recorda: instal·la Anki (apps.ankiweb.net) + add-on AnkiConnect (2055492159)."
echo "El model Whisper (≈3 GB) es descarrega al primer ús."
```

- [ ] **Step 2: `run.sh`**

```bash
#!/bin/bash
cd "$(dirname "$0")"
( sleep 1.2 && open "http://localhost:8977" ) &
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8977
```

`chmod +x install.sh run.sh`

- [ ] **Step 3: `tests/test_smoke.py`** — end-to-end through the API with a generated tone as "video" and mocked translate/whisper:

```python
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
```

- [ ] **Step 4: Write `README.md`** — short: what it is, install (`./install.sh`), run (`./run.sh`), Anki requirement (app + AnkiConnect add-on code 2055492159), model notes (first transcription downloads ~3 GB; model picker), troubleshooting (Anki closed → queue; mkv → auto-remux).
- [ ] **Step 5: Run full suite `./venv-run pytest -q`** — all pass. **Commit** `feat: install/run scripts, README, smoke test`

---

### Task 15: Real-world verification (manual, with the user)

- [ ] **Step 1:** Run `./install.sh` end-to-end; fix anything that breaks (wheel availability on 3.12, spaCy model URL, Softcatalà repo layout — check actual file names with `ls` after download and adjust `translate._Engine` glob if needed).
- [ ] **Step 2:** Start `./run.sh`, import a short Catalan YouTube video (e.g. a 3Cat clip), transcribe with `small` first (fast sanity), then `catala-large`.
- [ ] **Step 3:** Mine one card, verify: audio plays, image shows, translations sensible, senses popup works.
- [ ] **Step 4:** If Anki installed: verify note arrives with media; else verify queue badge shows pending count.
- [ ] **Step 5:** Commit any fixes; tag `v0.1.0`.

---

## Self-Review Notes

- **Spec coverage:** upload/YouTube (T11–12), sidecar srt (T4, T12), Catalan Whisper + word timestamps (T10), tokenized clickable subs with known/freq marking (T6, T13), preview with audio/frame/translations/senses (T12), editable card + AnkiConnect + queue (T9, T12–13), settings/deck (T12), remux (T8), low-confidence styling (T13), install/run/README incl. Anki-not-installed note (T14). Fallback LLM hook = out of scope (spec §8) — none needed.
- **Known deliberate simplifications (all spec-compliant):** selection of multi-word expressions uses browser text selection; card media generated at preview time (orphans are harmless, cleaned in a future version); `_flush` stops at first failure to avoid hammering a closed Anki.
- **Type consistency check:** `db.create_card` kwargs == `CardReq` fields == `anki.build_note` reads == smoke test payload. `tokens` schema `{t,lemma,pos,is_word,zipf}` used identically in T6/T10/T13.

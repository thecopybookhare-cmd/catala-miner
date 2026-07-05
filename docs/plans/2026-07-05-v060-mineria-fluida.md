# CatalàMiner v0.6.0 — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Minado sin fricción (hover + tarjetas en segundo plano), lematización/diccionario robustos (caso «Ets»), fix del salto A/D, popup estilo Migaku, panel de métricas y app de escritorio macOS.

**Architecture:** FastAPI + SQLite + JS vanilla (sin build). Se añade un diccionario de formas (Softcatalà/LT) indexado en SQLite propio (`forms.sqlite`), un endpoint de minado one-shot, un endpoint de stats que agrega SQLite local + AnkiConnect, y una ventana pywebview que envuelve el servidor existente.

**Tech Stack:** Python 3.12, FastAPI, spaCy `ca_core_news_sm`, diccionari LT de Softcatalà, bidix Apertium, CTranslate2 (Softcatalà cat→spa), espeak-ng (opcional), pywebview, AnkiConnect.

**Spec:** `docs/specs/2026-07-05-v060-mineria-fluida-design.md`

**Convenciones del repo:** tests pytest en `tests/` con `TestClient` y `unittest.mock.patch` (ver `tests/test_api.py`); no hay infraestructura de tests JS — el frontend se verifica manualmente con el servidor local (curl + navegador). Comandos de test: `.venv/bin/python -m pytest tests/ -q`.

---

### Task 0: Rama de trabajo

- [ ] **Step 0.1:** `git checkout -b feature/v060-mineria-fluida`

### Task 1: Fix navegación A/D (salto al inicio)

**Files:** Modify: `static/app.js` (funciones `gotoSeg`, handlers de botones y teclado)

- [ ] **Step 1.1: Sustituir la navegación por índice ciego por navegación temporal.**

Reemplazar `gotoSeg` y añadir helpers (sección `// ---------- video ----------`):

```js
function gotoSeg(i) {
  if (!SEGS.length) return;
  const j = Math.min(SEGS.length - 1, Math.max(0, i));
  V.currentTime = SEGS[j].start + 0.01;
  V.play();
}
// En huecos entre subtítulos CUR = -1: navegar por tiempo, nunca al segmento 0.
function nextSeg() {
  if (!SEGS.length) return;
  if (CUR >= 0) { gotoSeg(CUR + 1); return; }
  const t = V.currentTime;
  for (let i = 0; i < SEGS.length; i++)
    if (SEGS[i].start > t + 0.05) { gotoSeg(i); return; }
}
function prevSeg() {
  if (!SEGS.length) return;
  if (CUR >= 0) { gotoSeg(CUR - 1); return; }
  const t = V.currentTime;
  for (let i = SEGS.length - 1; i >= 0; i--)
    if (SEGS[i].end < t) { gotoSeg(i); return; }
  gotoSeg(0);
}
```

Actualizar los call sites:
- `$("prev-btn").onclick = () => prevSeg();`
- `$("next-btn").onclick = () => nextSeg();`
- teclado: `else if (k === "a" || e.key === "ArrowLeft") { e.preventDefault(); prevSeg(); }`
- teclado: `else if (k === "d" || e.key === "ArrowRight") { e.preventDefault(); nextSeg(); }`

- [ ] **Step 1.2: Verificar.** Con el servidor corriendo, abrir una sesión, pausar en un hueco entre dos subtítulos (o buscar con la barra un punto sin subtítulo) y pulsar `D`: debe ir al siguiente segmento, no al inicio. `A`: al anterior.

- [ ] **Step 1.3: Commit.** `git add static/app.js && git commit -m "fix: A/D en huecos entre subtitulos ya no salta al inicio"`

### Task 2: Diccionario de formas (`app/forms.py`)

**Files:** Create: `app/forms.py`, `tests/test_forms.py` · Modify: `app/config.py`

- [ ] **Step 2.1: Añadir URL a `app/config.py`** (junto a `BIDIX_URL`):

```python
# Diccionario de formas flexionadas de Softcatalà (LanguageTool):
# 1,3M líneas "forma lema ETIQUETA" — form->lemma para corregir a spaCy.
FORMS_URL = ("https://raw.githubusercontent.com/Softcatala/catalan-dict-tools/"
             "master/resultats/lt/diccionari.txt")
```

- [ ] **Step 2.2: Test que falla** — `tests/test_forms.py`:

```python
import sqlite3

from app import forms

SAMPLE = """ets ser VSIP2S00
gossos gos NCMP000
Barcelona Barcelona NPFSG00
casa casa NCFS000
casa casar VMIP3S0
"""


def _db(tmp_path):
    db = tmp_path / "forms.sqlite"
    forms.build(SAMPLE, db)
    return sqlite3.connect(str(db), check_same_thread=False)


def test_build_and_lookup(tmp_path, monkeypatch):
    con = _db(tmp_path)
    monkeypatch.setattr(forms, "_CON", con)
    monkeypatch.setattr(forms, "_TRIED", True)
    assert forms.lookup("ets") == [("ser", "VERB")]
    assert forms.lookup("Ets") == [("ser", "VERB")]        # cae a minúscula
    assert forms.lookup("gossos") == [("gos", "NOUN")]
    assert ("casa", "NOUN") in forms.lookup("casa")
    assert ("casar", "VERB") in forms.lookup("casa")
    assert forms.lookup("zzz") == []


def test_proper_noun_helpers(tmp_path, monkeypatch):
    con = _db(tmp_path)
    monkeypatch.setattr(forms, "_CON", con)
    monkeypatch.setattr(forms, "_TRIED", True)
    assert forms.known_exact("Barcelona") is True
    assert forms.known_exact("Ets") is False
    assert forms.knows_lower("Ets") is True
    assert forms.knows_lower("Barcelona") is False   # "barcelona" no existe
```

- [ ] **Step 2.3: Run** `.venv/bin/python -m pytest tests/test_forms.py -q` → FAIL (módulo no existe).

- [ ] **Step 2.4: Implementar `app/forms.py`:**

```python
"""Softcatalà/LanguageTool forms dictionary: inflected form -> (lemma, POS).

diccionari.txt (1.3M lines, "form lemma TAG") is downloaded once and dumped
into a small SQLite index so lookups don't keep ~300 MB of dicts in RAM.
Everything degrades to empty results when the file can't be fetched.
"""
import sqlite3
from pathlib import Path

import requests

from . import config

_TXT_PATH = config.MODELS_DIR / "diccionari-lt.txt"
_DB_PATH = config.MODELS_DIR / "forms.sqlite"

_CON = None
_TRIED = False

_POS = {"V": "VERB", "N": "NOUN", "A": "ADJ", "R": "ADV", "D": "DET",
        "P": "PRON", "C": "CONJ", "S": "ADP", "I": "INTJ", "M": "NUM",
        "Z": "NUM"}


def _pos_of(tag: str) -> str:
    if tag.startswith("NP"):
        return "PROPN"
    return _POS.get(tag[:1], "")


def build(txt: str, db_path: Path):
    """One-shot dump of diccionari.txt into an indexed SQLite file."""
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(str(db_path))
    con.execute("CREATE TABLE forms (form TEXT, lemma TEXT, pos TEXT)")
    def rows():
        for line in txt.splitlines():
            p = line.split(" ")
            if len(p) >= 3 and p[0] and p[1]:
                yield p[0], p[1], _pos_of(p[2])
    con.executemany("INSERT INTO forms VALUES (?,?,?)", rows())
    con.execute("CREATE INDEX ix_form ON forms(form)")
    con.commit()
    con.close()


def _con():
    global _CON, _TRIED
    if _CON is None and not _TRIED:
        _TRIED = True
        try:
            if not _DB_PATH.exists():
                if not _TXT_PATH.exists():
                    resp = requests.get(config.FORMS_URL, timeout=120)
                    resp.raise_for_status()
                    _TXT_PATH.write_text(resp.text, encoding="utf-8")
                build(_TXT_PATH.read_text(encoding="utf-8"), _DB_PATH)
            _CON = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        except Exception:
            _CON = None
    return _CON


def lookup(form: str) -> list[tuple[str, str]]:
    """[(lemma, POS)] for the exact form, falling back to lowercase."""
    con = _con()
    if con is None or not form:
        return []
    for f in dict.fromkeys((form, form.lower())):
        rs = con.execute("SELECT DISTINCT lemma, pos FROM forms WHERE form=?",
                         (f,)).fetchall()
        if rs:
            return [(r[0], r[1]) for r in rs]
    return []


def known_exact(form: str) -> bool:
    """The form exists spelled exactly like this (e.g. 'Barcelona')."""
    con = _con()
    if con is None:
        return False
    return con.execute("SELECT 1 FROM forms WHERE form=? LIMIT 1",
                       (form,)).fetchone() is not None


def knows_lower(form: str) -> bool:
    """The lowercased form is a known common word (e.g. 'Ets' -> 'ets')."""
    con = _con()
    if con is None:
        return False
    return con.execute("SELECT 1 FROM forms WHERE form=? LIMIT 1",
                       (form.lower(),)).fetchone() is not None
```

- [ ] **Step 2.5: Run** `.venv/bin/python -m pytest tests/test_forms.py -q` → PASS.
- [ ] **Step 2.6: Commit.** `git add app/forms.py app/config.py tests/test_forms.py && git commit -m "feat: diccionario de formas Softcatala/LT indexado en sqlite"`

### Task 3: Corrección de lemas en `nlp.tokenize`

**Files:** Modify: `app/nlp.py`, `tests/test_nlp.py`

- [ ] **Step 3.1: Test que falla** — añadir a `tests/test_nlp.py`:

```python
def test_correct_lemma_overrides_spacy(monkeypatch):
    from app import forms
    monkeypatch.setattr(forms, "lookup",
                        lambda f: [("ser", "VERB")] if f.lower() == "ets" else [])
    # spaCy se equivocó ("et" NOUN) y el dicc. de formas no lo avala -> corrige
    assert nlp._correct("Ets", "et", "NOUN") == ("ser", "VERB")
    # spaCy coincide con un candidato -> se respeta su desambiguación
    monkeypatch.setattr(forms, "lookup",
                        lambda f: [("casa", "NOUN"), ("casar", "VERB")])
    assert nlp._correct("casa", "casar", "VERB") == ("casar", "VERB")
    # sin entrada en el diccionario -> spaCy tal cual
    monkeypatch.setattr(forms, "lookup", lambda f: [])
    assert nlp._correct("blau", "blau", "ADJ") == ("blau", "ADJ")


def test_correct_pos_match_wins(monkeypatch):
    from app import forms
    monkeypatch.setattr(forms, "lookup",
                        lambda f: [("casa", "NOUN"), ("casar", "VERB")])
    # spaCy dice VERB con lema desconocido -> gana el candidato VERB
    assert nlp._correct("casa", "cassar", "VERB") == ("casar", "VERB")
    # AUX cuenta como VERB
    monkeypatch.setattr(forms, "lookup", lambda f: [("ser", "VERB")])
    assert nlp._correct("ets", "et", "AUX") == ("ser", "AUX")
```

- [ ] **Step 3.2: Run** `pytest tests/test_nlp.py -q` → FAIL (`_correct` no existe).

- [ ] **Step 3.3: Implementar en `app/nlp.py`:**

Al principio del módulo (tras `_WORD`):

```python
# Bump para re-tokenizar transcripciones guardadas con lemas antiguos.
TOK_VERSION = 1

_POS_EQ = {("VERB", "AUX"), ("AUX", "VERB")}


def _correct(form: str, lemma: str, pos: str) -> tuple[str, str]:
    """Fix spaCy's lemma with the Softcatalà forms dictionary.

    spaCy sm mangles capitalized sentence-initial forms ('Ets' -> 'et' NOUN);
    the forms dict is authoritative, spaCy only disambiguates homographs.
    """
    from . import forms
    cands = forms.lookup(form)
    if not cands:
        return lemma, pos
    if lemma in {c[0].lower() for c in cands}:
        return lemma, pos
    for cl, cp in cands:
        if cp == pos or (cp, pos) in _POS_EQ:
            return cl.lower(), pos
    cl, cp = cands[0]
    return cl.lower(), cp or pos
```

En `tokenize()` (rama spaCy), sustituir la construcción del dict por:

```python
    for tok in nlp_model(text):
        if tok.is_space:
            continue
        is_word = not tok.is_punct
        lemma, pos = ("", "")
        if is_word:
            lemma, pos = _correct(tok.text, tok.lemma_.lower(), tok.pos_)
        toks.append({"t": tok.text, "lemma": lemma, "pos": pos,
                     "is_word": is_word,
                     "zipf": zipf(tok.text) if is_word else 0.0})
```

En `naive_tokenize()`, sustituir la línea del token palabra por:

```python
        w = m.group(0)
        lemma, pos = _correct(w, w.lower(), "")
        toks.append({"t": w, "lemma": lemma, "pos": pos,
                     "is_word": True, "zipf": zipf(w)})
```

- [ ] **Step 3.4: Run** `pytest tests/test_nlp.py -q` → PASS. Después toda la suite: `pytest tests/ -q` (la descarga real del diccionario no debe dispararse en tests: `_correct` importa `forms` de forma lazy y los tests existentes de tokenize podrían descargarlo — si algún test llama a `tokenize()` sin mock, añadir en `tests/conftest.py`:

```python
import pytest


@pytest.fixture(autouse=True)
def no_forms_download(monkeypatch):
    """Los tests nunca descargan el diccionario de formas real."""
    from app import forms
    if not forms._DB_PATH.exists():
        monkeypatch.setattr(forms, "_TRIED", True)
```

(si `tests/conftest.py` no existe, crearlo con este contenido).
- [ ] **Step 3.5: Commit.** `git add app/nlp.py tests/ && git commit -m "feat: lemas corregidos con el diccionario de formas (caso Ets)"`

### Task 4: `tok_version` + re-tokenización de sesiones antiguas

**Files:** Modify: `app/db.py`, `app/main.py`, `tests/test_db.py`

- [ ] **Step 4.1: Test que falla** — añadir a `tests/test_db.py`:

```python
def test_tok_version_column_and_update(tmp_path):
    con = db.connect(tmp_path / "t.db")
    sid = db.create_session(
        con, title="V", source_type="local", media_path="/x.mp4",
        srt_source="whisper", model_size="small", duration_secs=10,
        transcript_json="[]")
    assert db.get_session(con, sid)["tok_version"] == 0
    db.update_transcript(con, sid, "[]", "small", "whisper", tok_version=3)
    assert db.get_session(con, sid)["tok_version"] == 3
```

(usar el import ya existente del módulo en ese archivo; si es `from app import db`, vale tal cual).

- [ ] **Step 4.2: Run** `pytest tests/test_db.py -q` → FAIL.

- [ ] **Step 4.3: Implementar en `app/db.py`:**

En `connect()`, tras `con.executescript(SCHEMA)`:

```python
    # migración: versión del tokenizador con que se guardó la transcripción
    cols = {r["name"] for r in con.execute("PRAGMA table_info(sessions)")}
    if "tok_version" not in cols:
        con.execute("ALTER TABLE sessions ADD COLUMN tok_version "
                    "INTEGER NOT NULL DEFAULT 0")
```

`update_transcript` gana el parámetro:

```python
def update_transcript(con, sid, transcript_json, model_size, srt_source,
                      tok_version=0):
    con.execute(
        "UPDATE sessions SET transcript_json=?, model_size=?, srt_source=?, "
        "tok_version=?, updated_at=? WHERE id=?",
        (transcript_json, model_size, srt_source, tok_version, _now(), sid))
    con.commit()
```

- [ ] **Step 4.4: Actualizar call sites en `app/main.py`** — todos los `db.update_transcript(...)` que guardan tokens recién generados pasan `nlp.TOK_VERSION`: en `youtube_import` (subs de YouTube), en `do_transcribe` (ambas ramas) y en `attach_subtitles`. El de `translate_segment` (solo cachea `text_es`) pasa la versión que ya tenía la sesión: `s.get("tok_version") or 0`.

- [ ] **Step 4.5: Re-tokenización perezosa en `session_detail`** (`app/main.py`), tras poblar `s["transcript"]`:

```python
    if s["transcript"] and (s.get("tok_version") or 0) < nlp.TOK_VERSION:
        for seg in s["transcript"]:
            seg["tokens"] = nlp.tokenize(seg["text"])
        db.update_transcript(CON, sid, json.dumps(s["transcript"]),
                             s["model_size"], s["srt_source"],
                             nlp.TOK_VERSION)
        s["tok_version"] = nlp.TOK_VERSION
```

- [ ] **Step 4.6: Test del endpoint** — añadir a `tests/test_api_v2.py` (o nuevo `tests/test_api_v3.py` si encaja mejor; usar el helper `client(tmp_path)` del archivo):

```python
def test_session_detail_retokenizes_old_transcripts(tmp_path):
    import json
    c = client(tmp_path)
    sid = main.db.create_session(
        main.CON, title="V", source_type="local", media_path="/x.mp4",
        srt_source="srt", model_size="-", duration_secs=10,
        transcript_json=json.dumps([{"start": 0.0, "end": 1.0,
                                     "text": "El gos corre", "words": [],
                                     "logprob": 0.0, "tokens": []}]))
    body = c.get("/api/sessions/" + sid).json()
    assert body["tok_version"] == main.nlp.TOK_VERSION
    words = [t["t"] for t in body["transcript"][0]["tokens"] if t["is_word"]]
    assert "gos" in words
```

- [ ] **Step 4.7: Run** `pytest tests/ -q` → PASS. **Commit:** `git add app/db.py app/main.py tests/ && git commit -m "feat: tok_version + retokenizacion perezosa de sesiones antiguas"`

### Task 5: Traducciones conscientes de mayúscula inicial

**Files:** Modify: `app/translate.py`, `tests/test_translate.py`

- [ ] **Step 5.1: Tests que fallan** — añadir a `tests/test_translate.py`:

```python
from unittest.mock import patch


FAKE = {"Ets molt intel·ligent, tu.": "Ets muy inteligente, tú.",
        "ets molt intel·ligent, tu.": "eres muy inteligente, tú.",
        "Barcelona és gran.": "Barcelona es grande.",
        "barcelona és gran.": "barcelona es grande."}


def _fake_translate(text):
    return FAKE.get(text, "X:" + text)


def test_sentence_decapitalizes_untranslated_leading_verb(monkeypatch):
    from app import forms, translate
    monkeypatch.setattr(translate, "translate", _fake_translate)
    monkeypatch.setattr(forms, "known_exact", lambda w: w == "Barcelona")
    monkeypatch.setattr(forms, "knows_lower", lambda w: w.lower() == "ets")
    assert translate.sentence("Ets molt intel·ligent, tu.") == \
        "Eres muy inteligente, tú."


def test_sentence_keeps_proper_nouns(monkeypatch):
    from app import forms, translate
    monkeypatch.setattr(translate, "translate", _fake_translate)
    monkeypatch.setattr(forms, "known_exact", lambda w: w == "Barcelona")
    monkeypatch.setattr(forms, "knows_lower", lambda w: False)
    assert translate.sentence("Barcelona és gran.") == "Barcelona es grande."
```

- [ ] **Step 5.2: Run** `pytest tests/test_translate.py -q` → FAIL (`sentence` no existe).

- [ ] **Step 5.3: Implementar en `app/translate.py`:**

```python
import re

_LEAD = re.compile(r"[^\W\d_]+", re.UNICODE)


def sentence(text: str) -> str:
    """translate() + reintento decapitalizado cuando el modelo deja la
    primera palabra sin traducir por ir en mayúscula ('Ets molt...' ->
    'Ets muy...'): se decapitaliza, retraduce y recapitaliza."""
    out = translate(text)
    if not out:
        return out
    m = _LEAD.search(text)
    if not m:
        return out
    w = m.group(0)
    if not w[0].isupper() or w.lower() == w or w not in out:
        return out
    from . import forms
    if forms.known_exact(w) or not forms.knows_lower(w):
        return out
    decap = text[:m.start()] + w[0].lower() + w[1:] + text[m.end():]
    out2 = translate(decap)
    if not out2 or w in out2:
        return out
    return out2[:1].upper() + out2[1:]
```

- [ ] **Step 5.4: Run** `pytest tests/test_translate.py -q` → PASS.
- [ ] **Step 5.5: Usar `translate.sentence` en `app/main.py`:** en `lookup` (campo `sentence_es`), en el preview de tarjeta (`frase_es`) y en `translate_segment` (cache `text_es`). Buscar los tres `translate.translate(` de frase completa y cambiarlos a `translate.sentence(`. (El de palabra suelta se toca en Task 6.)
- [ ] **Step 5.6: Run** `pytest tests/ -q` → PASS (los tests existentes de preview mockean `main.translate.translate`; si alguno rompe porque ahora se llama `sentence`, parchear en ese test también `app.main.translate.sentence` con el mismo side_effect). **Commit:** `git add app/translate.py app/main.py tests/ && git commit -m "feat: traduccion de frases robusta ante mayuscula inicial"`

### Task 6: Lookup rico — prioridad de acepciones, WSD, word_es, IPA, caché de frase

**Files:** Create: `app/ipa.py` · Modify: `app/main.py`, `tests/test_api_v3.py` (nuevo)

- [ ] **Step 6.1: `app/ipa.py`:**

```python
"""Optional IPA via espeak-ng (brew). Empty string when unavailable."""
import shutil
import subprocess
from functools import lru_cache


@lru_cache(maxsize=4096)
def ipa(text: str) -> str:
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe or not text:
        return ""
    try:
        out = subprocess.run([exe, "-q", "--ipa", "-v", "ca", text],
                             capture_output=True, text=True, timeout=5)
        s = " ".join(out.stdout.split())
        return f"/{s}/" if s else ""
    except Exception:
        return ""
```

- [ ] **Step 6.2: Tests que fallan** — crear `tests/test_api_v3.py`:

```python
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
@patch("app.main.translate.translate", side_effect=lambda t: "eres" if t == "ets" else "T:" + t)
def test_lookup_word_es_uses_lowercase_form(_tr, _sen, _ipa, tmp_path, monkeypatch):
    from app import forms
    c = client(tmp_path)
    monkeypatch.setattr(forms, "known_exact", lambda w: False)
    monkeypatch.setattr(forms, "knows_lower", lambda w: w.lower() == "ets")
    r = c.post("/api/lookup", json={"selection": "Ets",
                                    "sentence": "Ets molt intel·ligent, tu."}).json()
    assert r["word_es"] == "eres"
    assert r["ipa"] == "/əts/"
    assert "active" in r
```

- [ ] **Step 6.3: Run** `pytest tests/test_api_v3.py -q` → FAIL.

- [ ] **Step 6.4: Implementar en `app/main.py`:**

Imports: añadir `forms`, `ipa` al `from . import ...`.

Helpers (junto a `_dict()`):

```python
def _senses(selection: str, lemma: str, d=None) -> list[tuple[str, str]]:
    """Acepciones del bidix: lema primero (palabra única) para que un
    homógrafo superficial (p. ej. el acrónimo ETS) no tape al lema."""
    d = d or _dict()
    if " " in selection.strip():
        return d.lookup(selection) or d.lookup(lemma)
    return d.lookup(lemma) or d.lookup(selection)


def _active_sense(senses, sentence_es: str, word_es: str) -> int:
    """WSD ligero: la acepción cuya 1.ª palabra aparece en la traducción
    de la frase (o coincide con word_es) se preselecciona en el popup."""
    if not senses:
        return -1
    import re
    words = set(re.findall(r"[^\W\d_]+", sentence_es.lower(), re.UNICODE))
    for i, (es, _p) in enumerate(senses):
        head = (es.lower().split() or [""])[0]
        if head and (head in words or
                     (len(head) >= 5 and
                      any(w.startswith(head[:-1]) for w in words))):
            return i
    wl = word_es.strip().lower()
    if wl:
        for i, (es, _p) in enumerate(senses):
            if es.strip().lower() == wl:
                return i
    return 0


def _word_es(selection: str, lemma: str) -> str:
    """Traducción de la palabra conservando conjugación: si 'Ets' no es
    nombre propio se traduce 'ets' -> 'eres'; si aun así no cambia, cae
    al lema."""
    w = selection
    if not forms.known_exact(w) and forms.knows_lower(w):
        w = w.lower()
    out = translate.translate(w)
    if (out.strip().lower() == selection.strip().lower()
            and lemma and lemma != w.lower()):
        alt = translate.translate(lemma)
        if alt:
            out = alt
    return out


def _segment_es(sid: str, idx: int) -> str:
    """text_es cacheado del segmento (lo crea si falta)."""
    s = db.get_session(CON, sid)
    if not s:
        return ""
    segs = json.loads(s["transcript_json"])
    if not 0 <= idx < len(segs):
        return ""
    if not segs[idx].get("text_es"):
        segs[idx]["text_es"] = translate.sentence(segs[idx]["text"])
        db.update_transcript(CON, sid, json.dumps(segs), s["model_size"],
                             s["srt_source"], s.get("tok_version") or 0)
    return segs[idx]["text_es"]
```

`LookupReq` y `lookup`:

```python
class LookupReq(BaseModel):
    selection: str
    sentence: str = ""
    session_id: str = ""
    segment_index: int = -1


@app.post("/api/lookup")
def lookup(req: LookupReq):
    """Info instantánea para el popup (sin generar media)."""
    lemma, pos = nlp.analyze_selection(req.selection, req.sentence)
    z = nlp.zipf(req.selection)
    senses = _senses(req.selection, lemma)
    word_es = _word_es(req.selection, lemma)
    sentence_es = ""
    if req.session_id and req.segment_index >= 0:
        sentence_es = _segment_es(req.session_id, req.segment_index)
    if not sentence_es and req.sentence:
        sentence_es = translate.sentence(req.sentence)
    return {
        "selection": req.selection,
        "lemma": lemma, "pos": pos,
        "zipf": z, "freq_rank": nlp.freq_badge(z),
        "senses": [{"es": es, "pos": p} for es, p in senses[:8]],
        "active": _active_sense(senses[:8], sentence_es, word_es),
        "word_es": word_es,
        "sentence_es": sentence_es,
        "ipa": ipa.ipa(req.selection),
    }
```

`translate_segment` pasa a delegar: `return {"index": idx, "text_es": _segment_es(sid, idx)}` (tras validar sesión/índice como hasta ahora). En `card_preview`, usar también `_senses` y `_word_es` (sustituyendo `senses = _dict().lookup(...) or ...` y `"paraula_es": translate.translate(req.selection)`).

- [ ] **Step 6.5: Run** `pytest tests/ -q` → PASS (ajustar mocks antiguos si referencian el orden viejo de lookup).
- [ ] **Step 6.6: Commit.** `git add app/ipa.py app/main.py tests/test_api_v3.py && git commit -m "feat: lookup con prioridad de lema, WSD ligero, word_es contextual e IPA"`

### Task 7: Endpoint de minado one-shot `/api/cards/mine`

**Files:** Modify: `app/main.py`, `tests/test_api_v3.py`

- [ ] **Step 7.1: Test que falla** — añadir a `tests/test_api_v3.py`:

```python
@patch("app.main._flush", return_value=1)
@patch("app.main.media.animated_clip")
@patch("app.main.media.snapshot")
@patch("app.main.media.cut_audio")
@patch("app.main.translate.sentence", side_effect=lambda t: "ES:" + t)
@patch("app.main.translate.translate", side_effect=lambda t: "ES:" + t)
def test_mine_creates_and_flushes(_tr, _sen, _cut, _snap, _clip, _fl, tmp_path):
    c = client(tmp_path)
    sid = _seg_session("El gos corre")
    r = c.post("/api/cards/mine",
               json={"session_id": sid, "segment_index": 0,
                     "selection": "gos"}).json()
    assert r["sent_now"] is True
    assert r["paraula"] == "gos"
    assert r["word_status"] == "learning"
    cards = main.db.pending_cards(main.CON) + \
        [dict(x) for x in main.CON.execute("SELECT * FROM cards")]
    assert any(cc["paraula"] == "gos" for cc in cards)


@patch("app.main._flush", return_value=0)
@patch("app.main.media.animated_clip")
@patch("app.main.media.snapshot")
@patch("app.main.media.cut_audio")
@patch("app.main.translate.sentence", side_effect=lambda t: "ES:" + t)
@patch("app.main.translate.translate", side_effect=lambda t: "ES:" + t)
def test_mine_respects_chosen_sense(_tr, _sen, _cut, _snap, _clip, _fl, tmp_path):
    c = client(tmp_path)
    sid = _seg_session("El gos corre")
    r = c.post("/api/cards/mine",
               json={"session_id": sid, "segment_index": 0,
                     "selection": "gos", "paraula_es": "perro"}).json()
    assert r["sent_now"] is False
    row = main.CON.execute("SELECT paraula_es FROM cards").fetchone()
    assert row["paraula_es"] == "perro"
```

- [ ] **Step 7.2: Run** → FAIL (404 en `/api/cards/mine`).

- [ ] **Step 7.3: Implementar.** Extraer el cuerpo de `card_preview` a un helper y añadir el endpoint:

```python
def _build_preview(s: dict, segment_index: int, selection: str,
                   pad_before: int = 0, pad_after: int = 0) -> dict:
    segs = json.loads(s["transcript_json"])
    seg = segs[segment_index]
    start = segs[max(0, segment_index - pad_before)]["start"]
    end = segs[min(len(segs) - 1, segment_index + pad_after)]["end"]

    base = uuid.uuid4().hex[:10]
    audio_name, image_name = f"cm-{base}.mp3", f"cm-{base}.jpg"
    clip_name = f"cm-{base}.gif"
    audio_ok = image_ok = clip_ok = True
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
    try:
        if image_ok:
            media.animated_clip(s["media_path"], seg["start"], seg["end"],
                                str(config.MEDIA_DIR / clip_name))
        else:
            clip_ok = False
    except Exception:
        clip_ok = False

    lemma, pos = nlp.analyze_selection(selection, seg["text"])
    z = nlp.zipf(selection)
    senses = _senses(selection, lemma)
    frase_es = translate.sentence(seg["text"])
    word_es = _word_es(selection, lemma)
    return {
        "paraula": selection,
        "lema": lemma, "pos": pos,
        "paraula_es": word_es,
        "senses": [{"es": es, "pos": p} for es, p in senses[:8]],
        "active": _active_sense(senses[:8], frase_es, word_es),
        "frase": seg["text"],
        "frase_es": frase_es,
        "freq_zipf": z, "freq_rank": nlp.freq_badge(z),
        "audio_file": audio_name if audio_ok else "",
        "image_file": image_name if image_ok else "",
        "clip_file": clip_name if clip_ok else "",
        "font": f"{s['title']} @ {_fmt_ts(seg['start'])}",
    }


@app.post("/api/cards/preview")
def card_preview(req: PreviewReq):
    s = db.get_session(CON, req.session_id)
    if not s:
        return JSONResponse({"error": "not found"}, status_code=404)
    return _build_preview(s, req.segment_index, req.selection,
                          req.pad_before, req.pad_after)


class MineReq(BaseModel):
    session_id: str
    segment_index: int
    selection: str
    paraula_es: str = ""


@app.post("/api/cards/mine")
def card_mine(req: MineReq):
    """Minado one-shot: preview + alta + envío a Anki, sin panel."""
    s = db.get_session(CON, req.session_id)
    if not s:
        return JSONResponse({"error": "not found"}, status_code=404)
    p = _build_preview(s, req.segment_index, req.selection)
    active_es = (p["senses"][p["active"]]["es"]
                 if p["senses"] and p["active"] >= 0 else "")
    paraula_es = req.paraula_es or p["paraula_es"] or active_es
    cid = db.create_card(
        CON, session_id=req.session_id, segment_index=req.segment_index,
        paraula=p["paraula"], lema=p["lema"], pos=p["pos"],
        paraula_es=paraula_es, frase=p["frase"], frase_es=p["frase_es"],
        freq_rank=p["freq_rank"], audio_file=p["audio_file"],
        image_file=p["clip_file"] or p["image_file"], font=p["font"])
    if p["lema"]:
        db.mark_learning_if_new(CON, p["lema"])
    sent = _flush()
    return {"card_id": cid, "sent_now": sent > 0,
            "pending": len(db.pending_cards(CON)),
            "word_status": db.word_statuses(CON).get(p["lema"]),
            "lema": p["lema"], "paraula": p["paraula"]}
```

- [ ] **Step 7.4: Run** `pytest tests/ -q` → PASS.
- [ ] **Step 7.5: Commit.** `git add app/main.py tests/test_api_v3.py && git commit -m "feat: endpoint /api/cards/mine (minado en segundo plano)"`

### Task 8: Frontend — minado en segundo plano (Q / Shift+Q / acepciones)

**Files:** Modify: `static/app.js`, `static/index.html`, `README.md`

- [ ] **Step 8.1: `mineQuick` en `app.js`** (junto a `mine`):

```js
async function mineQuick(segIndex, selection, paraula_es = "") {
  toast("⛏️ Creando tarjeta…");
  const r = await api("/api/cards/mine", {
    method: "POST",
    body: JSON.stringify({ session_id: SESSION.id, segment_index: segIndex,
      selection, paraula_es }),
  });
  if (r.error) { toast(r.error, "err"); return; }
  if (r.word_status) STATUS[r.lema] = r.word_status;
  renderSegs(); renderOverlay(); updateComp(); refreshAnki();
  toast(r.sent_now ? `✅ «${r.paraula}» → Anki` : `🕓 «${r.paraula}» en cola`,
        r.sent_now ? "ok" : "err");
}
```

- [ ] **Step 8.2: Rutas de creación.**
  - `mineFromPopup()` pasa a: `const { segIndex, selection, chosen } = POP; closePopup(); mineQuick(segIndex, selection, chosen || "");`
  - Nueva `editFromPopup()`: `const { segIndex, selection } = POP; closePopup(); mine(segIndex, selection);` (flujo de panel actual).
  - Acepciones del popup: `sp.onclick = () => { POP.chosen = sp.dataset.es; mineFromPopup(); };` (sin cambio, ahora es instantáneo).
  - Teclado `q`: `if (e.shiftKey)` → flujo panel (`mine(...)`); sin shift → `mineQuick(...)` (con `POP.chosen || ""` si hay popup):

```js
  else if (k === "q") {
    const inPop = POP && !$("word-pop").hidden;
    const seg = inPop ? POP.segIndex : HOVER?.segIndex;
    const sel = inPop ? POP.selection : HOVER?.text;
    if (sel === undefined) { toast("Pasa el ratón por una palabra y pulsa Q", "err"); return; }
    const chosen = inPop ? (POP.chosen || "") : "";
    if (inPop) closePopup();
    if (e.shiftKey) mine(seg, sel);
    else mineQuick(seg, sel, chosen);
  }
```

  - `mine()` conserva `V.pause()` (el panel implica edición).
- [ ] **Step 8.3: `index.html`:** actualizar `#help-line`: `… · Q tarjeta · ⇧Q editar tarjeta · …`. **README.md:** misma actualización en la línea de atajos.
- [ ] **Step 8.4: Verificar** con el servidor: hover sobre palabra + `Q` → toast y tarjeta creada (revisar `/api/anki/status` para `pending` si Anki cerrado); `Shift+Q` → abre el panel antiguo.
- [ ] **Step 8.5: Commit.** `git add static/ README.md && git commit -m "feat: minado en segundo plano con Q; Shift+Q abre el editor"`

### Task 9: Popup por hover con pausa/reanudación

**Files:** Modify: `static/app.js`

- [ ] **Step 9.1: Estado nuevo** (junto a `POP`): `let PINNED = false, RESUME = false, HOVER_TIMER = null, CLOSE_TIMER = null;` y `const LOOKUP_CACHE = {};` (vaciarlo en `openSession`, junto a `ES_CACHE`).

- [ ] **Step 9.2: `bindTokenEvents`:**

```js
function bindTokenEvents(container, segIndex) {
  for (const tok of container.querySelectorAll(".t")) {
    tok.onclick = (ev) => {
      ev.stopPropagation();
      const sel = window.getSelection().toString().trim();
      openPopup(segIndex, sel || tok.textContent, tok, true);
    };
    tok.onmouseenter = () => {
      HOVER = { segIndex, text: tok.textContent, lemma: tok.dataset.l, el: tok };
      clearTimeout(CLOSE_TIMER);
      if (PINNED) return;
      clearTimeout(HOVER_TIMER);
      HOVER_TIMER = setTimeout(
        () => openPopup(segIndex, tok.textContent, tok, false), 180);
    };
    tok.onmouseleave = () => {
      if (HOVER && HOVER.el === tok) HOVER = null;
      clearTimeout(HOVER_TIMER);
      if (!PINNED && !$("word-pop").hidden) scheduleClose();
    };
  }
}

function scheduleClose() {
  clearTimeout(CLOSE_TIMER);
  CLOSE_TIMER = setTimeout(() => { if (!PINNED) closePopup(); }, 250);
}
```

- [ ] **Step 9.3: `openPopup` con `pin` y caché:**

```js
async function openPopup(segIndex, selection, anchorEl, pin) {
  if (pin && POP && !$("word-pop").hidden &&
      POP.selection === selection && POP.segIndex === segIndex) {
    closePopup();
    return;
  }
  if (!V.paused) { V.pause(); RESUME = !pin; }
  PINNED = !!pin;
  POP = { segIndex, selection,
          lemma: (anchorEl.dataset?.l || selection).toLowerCase() };
  $("wp-word").textContent = selection;
  $("wp-ipa").textContent = "";
  $("wp-meta").textContent = "…";
  $("wp-level").textContent = "";
  $("wp-senses").innerHTML = "";
  $("wp-word-es").textContent = "";
  $("wp-sentence-es").textContent = "";
  $("wp-sentence-ca").textContent = SEGS[segIndex].text;
  markStatusButtons(stOf(POP.lemma));
  positionPopup(anchorEl);
  $("word-pop").hidden = false;

  const key = segIndex + ":" + selection;
  let r = LOOKUP_CACHE[key];
  if (!r) {
    r = await api("/api/lookup", {
      method: "POST",
      body: JSON.stringify({ selection, sentence: SEGS[segIndex].text,
        session_id: SESSION.id, segment_index: segIndex }),
    });
    LOOKUP_CACHE[key] = r;
  }
  if (!POP || POP.selection !== selection || POP.segIndex !== segIndex) return;
  POP.lookup = r;
  POP.lemma = r.lemma;
  markStatusButtons(stOf(r.lemma));
  renderPopupLookup(r);
}
```

(`renderPopupLookup` se define en Task 10; hasta entonces, mantener temporalmente el bloque actual que rellena `wp-meta`, `wp-senses`, `wp-word-es`, `wp-sentence-es`.)

- [ ] **Step 9.4: Cierre y reanudación:**

```js
function closePopup() {
  $("word-pop").hidden = true;
  POP = null; PINNED = false;
  clearTimeout(HOVER_TIMER); clearTimeout(CLOSE_TIMER);
  if (RESUME) { RESUME = false; V.play(); }
}
```

Tras definir `V` (sección video): `V.addEventListener("play", () => { RESUME = false; });` — si el usuario reanuda a mano, no auto-reanudamos luego. *Nota:* en `closePopup` se pone `RESUME = false` **antes** de `V.play()`, así el listener no interfiere.

Al final de init del popup:

```js
const WP = $("word-pop");
WP.onmouseenter = () => clearTimeout(CLOSE_TIMER);
WP.onmouseleave = () => { if (!PINNED) scheduleClose(); };
```

- [ ] **Step 9.5: Verificar:** reproducir video → hover sobre palabra del overlay: se pausa y abre popup; mover el ratón al popup: sigue abierto; salir: se cierra y reanuda. Pausar a mano, hover, salir: NO reanuda. Clic en palabra: popup fijado, no se cierra al salir; `Esc` lo cierra sin reanudar. Selección arrastrando varias palabras: popup fijado de la expresión.
- [ ] **Step 9.6: Commit.** `git add static/app.js && git commit -m "feat: popup por hover con pausa/reanudacion y fijado por clic"`

### Task 10: Rediseño del popup estilo Migaku

**Files:** Modify: `static/index.html`, `static/style.css`, `static/app.js`

- [ ] **Step 10.1: HTML** — sustituir el contenido de `#word-pop`:

```html
<div id="word-pop" hidden>
  <div class="wp-head">
    <span id="wp-word"></span><span id="wp-ipa"></span>
    <button id="wp-close">✕</button>
  </div>
  <div class="wp-chips">
    <span id="wp-level" class="wp-chip"></span>
    <span id="wp-meta"></span>
  </div>
  <div class="wp-icons">
    <button id="wp-replay" class="wp-ic" title="Repetir segmento (S)">🔊</button>
    <button id="wp-card" class="wp-ic wp-primary" title="Crear tarjeta (Q)">➕</button>
    <button id="wp-edit" class="wp-ic" title="Editar y crear (⇧Q)">✏️</button>
  </div>
  <div id="wp-ctx">
    <div id="wp-sentence-es"></div>
    <div id="wp-sentence-ca"></div>
  </div>
  <div id="wp-senses"></div>
  <div id="wp-foot"><span id="wp-word-es"></span></div>
  <div id="wp-status">
    <button data-st="unknown" title="Atajo: 1">Nueva</button>
    <button data-st="learning" title="Atajo: 2">Aprendiendo</button>
    <button data-st="known" title="Atajo: 3">Conocida</button>
    <button data-st="ignored" title="Atajo: 4">Ignorar</button>
  </div>
</div>
```

- [ ] **Step 10.2: `renderPopupLookup(r)` en `app.js`** (sustituye el bloque de relleno del final de `openPopup`):

```js
const LEVEL_LABEL = { 5: "muy frecuente", 4: "frecuente", 3: "media", 2: "poco común", 1: "rara" };
function zipfLevel(z) { return z >= 5.5 ? 5 : z >= 5 ? 4 : z >= 4.3 ? 3 : z >= 3.3 ? 2 : 1; }

function renderPopupLookup(r) {
  $("wp-ipa").textContent = r.ipa || "";
  const lvl = zipfLevel(r.zipf);
  $("wp-level").textContent = `${LEVEL_LABEL[lvl]} ★${lvl}`;
  $("wp-meta").textContent = `${r.lemma}${r.pos ? " · " + r.pos : ""}`;
  $("wp-sentence-es").textContent = r.sentence_es || "";
  $("wp-senses").innerHTML = (r.senses.length ? r.senses : [])
    .map((s, i) => `<span class="sense${i === r.active ? " active" : ""}"
      data-es="${s.es}">${s.es} <small>${s.pos}</small></span>`).join("")
    || '<span class="dim" style="font-size:13px">— sin entrada en el diccionario —</span>';
  for (const sp of $("wp-senses").querySelectorAll(".sense"))
    sp.onclick = () => { POP.chosen = sp.dataset.es; mineFromPopup(); };
  if (r.senses.length && r.active >= 0) POP.active_es = r.senses[r.active].es;
  $("wp-word-es").textContent = r.word_es ? `→ ${r.word_es}` : "";
}
```

Cablear `$("wp-edit").onclick = () => editFromPopup();` junto a los handlers existentes de `wp-card`/`wp-replay`.

- [ ] **Step 10.3: CSS** — en `style.css`, actualizar el bloque de `#word-pop` (conservar paleta night-studio existente; usar las variables de color ya definidas en el archivo):

```css
#word-pop { width: 324px; border-radius: 18px; padding: 14px 16px; }
.wp-head { display: flex; align-items: baseline; gap: 8px; }
#wp-word { font-size: 26px; font-weight: 700; }
#wp-ipa { color: var(--dim, #9aa); font-size: 14px; flex: 1; }
.wp-chips { display: flex; gap: 8px; align-items: center; margin: 6px 0; }
.wp-chip { background: rgba(140,120,255,.18); color: #b9aaff;
  border-radius: 999px; padding: 2px 10px; font-size: 12px; font-weight: 600; }
#wp-meta { font-size: 12px; color: var(--dim, #9aa); }
.wp-icons { display: flex; gap: 10px; margin: 8px 0; }
.wp-ic { width: 38px; height: 38px; border-radius: 50%; border: none;
  background: rgba(255,255,255,.08); font-size: 16px; cursor: pointer; }
.wp-ic:hover { background: rgba(255,255,255,.16); }
.wp-primary { background: #7c5cff; }
#wp-ctx { margin: 8px 0; }
#wp-sentence-es { font-size: 14px; line-height: 1.45; }
#wp-sentence-ca { font-size: 13px; font-style: italic; color: var(--dim, #9aa);
  margin-top: 4px; }
#wp-senses .sense.active { outline: 2px solid #7c5cff; }
#wp-foot { display: flex; align-items: center; gap: 8px; margin: 6px 0; font-weight: 600; }
#wp-status button { border-radius: 999px; font-size: 12px; text-transform: none; }
```

(Ajustar selectores a los estilos previos del popup: reemplazar reglas obsoletas de `.wp-line`, `wp-actions`; revisar el resultado visualmente y afinar dentro del lenguaje visual del css existente.)

- [ ] **Step 10.4: Verificar en navegador** (hover sobre «Ets»): cabecera con IPA, chip «★», traducción ES arriba + CA cursiva debajo, acepción activa resaltada, pie `ser → eres`, pastillas de estado. Capturar pantalla y comparar contra la referencia Migaku.
- [ ] **Step 10.5: Commit.** `git add static/ && git commit -m "feat: popup rediseñado estilo Migaku (IPA, nivel, contexto, WSD)"`

### Task 11: Diálogo propio para el puerto de Anki (sin `prompt()`)

**Files:** Modify: `static/index.html`, `static/app.js`, `static/style.css`

- [ ] **Step 11.1: HTML** (antes de `#toast`):

```html
<dialog id="port-dlg">
  <form method="dialog">
    <h3>Puerto de AnkiConnect</h3>
    <p id="port-msg" class="dim"></p>
    <input id="port-input" type="number" min="1" max="65535"
           placeholder="vacío = automático (8765/8766/8767)">
    <div class="row actions">
      <button value="cancel" type="submit">Cancelar</button>
      <button value="ok" type="submit" class="primary">Guardar</button>
    </div>
  </form>
</dialog>
```

- [ ] **Step 11.2: JS** — sustituir el `prompt(...)` del handler `$("anki-badge").onclick`:

```js
$("anki-badge").onclick = () => {
  const reason = $("anki-badge").dataset.reason;
  $("port-msg").textContent = reason === "squatted"
    ? "Otro servicio ocupa los puertos 8765/8766. En Anki → Herramientas → Complementos → AnkiConnect → Configuración pon \"webBindPort\": 8767 y reinicia Anki (o escribe 8767 aquí)."
    : "Déjalo vacío para detectarlo automáticamente.";
  $("port-input").value = "";
  $("port-dlg").showModal();
};
$("port-dlg").addEventListener("close", async () => {
  if ($("port-dlg").returnValue !== "ok") return;
  const v = $("port-input").value.trim();
  const port = v === "" ? null : parseInt(v, 10);
  const r = await api("/api/anki/port", { method: "POST", body: JSON.stringify({ port }) });
  toast(r.port ? `✅ AnkiConnect encontrado en el puerto ${r.port}` : "Aún no encuentro AnkiConnect", r.port ? "ok" : "err");
  refreshAnki();
});
```

- [ ] **Step 11.3: CSS mínimo:**

```css
dialog { background: var(--panel, #1c1b2e); color: inherit; border: none;
  border-radius: 16px; padding: 18px 20px; width: min(420px, 90vw); }
dialog::backdrop { background: rgba(0,0,0,.55); }
```

- [ ] **Step 11.4: Verificar** clic en el badge de Anki → diálogo modal, guardar/cancelar funcionan. **Commit:** `git add static/ && git commit -m "feat: dialogo propio para el puerto de AnkiConnect (compatible WKWebView)"`

### Task 12: `/api/stats` + helpers de AnkiConnect

**Files:** Modify: `app/anki.py`, `app/main.py`, `tests/test_api_v3.py`

- [ ] **Step 12.1: Test que falla** — añadir a `tests/test_api_v3.py`:

```python
@patch("app.main.anki.is_up", return_value=False)
def test_stats_local_only_when_anki_down(_up, tmp_path):
    c = client(tmp_path)
    sid = _seg_session("El gos corre")
    main.db.create_card(
        main.CON, session_id=sid, segment_index=0, paraula="gos",
        lema="gos", pos="NOUN", paraula_es="perro", frase="El gos corre",
        frase_es="El perro corre", freq_rank="common", audio_file="",
        image_file="", font="V")
    main.db.set_word_status(main.CON, "gos", "learning")
    main.db.set_word_status(main.CON, "casa", "known")
    r = c.get("/api/stats").json()
    assert r["total_cards"] == 1
    assert r["status_counts"]["learning"] == 1
    assert r["status_counts"]["known"] == 1
    assert len(r["by_month"]) == 1
    assert r["anki"] is None
```

- [ ] **Step 12.2: Run** → FAIL (404).

- [ ] **Step 12.3: `app/anki.py`** — añadir helpers:

```python
def find_cards(query: str) -> list[int]:
    return invoke("findCards", query=query) or []


def cards_info(card_ids: list[int]) -> list[dict]:
    if not card_ids:
        return []
    return invoke("cardsInfo", cards=card_ids) or []
```

- [ ] **Step 12.4: `app/main.py`** — endpoint:

```python
@app.get("/api/stats")
def stats():
    """Métricas transparentes: minado local + estado real en Anki."""
    rows = CON.execute(
        "SELECT created_at FROM cards ORDER BY created_at").fetchall()
    by_month: dict[str, int] = {}
    for r in rows:
        k = r["created_at"][:7]
        by_month[k] = by_month.get(k, 0) + 1
    status_counts: dict[str, int] = {}
    for v in db.word_statuses(CON).values():
        status_counts[v] = status_counts.get(v, 0) + 1
    out = {"total_cards": len(rows), "by_month": by_month,
           "status_counts": status_counts,
           "sessions": len(db.list_sessions(CON)), "anki": None}
    if anki.is_up(_settings().get("anki_port")):
        try:
            deck = _settings()["deck"]
            ids = anki.find_cards(f'deck:"{deck}"')
            info = anki.cards_info(ids[:5000])
            reps = sum(c.get("reps", 0) for c in info)
            lapses = sum(c.get("lapses", 0) for c in info)
            out["anki"] = {
                "total": len(ids),
                "mature": sum(1 for c in info
                              if (c.get("interval") or 0) >= 21),
                "retention": round((1 - lapses / reps) * 100, 1) if reps else None,
                "due_today": len(anki.find_cards(f'deck:"{deck}" is:due')),
                "due_7d": len(anki.find_cards(f'deck:"{deck}" prop:due<8')),
                "due_30d": len(anki.find_cards(f'deck:"{deck}" prop:due<31')),
            }
        except Exception:
            pass
    return out
```

- [ ] **Step 12.5: Run** `pytest tests/ -q` → PASS. **Commit:** `git add app/anki.py app/main.py tests/test_api_v3.py && git commit -m "feat: endpoint /api/stats (local + AnkiConnect)"`

### Task 13: Vista de estadísticas 📊 (frontend)

**Files:** Modify: `static/index.html`, `static/app.js`, `static/style.css`

- [ ] **Step 13.1: HTML** — botón en `header .header-right` (antes del badge de Anki): `<div id="stats-btn" class="badge" title="Estadísticas">📊</div>`. Overlay al final de `<body>` (antes del script):

```html
<div id="stats-view" hidden>
  <div id="stats-box">
    <div class="stats-head"><h2>📊 Estadísticas</h2><button id="stats-close">✕</button></div>
    <div id="stats-body"></div>
  </div>
</div>
```

- [ ] **Step 13.2: JS** — al final de `app.js`:

```js
// ---------- estadísticas ----------
const ST_COLORS = { learning: "#f6a04d", known: "#4dc98a", ignored: "#6b6b7c", tracking: "#b07cff" };

function svgBars(data, color = "#7c5cff") {  // data: [[label, value], ...]
  const max = Math.max(1, ...data.map((d) => d[1]));
  const bw = 34, gap = 12, h = 120;
  const w = data.length * (bw + gap) + gap;
  const bars = data.map(([lab, v], i) => {
    const bh = Math.round((v / max) * (h - 34));
    const x = gap + i * (bw + gap), y = h - 18 - bh;
    return `<rect x="${x}" y="${y}" width="${bw}" height="${bh}" rx="6" fill="${color}"/>
      <text x="${x + bw / 2}" y="${y - 4}" text-anchor="middle" class="sv">${v}</text>
      <text x="${x + bw / 2}" y="${h - 4}" text-anchor="middle" class="sl">${lab}</text>`;
  }).join("");
  return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;max-width:${w * 1.4}px">${bars}</svg>`;
}

function svgDonut(counts) {  // {status: n}
  const entries = Object.entries(counts).filter(([, v]) => v > 0);
  const total = entries.reduce((a, [, v]) => a + v, 0);
  if (!total) return '<p class="dim">Sin palabras marcadas aún.</p>';
  let a0 = -Math.PI / 2, paths = "";
  for (const [st, v] of entries) {
    const a1 = a0 + (v / total) * Math.PI * 2;
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const p = (a) => `${60 + 46 * Math.cos(a)},${60 + 46 * Math.sin(a)}`;
    paths += `<path d="M ${p(a0)} A 46 46 0 ${large} 1 ${p(a1)}" stroke="${ST_COLORS[st] || "#888"}"
      stroke-width="16" fill="none"/>`;
    a0 = a1;
  }
  const legend = entries.map(([st, v]) =>
    `<span class="leg"><i style="background:${ST_COLORS[st] || "#888"}"></i>${ST_LABEL[st] || st}: ${v}</span>`).join("");
  return `<div class="donut-row"><svg viewBox="0 0 120 120" width="120">${paths}
    <text x="60" y="66" text-anchor="middle" class="sv">${total}</text></svg>
    <div class="legend">${legend}</div></div>`;
}

async function openStats() {
  $("stats-view").hidden = false;
  $("stats-body").innerHTML = '<p class="dim">Cargando…</p>';
  const s = await api("/api/stats");
  const months = Object.entries(s.by_month).slice(-8)
    .map(([m, v]) => [m.slice(2).replace("-", "/"), v]);
  let html = `
    <section><h3>Minado</h3>
      <p><b>${s.total_cards}</b> tarjetas minadas en <b>${s.sessions}</b> sesiones.</p>
      ${months.length ? svgBars(months) : '<p class="dim">Aún no has minado tarjetas.</p>'}
    </section>
    <section><h3>Palabras por estado</h3>
      <p class="dim" title="Estados que asignas al minar/marcar; se sincronizan con Anki (intervalo ≥ 21 días → conocida)">ⓘ cómo se calcula</p>
      ${svgDonut(s.status_counts)}
    </section>`;
  if (s.anki) {
    html += `
    <section><h3>En Anki (mazo de minado)</h3>
      <p><b>${s.anki.total}</b> tarjetas · <b>${s.anki.mature}</b> maduras (≥ 21 días)
      ${s.anki.retention !== null ? ` · retención <b>${s.anki.retention}%</b>` : ""}</p>
      <p class="dim" title="retención = 1 − fallos/repasos, sobre todas las tarjetas del mazo">ⓘ retención = 1 − fallos/repasos</p>
      ${svgBars([["hoy", s.anki.due_today], ["7 días", s.anki.due_7d], ["30 días", s.anki.due_30d]], "#f6a04d")}
      <p class="dim">Tarjetas que te tocará repasar (carga futura).</p>
    </section>`;
  } else {
    html += '<section><h3>En Anki</h3><p class="dim">Abre Anki para ver retención y pronóstico de repasos.</p></section>';
  }
  $("stats-body").innerHTML = html;
}
$("stats-btn").onclick = openStats;
$("stats-close").onclick = () => { $("stats-view").hidden = true; };
$("stats-view").onclick = (e) => { if (e.target === $("stats-view")) $("stats-view").hidden = true; };
```

- [ ] **Step 13.3: CSS:**

```css
#stats-view { position: fixed; inset: 0; background: rgba(0,0,0,.55);
  display: flex; align-items: center; justify-content: center; z-index: 60; }
#stats-box { background: var(--panel, #1c1b2e); border-radius: 20px;
  padding: 20px 24px; width: min(680px, 92vw); max-height: 86vh; overflow: auto; }
.stats-head { display: flex; justify-content: space-between; align-items: center; }
#stats-box section { margin: 14px 0; }
#stats-box .sv { fill: #fff; font-size: 12px; font-weight: 700; }
#stats-box .sl { fill: #9aa; font-size: 10px; }
.donut-row { display: flex; gap: 18px; align-items: center; }
.legend .leg { display: block; font-size: 13px; margin: 2px 0; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; }
#stats-btn { cursor: pointer; }
```

- [ ] **Step 13.4: Verificar** en navegador (con y sin Anki abierto). `Escape` también debería cerrar: añadir en el handler global de teclado, en la rama `Escape`: `$("stats-view").hidden = true;`.
- [ ] **Step 13.5: Commit.** `git add static/ && git commit -m "feat: panel de estadisticas con graficos SVG"`

### Task 14: App de escritorio (pywebview + CatalàMiner.app)

**Files:** Create: `app/desktop.py`, `make-app.sh` · Modify: `pyproject.toml`, `install.sh`, `README.md`

- [ ] **Step 14.1: Dependencia.** En `pyproject.toml` añadir `"pywebview>=5.0",` a `dependencies` y subir `version` a `"0.6.0"`. Instalar: `uv pip install -e . --python .venv/bin/python` (o `uv sync` si el repo usa lockfile — usar el mismo mecanismo que `install.sh`).

- [ ] **Step 14.2: `app/desktop.py`:**

```python
"""CatalàMiner como app de escritorio: uvicorn en un hilo + WKWebView."""
import socket
import threading
import time

from . import config


def _serve():
    import uvicorn
    from .main import app
    uvicorn.run(app, host="127.0.0.1", port=config.PORT, log_level="warning")


def _wait_port(port: int, secs: float = 20.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < secs:
        with socket.socket() as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def main():
    import webview
    threading.Thread(target=_serve, daemon=True).start()
    _wait_port(config.PORT)
    webview.create_window("CatalàMiner", f"http://127.0.0.1:{config.PORT}",
                          width=1280, height=860, min_size=(980, 640))
    webview.start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 14.3: Probar:** `.venv/bin/python -m app.desktop` → debe abrir ventana nativa con la app (si ya hay un servidor corriendo en 8977, pararlo antes; `_wait_port` encontraría el puerto ocupado y la ventana cargaría igualmente el servidor viejo — aceptable en dev pero para la prueba real, matar el uvicorn previo).

- [ ] **Step 14.4: `make-app.sh`:**

```bash
#!/bin/bash
# Genera ~/Applications/CatalàMiner.app apuntando a este checkout.
set -e
cd "$(dirname "$0")"
REPO="$(pwd)"
APP="$HOME/Applications/CatalàMiner.app"
mkdir -p "$APP/Contents/MacOS"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>CatalàMiner</string>
  <key>CFBundleDisplayName</key><string>CatalàMiner</string>
  <key>CFBundleIdentifier</key><string>cat.catalaminer.app</string>
  <key>CFBundleVersion</key><string>0.6.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST

cat > "$APP/Contents/MacOS/launcher" <<LAUNCH
#!/bin/bash
cd "$REPO"
exec "$REPO/.venv/bin/python" -m app.desktop
LAUNCH
chmod +x "$APP/Contents/MacOS/launcher"
echo "✅ Creada $APP — ábrela desde Launchpad o Spotlight."
```

`chmod +x make-app.sh`.

- [ ] **Step 14.5: `install.sh`** — añadir junto al brew de ffmpeg: `brew list espeak-ng >/dev/null 2>&1 || brew install espeak-ng || true` (IPA opcional; no romper la instalación si falla) y al final una línea que invoque `./make-app.sh` (o documentarlo). **README.md:** sección «App de escritorio»: `./make-app.sh` crea `CatalàMiner.app`; `./run.sh` sigue siendo el modo navegador; espeak-ng habilita la pronunciación IPA.
- [ ] **Step 14.6: Probar `make-app.sh`** y abrir la .app (con `open "$HOME/Applications/CatalàMiner.app"`). Verificar que carga y reproduce.
- [ ] **Step 14.7: Commit.** `git add app/desktop.py make-app.sh pyproject.toml install.sh README.md && git commit -m "feat: app de escritorio macOS (pywebview + bundle .app)"`

### Task 15: Versión, verificación final y merge

**Files:** Modify: `static/index.html`, `README.md`

- [ ] **Step 15.1:** Bump de cache-busting en `index.html`: `style.css?v=0.6.0` y `app.js?v=0.6.0`.
- [ ] **Step 15.2:** Suite completa: `.venv/bin/python -m pytest tests/ -q` → verde.
- [ ] **Step 15.3:** **Criterios de aceptación del spec** (§9) uno a uno con el servidor levantado: lookup de «Ets» correcto (curl), Q/⇧Q, A/D en huecos, expresión multi-palabra, stats con/sin Anki, `CatalàMiner.app`.
- [ ] **Step 15.4:** Commit final + merge a main como en versiones previas:

```bash
git add -A && git commit -m "feat: v0.6.0"   # si queda algo suelto
git checkout main && git merge --no-ff feature/v060-mineria-fluida -m "Merge feature/v060-mineria-fluida: v0.6.0"
```

---

## Notas para el ejecutor

- El servidor de desarrollo puede estar corriendo (uvicorn en :8977); **reiniciarlo tras cambios de backend** para probar (`pkill -f "uvicorn app.main:app"` + relanzar).
- La primera petición que toque `forms.py` descargará 37 MB y construirá `forms.sqlite` (~segundos). En tests está bloqueado por el fixture de `conftest.py`.
- `_correct` puede cambiar lemas que ya tenían estado: los estados antiguos con lemas erróneos quedan huérfanos (aceptado en spec §2.3).
- spaCy `ca_core_news_sm` puede no estar en el entorno de CI/tests — `tokenize()` ya degrada a `naive_tokenize`, los tests no deben asumir POS de spaCy.

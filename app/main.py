"""CatalàMiner — FastAPI backend + static frontend."""
import json
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import (anki, config, db, dictionary, forms, ipa, jobs, media, nlp,
               subs, translate)

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


def _settings() -> dict:
    s = {"deck": "Català::Mining", "anki_port": None}
    if SETTINGS_PATH.exists():
        s.update(json.loads(SETTINGS_PATH.read_text()))
    return s


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


def _session_meta(row: dict, statuses: dict) -> dict:
    """Thumbnail (lazy) + comprehension stats for the home cards."""
    sid = row["id"]
    thumb = config.MEDIA_DIR / f"thumb-{sid}.jpg"
    if not thumb.exists():
        full = db.get_session(CON, sid)
        try:
            media.snapshot(full["media_path"],
                           max(1.0, (full["duration_secs"] or 10) * 0.12),
                           str(thumb))
        except Exception:
            pass
    row["thumb"] = f"/media/thumb-{sid}.jpg" if thumb.exists() else None
    full = db.get_session(CON, sid)
    try:
        segs = json.loads(full["transcript_json"])
    except Exception:
        segs = []
    total = known = 0
    new_lemmas = set()
    for seg in segs:
        for t in seg.get("tokens", []):
            if t.get("is_word") and t.get("lemma"):
                st = statuses.get(t["lemma"], "unknown")
                if st == "ignored":
                    continue
                total += 1
                if st == "known":
                    known += 1
                elif st == "unknown":
                    new_lemmas.add(t["lemma"])
    row["comp_pct"] = round(known / total * 100) if total else None
    row["new_words"] = len(new_lemmas) if total else None
    return row


@app.get("/api/sessions")
def sessions():
    statuses = db.word_statuses(CON)
    return [_session_meta(r, statuses) for r in db.list_sessions(CON)]


@app.get("/api/sessions/{sid}")
def session_detail(sid: str):
    s = db.get_session(CON, sid)
    if not s:
        return JSONResponse({"error": "not found"}, status_code=404)
    s["transcript"] = json.loads(s.pop("transcript_json"))
    if s["transcript"] and (s.get("tok_version") or 0) < nlp.TOK_VERSION:
        for seg in s["transcript"]:
            seg["tokens"] = nlp.tokenize(seg["text"])
        db.update_transcript(CON, sid, json.dumps(s["transcript"]),
                             s["model_size"], s["srt_source"],
                             nlp.TOK_VERSION)
        s["tok_version"] = nlp.TOK_VERSION
    s["word_statuses"] = db.word_statuses(CON)
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
            from .transcribe import tokens_for_existing
            segs = subs.parse_subtitles(Path(info["subtitles"]).read_text())
            db.update_transcript(CON, sid,
                                 json.dumps(tokens_for_existing(segs)),
                                 "-", "youtube_subs", nlp.TOK_VERSION)
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
            db.update_transcript(CON, sid, json.dumps(segs), "-", "srt",
                                 nlp.TOK_VERSION)
        else:
            segs = T.transcribe(jid, s["media_path"], req.model,
                                s["duration_secs"] or 0)
            db.update_transcript(CON, sid, json.dumps(segs), req.model,
                                 "whisper", nlp.TOK_VERSION)
        return {"segments": len(segs)}

    return {"job_id": jobs.start(work, label="transcribe")}


@app.get("/api/jobs/{jid}")
def job_status(jid: str):
    j = jobs.get(jid)
    if j is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return j


@app.post("/api/sessions/{sid}/subtitles")
async def attach_subtitles(sid: str, file: UploadFile = File(...)):
    """User-provided .srt/.vtt — replaces the transcript, no Whisper needed."""
    s = db.get_session(CON, sid)
    if not s:
        return JSONResponse({"error": "not found"}, status_code=404)
    from .transcribe import tokens_for_existing
    text = (await file.read()).decode("utf-8", errors="replace")
    segs = tokens_for_existing(subs.parse_subtitles(text))
    if not segs:
        return JSONResponse({"error": "no s'han trobat subtítols al fitxer"},
                            status_code=400)
    db.update_transcript(CON, sid, json.dumps(segs), "-", "srt",
                         nlp.TOK_VERSION)
    return {"segments": len(segs)}


# ---------- word statuses (Migaku-style) ----------

class WordStatusReq(BaseModel):
    lemma: str
    status: str


@app.post("/api/words/status")
def set_word_status(req: WordStatusReq):
    if req.status not in db.WORD_STATUSES:
        return JSONResponse({"error": "bad status"}, status_code=400)
    db.set_word_status(CON, req.lemma, req.status)
    return {"ok": True, "lemma": req.lemma.strip().lower(),
            "status": req.status}


@app.post("/api/anki/sync-statuses")
def sync_statuses():
    """Migaku-style: Anki interval >= 21 days -> known, else learning."""
    if not anki.is_up(_settings().get("anki_port")):
        return {"synced": 0}
    try:
        anki.ensure_note_type()  # keeps card template in sync with app version
    except Exception:
        pass
    pairs = db.cards_with_notes(CON)
    intervals = anki.note_intervals([p["anki_note_id"] for p in pairs])
    statuses = db.word_statuses(CON)
    n = 0
    for p in pairs:
        iv = intervals.get(p["anki_note_id"])
        if iv is None:
            continue
        target = "known" if iv >= 21 else "learning"
        current = statuses.get(p["lema"])
        if current in ("ignored",):
            continue
        if current != target:
            db.set_word_status(CON, p["lema"], target)
            n += 1
    return {"synced": n}


# ---------- dictionary popup ----------

class LookupReq(BaseModel):
    selection: str
    sentence: str = ""
    session_id: str = ""
    segment_index: int = -1


@app.post("/api/lookup")
def lookup(req: LookupReq):
    """Instant word info for the Migaku-style popup (no media generated)."""
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


@app.post("/api/sessions/{sid}/segments/{idx}/translate")
def translate_segment(sid: str, idx: int):
    """Dual-subtitle line (Language Reactor style), cached in the transcript."""
    s = db.get_session(CON, sid)
    if not s:
        return JSONResponse({"error": "not found"}, status_code=404)
    segs = json.loads(s["transcript_json"])
    if not 0 <= idx < len(segs):
        return JSONResponse({"error": "bad index"}, status_code=400)
    return {"index": idx, "text_es": _segment_es(sid, idx)}


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
        # animated clip only makes sense for video sources
        if image_ok:
            media.animated_clip(s["media_path"], seg["start"], seg["end"],
                                str(config.MEDIA_DIR / clip_name))
        else:
            clip_ok = False
    except Exception:
        clip_ok = False

    lemma, pos = nlp.analyze_selection(req.selection, seg["text"])
    z = nlp.zipf(req.selection)
    senses = _dict().lookup(req.selection) or _dict().lookup(lemma)
    return {
        "paraula": req.selection,
        "lema": lemma, "pos": pos,
        "paraula_es": translate.translate(req.selection),
        "senses": [{"es": es, "pos": p} for es, p in senses[:8]],
        "frase": seg["text"],
        "frase_es": translate.sentence(seg["text"]),
        "freq_zipf": z, "freq_rank": nlp.freq_badge(z),
        "audio_file": audio_name if audio_ok else "",
        "image_file": image_name if image_ok else "",
        "clip_file": clip_name if clip_ok else "",
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
    if req.lema:
        db.mark_learning_if_new(CON, req.lema)
    sent = _flush()
    return {"card_id": cid, "sent_now": sent,
            "pending": len(db.pending_cards(CON)),
            "word_status": db.word_statuses(CON).get(req.lema.strip().lower())}


def _flush() -> int:
    if not anki.is_up(_settings().get("anki_port")):
        return 0
    deck = _settings()["deck"]
    n = 0
    for card in db.pending_cards(CON):
        try:
            note_id = anki.send_card(card, deck)
            db.mark_card_sent(CON, card["id"], note_id)
            n += 1
        except anki.AnkiError as e:
            if "duplicate" in str(e).lower():
                db.mark_card_duplicate(CON, card["id"])
                continue
            break
        except Exception:
            break
    return n


@app.post("/api/anki/flush")
def anki_flush():
    return {"sent": _flush(), "pending": len(db.pending_cards(CON))}


@app.get("/api/anki/status")
def anki_status():
    port, diag = anki.find_port(_settings().get("anki_port"))
    up = port is not None
    if up:
        reason = "ok"
    elif any(v == "squatted" for v in diag.values()):
        reason = "squatted"
    else:
        reason = "down"
    decks = anki.invoke("deckNames") if up else []
    return {"up": up, "port": port, "reason": reason, "diag": diag,
            "decks": decks, "deck": _settings()["deck"],
            "pending": len(db.pending_cards(CON))}


class DeckReq(BaseModel):
    deck: str


@app.post("/api/anki/deck")
def set_deck(req: DeckReq):
    s = _settings()
    s["deck"] = req.deck
    _save_settings(s)
    return {"ok": True}


class PortReq(BaseModel):
    port: int | None = None


@app.post("/api/anki/port")
def set_anki_port(req: PortReq):
    s = _settings()
    s["anki_port"] = req.port
    _save_settings(s)
    port, diag = anki.find_port(req.port)
    return {"ok": True, "port": port, "diag": diag}


# media (card audio previews) + frontend
app.mount("/media", StaticFiles(directory=str(config.MEDIA_DIR)), name="media")
app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")

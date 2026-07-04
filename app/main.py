"""CatalàMiner — FastAPI backend + static frontend."""
import json
import shutil
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
            from .transcribe import tokens_for_existing
            segs = subs.parse_subtitles(Path(info["subtitles"]).read_text())
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
    db.update_transcript(CON, sid, json.dumps(segs), "-", "srt")
    return {"segments": len(segs)}


# ---------- dictionary popup ----------

class LookupReq(BaseModel):
    selection: str
    sentence: str = ""


@app.post("/api/lookup")
def lookup(req: LookupReq):
    """Instant word info for the Migaku-style popup (no media generated)."""
    lemma, pos = nlp.analyze_selection(req.selection, req.sentence)
    z = nlp.zipf(req.selection)
    senses = _dict().lookup(req.selection) or _dict().lookup(lemma)
    return {
        "selection": req.selection,
        "lemma": lemma, "pos": pos,
        "zipf": z, "freq_rank": nlp.freq_badge(z),
        "senses": [{"es": es, "pos": p} for es, p in senses[:8]],
        "word_es": translate.translate(req.selection),
        "sentence_es": translate.translate(req.sentence) if req.sentence else "",
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
    if not segs[idx].get("text_es"):
        segs[idx]["text_es"] = translate.translate(segs[idx]["text"])
        db.update_transcript(CON, sid, json.dumps(segs),
                             s["model_size"], s["srt_source"])
    return {"index": idx, "text_es": segs[idx]["text_es"]}


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

    lemma, pos = nlp.analyze_selection(req.selection, seg["text"])
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

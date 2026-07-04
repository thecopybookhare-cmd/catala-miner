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
    jobs.set_progress(jid, 0.01, "Carregant model… (la primera vegada es descarrega)")
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

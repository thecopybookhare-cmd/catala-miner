"""Softcatalà cat->spa neural translation via CTranslate2 + SentencePiece."""
import re
from pathlib import Path

from . import config

_LEAD = re.compile(r"[^\W\d_]+", re.UNICODE)


def detok(pieces: list[str]) -> str:
    out = "".join(pieces).replace("▁", " ")
    return out.replace("<unk>", "").strip()


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
    from . import languages
    return config.MODELS_DIR / languages.profile()["translate_dir"]


def is_downloaded() -> bool:
    return model_dir().exists() and any(model_dir().glob("**/model.bin"))


def download():
    from huggingface_hub import snapshot_download
    from . import languages
    repo = languages.profile()["translate_repo"]
    if repo:
        snapshot_download(repo_id=repo, local_dir=str(model_dir()))


_ENGINES: dict = {}   # motor por idioma


def translate(text: str) -> str:
    """Translate →es. Returns '' on any failure (never raises to caller)."""
    from . import languages
    code = languages.active_code()
    if code not in _ENGINES:
        try:
            if not is_downloaded():
                download()
            _ENGINES[code] = _Engine(model_dir())
        except Exception:
            _ENGINES[code] = None
    eng = _ENGINES[code]
    if eng is None:
        return ""
    try:
        return eng.translate(text)
    except Exception:
        return ""


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

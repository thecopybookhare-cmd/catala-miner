"""Softcatalà cat->spa neural translation via CTranslate2 + SentencePiece."""
import re
from pathlib import Path

from . import config

_LEAD = re.compile(r"[^\W\d_]+", re.UNICODE)


def detok(pieces: list[str]) -> str:
    out = "".join(pieces).replace("▁", " ")
    return out.replace("<unk>", "").strip()


def _find_sp(model_dir: Path) -> Path:
    """SentencePiece del modelo. OPUS-MT trae source.spm/target.spm por
    separado (codificamos con el de origen); Softcatalà trae un único
    sp_m.model compartido."""
    src = next(iter(model_dir.glob("**/source.spm")), None)
    if src:
        return src
    for pat in ("**/*.model", "**/*.spm"):
        hits = sorted(model_dir.glob(pat))
        if hits:
            return hits[0]
    raise FileNotFoundError("no SentencePiece model in " + str(model_dir))


class _Engine:
    def __init__(self, model_dir: Path, eos: bool = False):
        import ctranslate2
        import sentencepiece as spm
        self.sp = spm.SentencePieceProcessor(model_file=str(_find_sp(model_dir)))
        self.eos = eos                        # OPUS-MT necesita </s> en la fuente
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
        if self.eos:
            toks = toks + ["</s>"]
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


_ENGINES: dict = {}       # motor por idioma
_FAILED_AT: dict = {}     # idioma -> timestamp del último intento fallido
_RETRY_SECS = 60.0        # un corte de red no debe matar el traductor para siempre


def translate(text: str) -> str:
    """Translate →es. Returns '' on any failure (never raises to caller)."""
    import time

    from . import languages
    code = languages.active_code()
    if _ENGINES.get(code) is None:
        last = _FAILED_AT.get(code, 0.0)
        if code in _ENGINES and time.time() - last < _RETRY_SECS:
            return ""                     # fallo reciente: esperar al reintento
        try:
            if not is_downloaded():
                download()
            eos = bool(languages.profile().get("translate_eos"))
            _ENGINES[code] = _Engine(model_dir(), eos=eos)
            _FAILED_AT.pop(code, None)
        except Exception:
            _ENGINES[code] = None
            _FAILED_AT[code] = time.time()
            return ""
    try:
        return _ENGINES[code].translate(text)
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

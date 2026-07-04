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

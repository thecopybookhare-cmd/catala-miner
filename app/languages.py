"""Perfiles de idioma: todo lo específico de un idioma vive aquí.

Un perfil es activable cuando tiene traductor validado (translate_repo).
El francés queda preparado pero inactivo hasta validar su traductor →es.
"""
import json

from . import config

PROFILES = {
    "ca": {
        "name": "Català",
        "wordfreq": "ca",
        "espeak": "ca",
        "spacy": "ca_core_news_sm",
        "whisper_models": config.WHISPER_MODELS,
        "default_whisper": config.DEFAULT_WHISPER,
        "translate_repo": config.TRANSLATE_REPO,
        "translate_dir": "translate-cat-spa",     # compat con instalaciones previas
        "bidix_url": config.BIDIX_URL,
        "bidix_file": "apertium-spa-cat.dix",     # compat
        "forms_url": config.FORMS_URL,
        "wikdict_url": ("https://kaikki.org/eswiktionary/Catal%C3%A1n/"
                        "kaikki.org-dictionary-Catal%C3%A1n.jsonl"),
        # voz neural Piper (ONNX) para la pronunciación; ruta en rhasspy/piper-voices
        "piper_voice": "ca/ca_ES/upc_ona/x_low/ca_ES-upc_ona-x_low.onnx",
    },
    "fr": {
        "name": "Français",
        "wordfreq": "fr",
        "espeak": "fr",
        "spacy": "fr_core_news_sm",
        "whisper_models": {"large-v3": "large-v3", "small": "small"},
        "default_whisper": "large-v3",
        # OPUS-MT fr→es convertido a CTranslate2 (Marian → necesita </s>).
        "translate_repo": "gaudi/opus-mt-fr-es-ctranslate2",
        "translate_eos": True,
        "translate_dir": "translate-fra-spa",
        "bidix_url": ("https://raw.githubusercontent.com/apertium/apertium-fr-es/"
                      "master/apertium-fra-spa.fra-spa.dix"),
        "bidix_file": "apertium-fra-spa.dix",
        "bidix_src": "l",                         # <l>=fra, <r>=spa (fra→spa)
        "forms_url": None,                        # spaCy fr_core_news_sm lematiza
        "wikdict_url": ("https://kaikki.org/eswiktionary/Franc%C3%A9s/"
                        "kaikki.org-dictionary-Franc%C3%A9s.jsonl"),
        "piper_voice": "fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx",
    },
}


def available(code: str) -> bool:
    p = PROFILES.get(code)
    return bool(p and p.get("translate_repo"))


def activable() -> list[str]:
    return [c for c in PROFILES if available(c)]


def active_code() -> str:
    try:
        s = json.loads((config.APP_DIR / "settings.json").read_text())
        code = s.get("language", "ca")
    except Exception:
        code = "ca"
    return code if available(code) else "ca"


def profile() -> dict:
    return PROFILES[active_code()]

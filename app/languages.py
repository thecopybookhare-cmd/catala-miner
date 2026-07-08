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
    },
    "fr": {
        "name": "Français",
        "wordfreq": "fr",
        "espeak": "fr",
        "spacy": "fr_core_news_sm",
        "whisper_models": {"large-v3": "large-v3", "small": "small"},
        "default_whisper": "large-v3",
        "translate_repo": None,                   # ← pendiente de validar → inactivo
        "translate_dir": "translate-fra-spa",
        "bidix_url": None,
        "bidix_file": "apertium-fra-spa.dix",
        "forms_url": None,
        "wikdict_url": ("https://kaikki.org/eswiktionary/Franc%C3%A9s/"
                        "kaikki.org-dictionary-Franc%C3%A9s.jsonl"),
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

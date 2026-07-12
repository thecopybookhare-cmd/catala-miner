import os
import sys
from pathlib import Path

PORT = 8977
# AnkiConnect default port is 8765, but on this machine another local
# service can squat it — we probe candidates and remember the winner.
ANKI_PORTS = (8765, 8766, 8767)


def default_app_dir(platform: str | None = None) -> Path:
    """Directorio de datos según el SO (multiplataforma). El de macOS se
    mantiene idéntico al histórico para no perder datos de instalaciones
    previas. CATALAMINER_DIR lo sobreescribe (tests / instalaciones portables)."""
    plat = platform or sys.platform
    if plat == "darwin":
        return Path.home() / "Library" / "Application Support" / "CatalaMiner"
    if plat.startswith("win"):
        base = Path(os.environ.get("APPDATA")
                    or Path.home() / "AppData" / "Roaming")
        return base / "CatalaMiner"
    base = Path(os.environ.get("XDG_DATA_HOME")
                or Path.home() / ".local" / "share")
    return base / "CatalaMiner"


APP_DIR = Path(os.environ.get("CATALAMINER_DIR") or default_app_dir())
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
# Bilingual dictionary: the repo ships it as .metadix (same XML structure
# with a few extra tags: <g>, <j/>, <v>) — we parse it directly.
BIDIX_URL = ("https://raw.githubusercontent.com/apertium/apertium-spa-cat/"
             "master/apertium-spa-cat.spa-cat.metadix")
# Diccionario de formas flexionadas de Softcatalà (LanguageTool):
# 1,3M líneas "forma lema ETIQUETA" — form->lemma para corregir a spaCy.
FORMS_URL = ("https://raw.githubusercontent.com/Softcatala/catalan-dict-tools/"
             "master/resultats/lt/diccionari.txt")

NOTE_TYPE = "CatalaMiner"
NOTE_FIELDS = ["Paraula", "ParaulaES", "Frase", "FraseES",
               "Audio", "Imatge", "Font", "Freq"]

#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
echo "== CatalàMiner install =="
command -v brew >/dev/null || { echo "Necessites Homebrew: https://brew.sh"; exit 1; }
brew list uv >/dev/null 2>&1 || brew install uv
command -v ffmpeg >/dev/null 2>&1 || brew install ffmpeg
# espeak-ng habilita la pronunciación IPA del popup (opcional)
brew list espeak-ng >/dev/null 2>&1 || brew install espeak-ng || true
[ -d .venv ] || uv venv --python 3.12 .venv
uv pip install -p .venv/bin/python -e . --group dev
echo "-- spaCy català --"
.venv/bin/python -m spacy download ca_core_news_sm || echo "AVÍS: spaCy ca no instal·lat (fallback regex)"
echo "-- Traductor Softcatalà + diccionari (descàrrega única) --"
.venv/bin/python - <<'PY'
from app import translate, dictionary, forms
if not translate.is_downloaded():
    translate.download()
print("traductor:", "ok" if translate.is_downloaded() else "ERROR")
d = dictionary.load()
print("diccionari:", "ok" if d.lookup("gos") else "ERROR")
print("formes:", "ok" if forms.lookup("ets") else "ERROR")  # baixa diccionari-lt
PY
echo "-- App d'escriptori --"
./make-app.sh || echo "AVÍS: no s'ha pogut crear CatalàMiner.app"
echo
echo "Fet! Arrenca amb ./run.sh (navegador) o obre CatalàMiner.app (finestra nativa)."
echo "Recorda: instal·la Anki (https://apps.ankiweb.net) + add-on AnkiConnect (codi 2055492159)."
echo "El model Whisper català (≈3 GB) es descarrega automàticament al primer ús."

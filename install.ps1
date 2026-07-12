# CatalàMiner — instalación en Windows (PowerShell).
# No requiere instalar Python ni ffmpeg a mano: uv aporta Python y
# static-ffmpeg descarga ffmpeg solo. Ejecuta con:
#   powershell -ExecutionPolicy Bypass -File install.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "== CatalàMiner install (Windows) =="

# 1) uv (gestor de Python; se instala solo si falta)
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "-- Instalando uv --"
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# 2) entorno + dependencias (uv instala Python 3.12 si hace falta)
if (-not (Test-Path .venv)) { uv venv --python 3.12 .venv }
uv pip install -p .venv\Scripts\python.exe -e .

# 3) modelos ligeros de primer uso
Write-Host "-- Modelo spaCy (catalán) --"
.\.venv\Scripts\python.exe -m spacy download ca_core_news_sm
Write-Host "-- Traductor Softcatalà + diccionarios (descarga única) --"
.\.venv\Scripts\python.exe -c "from app import translate, dictionary, forms; translate.is_downloaded() or translate.download(); print('traductor:', 'ok' if translate.is_downloaded() else 'ERROR'); print('diccionario:', 'ok' if dictionary.load().lookup('gos') else 'ERROR')"

Write-Host ""
Write-Host "¡Listo! Arranca con:  .\run.bat   (abre la app en tu navegador)"
Write-Host "Opcional: instala Anki (https://apps.ankiweb.net) + add-on AnkiConnect (2055492159)."
Write-Host "El modelo Whisper catalán (~3 GB) se descarga solo al transcribir por primera vez."

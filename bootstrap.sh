#!/bin/bash
# CatalàMiner — instalación de UN comando (macOS / Linux). Clona el repo y lo
# instala todo. Uso:
#   curl -LsSf https://raw.githubusercontent.com/thecopybookhare-cmd/catala-miner/main/bootstrap.sh | bash
# (requiere que el repo sea público; si es privado, clónalo tú y ejecuta ./install.sh)
set -euo pipefail

REPO="${CATALAMINER_REPO:-https://github.com/thecopybookhare-cmd/catala-miner.git}"
DEST="${CATALAMINER_HOME:-$HOME/CatalaMiner}"

echo "== CatalàMiner — instalación de un comando =="
if ! command -v git >/dev/null 2>&1; then
  echo "Necesitas 'git'. macOS: se instala con 'xcode-select --install'. Linux: 'sudo apt install git'." >&2
  exit 1
fi

if [ -d "$DEST/.git" ]; then
  echo "-- Actualizando copia en $DEST --"
  git -C "$DEST" pull --ff-only || echo "(no pude actualizar; sigo con lo que hay)"
else
  echo "-- Clonando en $DEST --"
  git clone --depth 1 "$REPO" "$DEST"
fi

cd "$DEST"
exec ./install.sh

#!/bin/bash
# Arranca LinguaMiner y abre la app en el navegador (macOS y Linux).
cd "$(dirname "$0")"
URL="http://localhost:8977"
if command -v open >/dev/null 2>&1; then OPEN=open        # macOS
elif command -v xdg-open >/dev/null 2>&1; then OPEN=xdg-open  # Linux
else OPEN=true; fi
( sleep 1.2 && "$OPEN" "$URL" >/dev/null 2>&1 ) &
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8977

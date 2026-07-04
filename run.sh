#!/bin/bash
cd "$(dirname "$0")"
( sleep 1.2 && open "http://localhost:8977" ) &
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8977

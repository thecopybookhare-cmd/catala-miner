@echo off
REM Arranca CatalaMiner y abre la app en el navegador (Windows).
cd /d "%~dp0"
start "" /b cmd /c "timeout /t 2 >nul & start http://localhost:8977"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8977

@echo off
REM ============================================================
REM  Landslide Guardian - Automatic Monitoring + Auto SOS
REM  Double-click this file to start the server and open the app.
REM ============================================================
cd /d "%~dp0"
echo Starting Landslide Guardian backend...

set "PY_EXE=.venv\Scripts\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=venv\Scripts\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"

echo Using Python: %PY_EXE%
echo Installing/verifying backend dependencies...
"%PY_EXE%" -m pip install -r backend\requirements.txt --quiet

echo Starting backend server at http://127.0.0.1:8000 ...
start "" http://127.0.0.1:8000/
"%PY_EXE%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

pause

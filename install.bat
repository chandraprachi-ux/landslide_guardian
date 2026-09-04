@echo off
REM ============================================================
REM  Landslide Guardian - First-time setup
REM  Double-click once to install dependencies and train the model.
REM ============================================================
cd /d "%~dp0"
echo Creating virtual environment...
python -m venv .venv

echo Installing dependencies (this can take a few minutes)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt

echo Training the ML model...
".venv\Scripts\python.exe" -m backend.ml.train_model

echo.
echo DONE. Now double-click start_server.bat to run.
pause

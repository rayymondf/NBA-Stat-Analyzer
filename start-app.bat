@echo off
rem NBA Stat Analyzer - double-click to start
cd /d "%~dp0"

if not exist "backend\venv\Scripts\python.exe" (
  echo Python environment not found. Run setup first: see README.md
  pause
  exit /b 1
)

echo Starting NBA Stat Analyzer at http://localhost:8000 ...
start "" http://localhost:8000
"backend\venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --port 8000
pause

@echo off
rem NBA Stat Analyzer - double-click to start
cd /d "%~dp0"

set "PYTHON=backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=backend\venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo Python environment not found. Run setup.ps1 first: see README.md
  pause
  exit /b 1
)

if not exist "frontend\dist\index.html" (
  echo Built frontend not found. Run setup.ps1 or npm run build in frontend.
  pause
  exit /b 1
)

echo Starting NBA Stat Analyzer at http://localhost:8000 ...
start "" http://localhost:8000
"%PYTHON%" -m uvicorn app.main:app --app-dir backend --port 8000
pause

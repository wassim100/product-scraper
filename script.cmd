@echo off
setlocal
cd /d "C:\Users\Wassim\OneDrive - ESPRIT\Desktop\Selenium"

REM Flags prod (run complet)
set "HEADLESS_MODE=true"
set "ENABLE_AI_CLEANING=true"
set "ENABLE_DB=true"
set "ENABLE_DEACTIVATE_MISSING=true"

REM Désactiver tout filtre/limite de test
set "MAX_PRODUCTS="
set "SCHEDULER_CATEGORIES="
set "SCHEDULER_SCRIPTS="
set "SCHEDULER_DEBUG="

REM Encodage Python
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM Résoudre Python (prend le venv si présent)
set "PYEXE=python"
if exist ".\.venv\Scripts\python.exe" set "PYEXE=.venv\Scripts\python.exe"

REM Lancer une passe complète (scheduler)
"%PYEXE%" ".\main.py" --mode schedule --manual-run
set "EXITCODE=%ERRORLEVEL%"
echo.
echo Exit code: %EXITCODE%
exit /b %EXITCODE%
@echo off
rem One-step local build: creates a venv, installs dependencies, builds dist\FloppyMounter.exe
rem Pass --onedir for a folder build.
setlocal
cd /d "%~dp0"
if not exist .venv python -m venv .venv || goto :err
call .venv\Scripts\activate.bat || goto :err
python -m pip install --upgrade pip || goto :err
pip install -r requirements.txt -r requirements-dev.txt || goto :err
python build.py %* || goto :err
echo.
echo Done. See the dist folder.
exit /b 0
:err
echo Build failed.
exit /b 1

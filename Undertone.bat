@echo off
cd /d "%~dp0"
rem The release zip ships its own Python; a git checkout uses .venv from install.bat.
if exist "python\pythonw.exe" (
    start "" "python\pythonw.exe" -m undertone
    exit /b 0
)
if not exist ".venv\Scripts\pythonw.exe" (
    echo Undertone isn't set up yet. Running install.bat first...
    call install.bat || exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m undertone

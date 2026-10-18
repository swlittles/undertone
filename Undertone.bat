@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Undertone isn't set up yet. Running install.bat first...
    call install.bat || exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m undertone

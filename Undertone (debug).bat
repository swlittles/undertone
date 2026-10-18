@echo off
rem Runs with a console window so errors are visible.
cd /d "%~dp0"
if exist "python\python.exe" (
    "python\python.exe" -m undertone
) else (
    ".venv\Scripts\python.exe" -m undertone
)
pause

@echo off
rem Runs with a console window so errors are visible.
cd /d "%~dp0"
".venv\Scripts\python.exe" -m undertone
pause

@echo off
setlocal
cd /d "%~dp0"
echo Getting the latest version...
git pull --ff-only || goto fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet || goto fail
echo Up to date.
pause
exit /b 0

:fail
echo Update failed. Scroll up for the error.
pause
exit /b 1

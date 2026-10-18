@echo off
setlocal
cd /d "%~dp0"
title Undertone setup
echo.
echo  Undertone setup
echo  ===============
echo.

py -3.12 -c "import sys" >nul 2>nul
if errorlevel 1 goto nopython

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python environment...
    py -3.12 -m venv .venv || goto fail
)
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet || goto fail

where nvidia-smi >nul 2>nul
if errorlevel 1 (
    echo No NVIDIA GPU found: installing the CPU version of PyTorch.
    echo AI voice will be slow without an NVIDIA GPU. Deep voice works fine.
    set "TORCH_INDEX=https://download.pytorch.org/whl/cpu"
) else (
    echo NVIDIA GPU found: installing PyTorch with CUDA. This is a big download, about 3 GB.
    set "TORCH_INDEX=https://download.pytorch.org/whl/cu128"
)
".venv\Scripts\python.exe" -m pip install torch==2.11.0 torchaudio==2.11.0 --index-url %TORCH_INDEX% || goto fail

echo Installing the rest...
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto fail

echo Creating a desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Undertone.lnk');" ^
  "$s.TargetPath = '%CD%\.venv\Scripts\pythonw.exe';" ^
  "$s.Arguments = '-m undertone';" ^
  "$s.WorkingDirectory = '%CD%';" ^
  "$s.IconLocation = '%CD%\undertone\assets\undertone.ico';" ^
  "$s.Save()"

echo.
echo  Done. Start Undertone from the desktop shortcut or Undertone.bat.
echo.
echo  To let Discord and games hear the changed voice, install the free VB-Cable:
echo  https://vb-audio.com/Cable/
echo.
pause
exit /b 0

:nopython
echo Python 3.12 is not installed.
echo.
echo Installing it with winget...
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo.
    echo Couldn't install automatically. Download Python 3.12 from https://www.python.org/downloads/
    echo then run install.bat again.
) else (
    echo.
    echo Python installed. Close this window and run install.bat again.
)
pause
exit /b 1

:fail
echo.
echo Setup failed. Scroll up for the error, or send it to whoever is helping you.
pause
exit /b 1

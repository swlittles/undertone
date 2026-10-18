## Install on Windows

1. Download **Undertone-…-windows.zip** below.
2. Right-click it, choose **Extract All…**, and put the folder anywhere (e.g. Documents).
   Don't run it from inside the zip.
3. Open the folder and double-click **Undertone.bat**. If Windows SmartScreen warns
   you, click **More info → Run anyway**. The first launch puts an **Undertone**
   shortcut on your desktop.
4. Install the free [VB-Cable](https://vb-audio.com/Cable/) and reboot. In Undertone, send the voice to
   **CABLE Input**; in Discord or your game, pick **CABLE Output** as the microphone.

Deep voice works straight away. AI voice asks for a one-time download the first time
(about 3.2 GB on an NVIDIA GPU) and needs an RVC voice model you add yourself.

## Updating

Download the new zip, extract it, and run **Undertone.bat** from the new folder. Your
settings, voices and downloads are kept in `%LOCALAPPDATA%\Undertone` and
`%APPDATA%\Undertone`, and the desktop shortcut moves to the new version, so you can
delete the old folder.

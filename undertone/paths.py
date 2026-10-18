"""Where Undertone keeps its code, downloaded models, voices and settings."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"  # Applio's RVC code (see vendor/README.md)
BASE_MODELS = VENDOR / "rvc" / "models"  # Applio resolves these relative to VENDOR
VOICES = ROOT / "voices"  # drop .pth / .index voice files here


def data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    path = base / "Undertone"
    path.mkdir(parents=True, exist_ok=True)
    return path


SETTINGS_FILE = data_dir() / "settings.json"

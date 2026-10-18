"""Where Undertone keeps its code, downloaded models, voices and settings.

Everything the user downloads or adds lives outside the app folder, so a new
version can be unzipped anywhere without losing voices, models or settings.
"""

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"  # Applio's RVC code (see vendor/README.md)
# The Windows release ships its own Python in ROOT/python; source checkouts use a venv.
BUNDLED = (ROOT / "python" / "python.exe").is_file()


def _user_dir(env: str, windows_fallback: str) -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get(env) or Path.home() / "AppData" / windows_fallback)
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    path = base / "Undertone"
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    """Settings and logs (roams with a Windows profile)."""
    return _user_dir("APPDATA", "Roaming")


def local_dir() -> Path:
    """Big downloads: the AI engine, shared models and voices (never roams)."""
    return _user_dir("LOCALAPPDATA", "Local")


SETTINGS_FILE = data_dir() / "settings.json"
# Applio opens its models as rvc/models/... relative to the working directory,
# so the AI engine runs with ENGINE_DIR as its working directory.
ENGINE_DIR = local_dir() / "engine"
BASE_MODELS = ENGINE_DIR / "rvc" / "models"
VOICES = local_dir() / "voices"  # .pth / .index voice files
RUNTIME = local_dir() / "rt"  # PyTorch for the Windows release; kept short for MAX_PATH


def migrate_old_locations() -> None:
    """Versions before 0.2 kept voices and models inside the app folder."""
    moves = [(ROOT / "voices", VOICES), (VENDOR / "rvc" / "models", BASE_MODELS)]
    for old, new in moves:
        if not old.is_dir():
            continue
        for item in old.rglob("*"):
            if item.is_file() and item.name != "README.md":
                dest = new / item.relative_to(old)
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(item), str(dest))
        if old.name == "models":
            shutil.rmtree(old, ignore_errors=True)

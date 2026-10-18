"""Desktop shortcut for the Windows release, kept pointing at the newest copy."""

import subprocess
import sys

from .paths import BUNDLED, ROOT
from .settings import Settings


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def ensure_desktop_shortcut(s: Settings) -> None:
    """Create the shortcut on first run, and move it when a new version runs from another folder."""
    if sys.platform != "win32" or not BUNDLED or s.shortcut_root == str(ROOT):
        return
    script = "; ".join([
        "$p = [Environment]::GetFolderPath('Desktop') + '\\Undertone.lnk'",
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($p)",
        f"$s.TargetPath = {_ps_quote(str(ROOT / 'python' / 'pythonw.exe'))}",
        "$s.Arguments = '-m undertone'",
        f"$s.WorkingDirectory = {_ps_quote(str(ROOT))}",
        f"$s.IconLocation = {_ps_quote(str(ROOT / 'undertone' / 'assets' / 'undertone.ico'))}",
        "$s.Save()",
    ])
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=True, timeout=20, capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as e:
        print(f"Couldn't create the desktop shortcut: {e}", file=sys.stderr)
        return
    s.shortcut_root = str(ROOT)
    s.save()

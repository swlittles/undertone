"""Updates for the Windows release from GitHub Releases.

The new zip is downloaded and unpacked into ROOT/_update while the app runs.
Moving it into place has to wait until the app's Python has exited, so a small
PowerShell script (assets/apply_update.ps1) does that after Undertone closes:
it swaps the app's own files, rolls back if anything is locked, and can start
the new version. Settings, voices and downloads live outside ROOT and are untouched.

Source checkouts update with git (update.bat) and never see any of this.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import __version__
from .paths import BUNDLED, ROOT, data_dir, local_dir

REPO = "swlittles/undertone"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
STAGING = ROOT / "_update"
_ASSET = re.compile(r"^Undertone-.+-windows\.zip$")
_READY = "update-ready.txt"  # written last; holds the staged version

Progress = Callable[[float, str], None]


@dataclass
class Release:
    version: str
    url: str  # the zip
    size: int
    sha256: str  # empty if GitHub didn't give one
    page: str


def supported() -> bool:
    return sys.platform == "win32" and BUNDLED


def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", v)[:3])


def is_newer(version: str, than: str = __version__) -> bool:
    return parse_version(version) > parse_version(than)


def latest() -> Optional[Release]:
    """The newest published release with a Windows zip, or None."""
    import requests

    headers = {"Accept": "application/vnd.github+json"}
    if token := os.environ.get("UNDERTONE_GITHUB_TOKEN"):  # only for CI, which shares rate limits
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(LATEST_URL, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()
    for asset in data.get("assets", []):
        if _ASSET.match(asset.get("name", "")):
            digest = asset.get("digest") or ""
            return Release(
                version=data["tag_name"].lstrip("v"),
                url=asset["browser_download_url"],
                size=asset.get("size", 0),
                sha256=digest.split(":", 1)[1] if digest.startswith("sha256:") else "",
                page=data.get("html_url", ""),
            )
    return None


def check() -> Optional[Release]:
    """A release newer than this one, or None."""
    rel = latest()
    return rel if rel and is_newer(rel.version) else None


def staged_version() -> str:
    try:
        return (STAGING / _READY).read_text().strip()
    except OSError:
        return ""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download(rel: Release, progress: Progress) -> None:
    """Download and unpack rel into STAGING. Takes a minute or two."""
    from .runtime import _download

    downloads = local_dir() / "updates"
    downloads.mkdir(parents=True, exist_ok=True)
    zip_path = downloads / rel.url.rsplit("/", 1)[1]
    if not zip_path.exists():
        _download(rel.url, zip_path, lambda f, label: progress(0.7 * f, label), f"Downloading {rel.version}")
    if rel.sha256 and _sha256(zip_path) != rel.sha256:
        zip_path.unlink()
        raise RuntimeError("the download was corrupted; try again")

    shutil.rmtree(STAGING, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        members = z.infolist()
        for i, m in enumerate(members):
            z.extract(m, STAGING)
            if i % 200 == 0:
                progress(0.7 + 0.3 * i / len(members), "Unpacking")
    if not (STAGING / "python" / "pythonw.exe").is_file() or not (STAGING / "undertone").is_dir():
        shutil.rmtree(STAGING, ignore_errors=True)
        raise RuntimeError("the release zip doesn't look like Undertone")
    (STAGING / _READY).write_text(rel.version)
    shutil.rmtree(downloads, ignore_errors=True)
    progress(1.0, "Ready")


def apply(restart: bool, pid: int | None = None) -> None:
    """Start the script that swaps in the staged version once process pid exits.

    Call right before the app quits.
    """
    (STAGING / _READY).unlink()  # the swap moves everything in STAGING into ROOT
    script = Path(tempfile.gettempdir()) / "undertone-apply-update.ps1"
    shutil.copyfile(ROOT / "undertone" / "assets" / "apply_update.ps1", script)
    args = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
        "-File", str(script),
        "-AppPid", str(pid or os.getpid()),
        "-Root", str(ROOT),
        "-Staging", str(STAGING),
        "-Log", str(data_dir() / "update.log"),
    ]
    if restart:
        args.append("-Restart")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(args, cwd=tempfile.gettempdir(), creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def clean_leftovers() -> None:
    """Remove what an earlier update left behind: old files and unfinished downloads."""
    if not supported():
        return
    for old in ROOT.glob("_old_*"):
        shutil.rmtree(old, ignore_errors=True)
    staged = staged_version()
    if not staged or not is_newer(staged):
        shutil.rmtree(STAGING, ignore_errors=True)

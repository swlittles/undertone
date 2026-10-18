"""PyTorch for the Windows release.

The CUDA build of PyTorch is about 2.7 GB, too big to ship in the release zip,
so the app downloads it the first time AI voice is set up. The wheel is
unpacked into RUNTIME (outside the app folder, so it survives updates) and put
on sys.path at startup. Its dependencies already ship in the release.

Source checkouts install PyTorch into their venv instead, and this module
leaves them alone.

    python -m undertone.runtime install [--flavor cpu|cu128]
"""

import importlib
import importlib.util
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Callable

from .paths import RUNTIME

TORCH_VERSION = "2.11.0"
_INDEX = "https://download.pytorch.org/whl"
_PACKAGES = ("torch", "torchaudio")
# Headers, CMake files and link-time .lib files are only for compiling
# extensions. Skipping them saves ~10k files and the deepest paths.
_SKIP_PREFIXES = ("torch/include/", "torch/share/")
_MARKER = "installed.json"

Progress = Callable[[float, str], None]


def flavor_dir(flavor: str) -> Path:
    return RUNTIME / flavor


def installed_flavor() -> str | None:
    """Flavor of a complete install in RUNTIME, preferring CUDA."""
    for flavor in ("cu128", "cpu"):
        try:
            info = json.loads((flavor_dir(flavor) / _MARKER).read_text())
        except (OSError, ValueError):
            continue
        if info.get("torch") == TORCH_VERSION:
            return flavor
    return None


def activate() -> None:
    """Make an installed runtime importable. Call before anything imports torch."""
    flavor = installed_flavor()
    if flavor:
        path = str(flavor_dir(flavor))
        if path not in sys.path:
            sys.path.insert(0, path)
            importlib.invalidate_caches()


def torch_ready() -> bool:
    return importlib.util.find_spec("torch") is not None


def has_nvidia_gpu() -> bool:
    if shutil.which("nvidia-smi"):
        return True
    return Path(r"C:\Windows\System32\nvidia-smi.exe").is_file()


def recommended_flavor() -> str:
    return "cu128" if has_nvidia_gpu() else "cpu"


def _wheel_urls(flavor: str) -> list[str]:
    tag = "cp312-cp312-win_amd64"
    return [f"{_INDEX}/{flavor}/{pkg}-{TORCH_VERSION}%2B{flavor}-{tag}.whl" for pkg in _PACKAGES]


def download_size_mb(flavor: str) -> int:
    return {"cu128": 2630, "cpu": 110}[flavor]


def _download(url: str, dest: Path, progress: Progress, label: str) -> None:
    import requests

    part = dest.with_suffix(".part")
    have = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    with requests.get(url, stream=True, timeout=30, headers=headers) as r:
        if r.status_code == 416:  # already complete
            part.replace(dest)
            return
        r.raise_for_status()
        if r.status_code != 206:
            have = 0
        total = have + int(r.headers.get("Content-Length", 0))
        with open(part, "ab" if have else "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                have += len(chunk)
                if total:
                    progress(have / total, label)
    part.replace(dest)


def _unpack(wheel: Path, target: Path, progress: Progress, label: str) -> None:
    with zipfile.ZipFile(wheel) as z:
        members = [m for m in z.infolist() if not m.is_dir()]
        for i, m in enumerate(members):
            name = m.filename
            if name.startswith(_SKIP_PREFIXES) or name.endswith(".lib"):
                continue
            if ".data/" in name:
                # purelib/platlib land in the target; scripts and headers aren't needed.
                parts = name.split("/")
                if len(parts) < 3 or parts[1] not in ("purelib", "platlib"):
                    continue
                name = "/".join(parts[2:])
            dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(m) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out, 1 << 20)
            if i % 200 == 0:
                progress(i / len(members), label)


def install(flavor: str, progress: Progress) -> None:
    """Download and unpack PyTorch. progress(fraction, label) is called often."""
    urls = _wheel_urls(flavor)
    downloads = RUNTIME / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    final = flavor_dir(flavor)
    staging = RUNTIME / f"{flavor}.new"
    shutil.rmtree(staging, ignore_errors=True)

    # Weights for the progress bar: the big torch download dominates.
    wheels = []
    for i, url in enumerate(urls):
        wheel = downloads / url.rsplit("/", 1)[1].replace("%2B", "+")
        if not wheel.exists():
            lo, hi = (0.0, 0.8) if i == 0 else (0.8, 0.82)
            what = "AI engine" if i == 0 else "audio support"
            _download(url, wheel, lambda f, _l, lo=lo, hi=hi: progress(lo + (hi - lo) * f, _l), f"Downloading {what}")
        wheels.append(wheel)
    for i, wheel in enumerate(wheels):
        lo, hi = (0.82, 0.99) if i == 0 else (0.99, 1.0)
        _unpack(wheel, staging, lambda f, _l, lo=lo, hi=hi: progress(lo + (hi - lo) * f, _l), "Unpacking AI engine")

    (staging / _MARKER).write_text(json.dumps({"torch": TORCH_VERSION, "flavor": flavor}))
    shutil.rmtree(final, ignore_errors=True)
    staging.replace(final)
    shutil.rmtree(downloads, ignore_errors=True)
    for other in RUNTIME.iterdir():  # older versions or the other flavor
        if other.is_dir() and other != final:
            shutil.rmtree(other, ignore_errors=True)
    activate()
    progress(1.0, "AI engine ready")


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m undertone.runtime")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("install", help="download PyTorch into the runtime folder")
    p.add_argument("--flavor", choices=["cpu", "cu128"], default=recommended_flavor())
    args = parser.parse_args(argv)

    last = [-1]

    def show(frac: float, label: str) -> None:
        pct = int(frac * 100)
        if pct != last[0]:
            last[0] = pct
            print(f"{label}: {pct}%", flush=True)

    install(args.flavor, show)
    print(f"Installed PyTorch {TORCH_VERSION} ({args.flavor}) in {flavor_dir(args.flavor)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

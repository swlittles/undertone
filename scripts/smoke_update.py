"""Checks the updater end to end on a copy of a release build: downloads the
latest published release, stages it, and starts the swap. test_windows.ps1
waits for the swap and checks the result after this process exits."""

import tempfile
from pathlib import Path

from undertone import paths, updater

assert paths.BUNDLED and updater.supported(), f"not running a bundled copy: {paths.ROOT}"
rel = updater.latest()
assert rel, "no published release with a Windows zip"
print(f"Latest release {rel.version}: {rel.size / 1e6:.0f} MB, sha256 {'given' if rel.sha256 else 'missing'}")
updater.download(rel, lambda f, label: None)
assert updater.staged_version() == rel.version
(paths.ROOT / "my-notes.txt").write_text("not part of the app")  # must survive the swap
Path(tempfile.gettempdir(), "undertone-expected-version.txt").write_text(rel.version)
updater.apply(restart=False)
print("Swap started; exiting so it can run")

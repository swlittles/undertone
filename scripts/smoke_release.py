"""Checks a release build works end to end: run with its bundled Python after
`python -m undertone.runtime install --flavor cpu`."""

import sys
import time

from undertone import paths, runtime

assert paths.BUNDLED, f"not running the bundled app: {paths.ROOT}"
assert not runtime.torch_ready(), "PyTorch should come from the runtime folder, not the bundle"
runtime.activate()
assert runtime.installed_flavor() == "cpu"

import torch  # noqa: E402

assert str(paths.RUNTIME) in torch.__file__, torch.__file__
from undertone.voices import ai  # noqa: E402

ai._import_applio()
print("AI engine imports; runs on", ai.compute_device())

from PySide6.QtWidgets import QApplication  # noqa: E402

from undertone.ui.window import MainWindow  # noqa: E402

app = QApplication(sys.argv)
win = MainWindow(app)
win.show()
end = time.time() + 2
while time.time() < end:
    app.processEvents()
    time.sleep(0.02)
assert win.base_banner.isVisibleTo(win), "should offer the shared model download"
win.close()
print("GUI starts")

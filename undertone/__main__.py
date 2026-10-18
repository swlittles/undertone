"""Entry point: python -m undertone"""

import os
import sys


def _log_to_file():
    """pythonw has no console; keep output (and crashes) in a log file instead."""
    from .paths import data_dir

    if sys.stdout is None or sys.stderr is None or os.environ.get("UNDERTONE_LOG"):
        log = open(data_dir() / "undertone.log", "w", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log


def main() -> int:
    _log_to_file()
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Undertone.VoiceChanger")

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .paths import ROOT
    from .ui.window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Undertone")
    app.setWindowIcon(QIcon(str(ROOT / "undertone" / "assets" / "icon.png")))
    win = MainWindow(app)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

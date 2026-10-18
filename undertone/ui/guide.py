"""Setup guide: what to install and click to get the changed voice into Discord and games.

Opens by itself on first launch and from the Setup button in the header.
"""

import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..audio import engine as audio
from ..paths import data_dir
from . import theme
from .widgets import Card

VC_REDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"

if sys.platform == "darwin":
    CABLE_NAME, CABLE_URL = "BlackHole", "https://existential.audio/blackhole/"
    CABLE_IN = CABLE_OUT = "BlackHole 2ch"
    CABLE_INSTALL = "Download the free <b>BlackHole 2ch</b> installer and run it."
else:
    CABLE_NAME, CABLE_URL = "VB-Cable", "https://vb-audio.com/Cable/"
    CABLE_IN, CABLE_OUT = "CABLE Input (VB-Audio Virtual Cable)", "CABLE Output (VB-Audio Virtual Cable)"
    CABLE_INSTALL = ("Download the free <b>VB-Cable</b> zip and extract it. Right-click "
                     "<b>VBCABLE_Setup_x64.exe</b>, choose <b>Run as administrator</b>, click "
                     "<b>Install Driver</b>, then <b>restart your PC</b>.")


def _steps() -> list[tuple[str, str]]:
    """(title, rich text) for each step."""
    a = f'style="color:{theme.current().accent}; text-decoration:none;"'
    if sys.platform == "darwin":
        game_mic = ""
        problems_extra = ""
    else:
        game_mic = ("<p><b>Games that only use the Windows mic:</b> Settings → System → Sound → "
                    f"Input, choose <b>{CABLE_OUT}</b>.</p>"
                    f"<p>Don't make <b>{CABLE_IN}</b> your default <i>output</i> in Windows, or "
                    "every sound on your PC goes into your mic.</p>")
        problems_extra = (f"<li><b>“DLL load failed” when starting AI voice:</b> install the "
                          f'<a {a} href="{VC_REDIST_URL}">Microsoft Visual C++ Redistributable</a>, '
                          "then restart Undertone.</li>"
                          "<li><b>Anything else:</b> run <b>Undertone (debug).bat</b> from the app "
                          "folder to see the error, or open the log below.</li>")
    return [
        (f"Install {CABLE_NAME}",
         "<p>Undertone sends the changed voice into a virtual microphone that Discord and games "
         f"listen to. {CABLE_INSTALL}</p>"),
        ("Pick your devices in Undertone",
         "<ul>"
         "<li><b>Microphone:</b> your real mic. Talk and the meter under it should move.</li>"
         f"<li><b>Send changed voice to:</b> <b>{CABLE_IN}</b>.</li>"
         "<li><b>Headphones:</b> what you listen on. Used by <b>Test my voice</b> and "
         "<b>Hear myself</b>.</li>"
         "</ul>"
         "<p>Leave <b>Hear myself</b> off while you play; hearing your own delayed voice is "
         "distracting.</p>"),
        ("Set the mic in Discord and your games",
         "<p><b>Discord:</b> User Settings → Voice &amp; Video → <b>Input Device</b>, choose "
         f"<b>{CABLE_OUT}</b>. If the voice sounds muffled or cuts out, set <b>Noise "
         "Suppression</b> to None.</p>"
         "<p><b>Games:</b> in the game's audio or voice chat settings, choose "
         f"<b>{CABLE_OUT}</b> as the microphone.</p>"
         + game_mic),
        ("Choose a voice and press Start",
         "<p><b>Deep voice</b> works right away. Pick a preset (<b>Deeper</b> is a good start) "
         "and press <b>Start</b>.</p>"
         "<p><b>AI voice</b> needs a one-time download: click <b>Download</b> in the AI voice "
         "panel (a few GB; an NVIDIA graphics card is strongly recommended). Then click "
         "<b>Add voice…</b>, pick an RVC v2 voice model (<b>.pth</b>, or a <b>.zip</b> with "
         "one inside) and press <b>Start</b>. The first load takes a few seconds.</p>"),
        ("Test it",
         "<p>While live, click <b>Record</b> under <b>Test my voice</b> and talk for a few "
         "seconds the way you do in game. Then compare <b>Original</b> with <b>Changed</b>, "
         "which is exactly what others hear.</p>"
         "<p><b>Real voice</b> next to Start sends your normal voice until you click it "
         "again.</p>"),
        ("If something isn't working",
         "<ul>"
         f"<li><b>{CABLE_NAME} isn't in the lists:</b> restart your PC after installing "
         f"{CABLE_NAME}, then click <b>Refresh</b>.</li>"
         f"<li><b>Friends hear nothing:</b> check Discord or the game is listening to <b>{CABLE_OUT}</b> "
         "and that Undertone's output meter moves when you talk.</li>"
         "<li><b>AI voice breaks up or the status says “too slow”:</b> raise <b>Latency</b>, "
         "or switch <b>Pitch tracking</b> to FCPE.</li>"
         "<li><b>AI voice sounds too high or low:</b> adjust <b>Pitch shift</b> (about +12 for "
         "a male → female voice, −12 for female → male).</li>"
         + problems_extra +
         "</ul>"),
    ]


class SetupGuide(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("guide")
        self.setWindowTitle("Undertone setup")
        self.resize(520, 760)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget(objectName="content")
        col = QVBoxLayout(content)
        col.setContentsMargins(20, 18, 20, 20)
        col.setSpacing(14)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        col.addWidget(QLabel("Set up Undertone", objectName="title"))
        intro = QLabel("About five minutes, once. You can open this again from the Setup button.",
                       objectName="hint")
        intro.setWordWrap(True)
        col.addWidget(intro)

        for i, (title, html) in enumerate(_steps(), 1):
            card = Card(f"{i}. {title}")
            text = QLabel(html)
            text.setTextFormat(Qt.RichText)
            text.setWordWrap(True)
            text.setOpenExternalLinks(True)
            card.body.addWidget(text)
            if i == 1:
                card.body.addLayout(self._cable_row())
            if title.startswith("If something"):
                logs = QPushButton("Open log folder")
                logs.setCursor(Qt.PointingHandCursor)
                logs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir()))))
                row = QHBoxLayout()
                row.addWidget(logs)
                row.addStretch()
                card.body.addLayout(row)
            col.addWidget(card)
        col.addStretch()

        bar = QFrame(objectName="bottombar")
        brow = QHBoxLayout(bar)
        brow.setContentsMargins(20, 12, 20, 14)
        brow.addStretch()
        done = QPushButton("Done", objectName="primary")
        done.setCursor(Qt.PointingHandCursor)
        done.clicked.connect(self.accept)
        brow.addWidget(done)
        outer.addWidget(bar)

    def _cable_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        get = QPushButton(f"Get {CABLE_NAME}")
        get.setCursor(Qt.PointingHandCursor)
        get.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(CABLE_URL)))
        row.addWidget(get)
        self.cable_status = QLabel()
        row.addWidget(self.cable_status, 1)
        self.refresh_cable_status()
        return row

    def refresh_cable_status(self) -> None:
        try:
            cable = audio.find_virtual_cable()
        except Exception:
            cable = None
        if cable:
            self.cable_status.setText(f"✓ Installed: {cable}")
            self.cable_status.setObjectName("hint")
        else:
            self.cable_status.setText("Not found yet")
            self.cable_status.setObjectName("warn")
        self.cable_status.style().unpolish(self.cable_status)
        self.cable_status.style().polish(self.cable_status)

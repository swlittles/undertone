"""Main window."""

import threading
import traceback

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..audio import engine as audio
from ..paths import ROOT, VOICES
from ..settings import Settings
from ..voices import ai
from ..voices.deep import PRESETS, DeepVoice
from . import theme
from .widgets import Card, Meter, Segmented, SliderRow, Switch, labeled

VB_CABLE_URL = "https://vb-audio.com/Cable/"
TEST_SECONDS = 6


class Bridge(QObject):
    """Signals used to hand results from worker threads back to the UI thread."""

    voice_loaded = Signal(object, object)  # (key, AIVoice)
    voice_failed = Signal(str)
    download_progress = Signal(float, str)
    download_done = Signal(str)  # empty string on success, else error
    device_name = Signal(str)


def _db_to_lin(db: float) -> float:
    return 10 ** (db / 20)


class MainWindow(QMainWindow):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.s = Settings.load()
        self.engine = audio.AudioEngine()
        self.deep = DeepVoice(self.s.deep_pitch, self.s.deep_formant, self.s.deep_warmth)
        self.ai_voice = None  # loaded AIVoice
        self.ai_key = None  # (voice, chunk, f0) it was loaded with
        self.loading = False
        self.test_clips = None
        self.bridge = Bridge()
        self.bridge.voice_loaded.connect(self._on_voice_loaded)
        self.bridge.voice_failed.connect(self._on_voice_failed)
        self.bridge.download_progress.connect(self._on_download_progress)
        self.bridge.download_done.connect(self._on_download_done)
        self.bridge.device_name.connect(lambda n: self.ai_device.setText(f"Runs on: {n}"))

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.s.save)

        self.setWindowTitle("Undertone")
        self.resize(560, 860)
        self.setMinimumWidth(500)
        theme.apply(app, self.s.theme)
        self._build()
        self._load_settings_into_ui()
        self._refresh_devices()
        self._refresh_voices()
        self._update_base_model_banner()
        self._set_live_ui(False)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

        app.styleHints().colorSchemeChanged.connect(lambda _: self._apply_theme())
        threading.Thread(target=self._detect_compute, daemon=True).start()

    # ---- layout ------------------------------------------------------------------

    def _build(self):
        root = QWidget(objectName="root")
        outer = QVBoxLayout(root)
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

        col.addLayout(self._header())
        col.addWidget(self._mode_card())
        col.addWidget(self._audio_card())
        col.addWidget(self._test_card())
        col.addStretch()

        outer.addWidget(self._bottom_bar())
        self.setCentralWidget(root)

    def _header(self):
        row = QHBoxLayout()
        logo = QLabel(objectName="logo")
        pm = QPixmap(str(ROOT / "undertone" / "assets" / "icon.png"))
        dpr = self.devicePixelRatioF()
        pm = pm.scaled(int(26 * dpr), int(26 * dpr), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pm.setDevicePixelRatio(dpr)
        logo.setPixmap(pm)
        title = QLabel("Undertone", objectName="title")
        row.addWidget(logo)
        row.addWidget(title)
        row.addStretch()
        self.theme_btn = QPushButton(objectName="ghost")
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.clicked.connect(self._cycle_theme)
        row.addWidget(self.theme_btn)
        return row

    def _mode_card(self):
        card = Card()
        self.mode_seg = Segmented(["Deep voice", "AI voice"])
        self.mode_seg.changed.connect(self._on_mode)
        card.body.addWidget(self.mode_seg)
        # Hidden/shown rather than a QStackedWidget, which is always as tall as its tallest page.
        self.mode_pages = [self._deep_panel(), self._ai_panel()]
        for page in self.mode_pages:
            card.body.addWidget(page)
        return card

    def _deep_panel(self):
        w = QWidget()
        col = QVBoxLayout(w)
        col.setContentsMargins(0, 4, 0, 0)
        col.setSpacing(14)
        blurb = QLabel("Your own voice, lower and bigger. Pitch and vocal size move separately so it "
                       "sounds like a deeper-voiced person, not a slowed-down recording.")
        blurb.setObjectName("hint")
        blurb.setWordWrap(True)
        col.addWidget(blurb)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.preset_btns = {}
        for name in [*PRESETS, "Custom"]:
            b = QPushButton(name, objectName="chip")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=name: self._on_preset(n))
            chips.addWidget(b)
            self.preset_btns[name] = b
        chips.addStretch()
        col.addLayout(chips)

        self.deep_pitch = SliderRow("Pitch", -8, 4, 0.5, lambda v: f"{v:+.1f} semitones",
                                    "How low the voice sits. Most realistic between −2 and −5.")
        self.deep_formant = SliderRow("Vocal size", 0.80, 1.10, 0.01, lambda v: f"{(1 - v) * 100:+.0f}% bigger" if v <= 1 else f"{(v - 1) * 100:.0f}% smaller",
                                      "Size of the throat and chest it sounds like. Keep it well under the pitch change.")
        self.deep_warmth = SliderRow("Warmth", 0, 6, 0.5, lambda v: f"+{v:.1f} dB", "Extra low-end body.")
        for r in (self.deep_pitch, self.deep_formant, self.deep_warmth):
            r.valueChanged.connect(self._on_deep_slider)
            col.addWidget(r)
        return w

    def _ai_panel(self):
        w = QWidget()
        col = QVBoxLayout(w)
        col.setContentsMargins(0, 4, 0, 0)
        col.setSpacing(14)
        blurb = QLabel("Replaces your voice with a voice model. You still do the talking — words, timing "
                       "and emotion are yours — but the voice people hear is the model's.")
        blurb.setObjectName("hint")
        blurb.setWordWrap(True)
        col.addWidget(blurb)

        self.base_banner = QFrame(objectName="banner")
        bb = QVBoxLayout(self.base_banner)
        bb.setContentsMargins(14, 12, 14, 12)
        bb.setSpacing(8)
        self.base_label = QLabel()
        self.base_label.setWordWrap(True)
        bb.addWidget(self.base_label)
        brow = QHBoxLayout()
        self.base_btn = QPushButton("Download")
        self.base_btn.setCursor(Qt.PointingHandCursor)
        self.base_btn.clicked.connect(self._download_base)
        self.base_progress = QProgressBar()
        self.base_progress.setRange(0, 1000)
        self.base_progress.hide()
        brow.addWidget(self.base_btn)
        brow.addWidget(self.base_progress, 1)
        bb.addLayout(brow)
        col.addWidget(self.base_banner)

        vrow = QHBoxLayout()
        self.voice_combo = QComboBox()
        self.voice_combo.currentIndexChanged.connect(self._on_voice_changed)
        add = QPushButton("Add voice…")
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(self._add_voice)
        folder = QPushButton("Folder")
        folder.setToolTip("Open the voices folder")
        folder.setCursor(Qt.PointingHandCursor)
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(VOICES))))
        vrow.addWidget(self.voice_combo, 1)
        vrow.addWidget(add)
        vrow.addWidget(folder)
        vw = QWidget()
        vw.setLayout(vrow)
        vrow.setContentsMargins(0, 0, 0, 0)
        col.addWidget(labeled("Voice", vw, "An RVC v2 voice model (.pth, or a .zip with one inside)."))

        self.ai_pitch = SliderRow("Pitch shift", -12, 12, 1, lambda v: f"{v:+.0f} semitones",
                                  "Match your range to the voice. Male → female voice: about +12. Female → male: about −12.")
        self.ai_index = SliderRow("Voice match", 0, 1, 0.05, lambda v: f"{v * 100:.0f}%",
                                  "Higher sounds more like the model but can slur words. Needs the voice's .index file.")
        self.ai_protect = SliderRow("Protect consonants", 0, 0.5, 0.01, lambda v: f"{v / 0.5 * 100:.0f}%",
                                    "Keeps breaths and 's'/'t' sounds natural. Lower = more of the model's voice.")
        self.ai_chunk = SliderRow("Latency", 80, 400, 10, lambda v: f"{v:.0f} ms chunks",
                                  "Lower = less delay, more GPU work. If the voice breaks up, raise it.")
        self.ai_gate = SliderRow("Noise gate", -70, -20, 1, lambda v: f"{v:.0f} dB",
                                 "Silence below this level is muted, so keyboard and fan noise don't turn into voice.")
        for r in (self.ai_pitch, self.ai_index, self.ai_protect):
            r.valueChanged.connect(self._on_ai_slider)
        self.ai_chunk.valueChanged.connect(self._on_ai_reload_setting)
        self.ai_gate.valueChanged.connect(self._on_ai_slider)
        for r in (self.ai_pitch, self.ai_index, self.ai_protect, self.ai_chunk, self.ai_gate):
            col.addWidget(r)

        self.f0_combo = QComboBox()
        self.f0_combo.addItem("RMVPE — most accurate", "rmvpe")
        self.f0_combo.addItem("FCPE — fastest", "fcpe")
        self.f0_combo.currentIndexChanged.connect(self._on_ai_reload_setting)
        col.addWidget(labeled("Pitch tracking", self.f0_combo))

        self.ai_device = QLabel("Runs on: checking…", objectName="hint")
        col.addWidget(self.ai_device)
        return w

    def _audio_card(self):
        card = Card("Audio")
        self.in_combo = QComboBox()
        self.out_combo = QComboBox()
        self.mon_combo = QComboBox()
        for c in (self.in_combo, self.out_combo, self.mon_combo):
            c.currentIndexChanged.connect(self._on_device_changed)

        card.body.addWidget(labeled("Microphone", self.in_combo))
        self.in_meter = Meter()
        card.body.addWidget(self.in_meter)
        self.mic_gain = SliderRow("Mic level", -12, 12, 0.5, lambda v: f"{v:+.1f} dB")
        self.mic_gain.valueChanged.connect(self._on_gain)
        card.body.addWidget(self.mic_gain)

        card.body.addWidget(labeled(
            "Send changed voice to", self.out_combo,
            "Pick “CABLE Input”, then choose “CABLE Output” as the microphone in Discord or your game."))
        self.out_meter = Meter()
        card.body.addWidget(self.out_meter)
        self.out_gain = SliderRow("Output level", -12, 12, 0.5, lambda v: f"{v:+.1f} dB")
        self.out_gain.valueChanged.connect(self._on_gain)
        card.body.addWidget(self.out_gain)

        self.cable_banner = QFrame(objectName="banner")
        cb = QHBoxLayout(self.cable_banner)
        cb.setContentsMargins(14, 10, 14, 10)
        msg = QLabel("No virtual cable found. Install the free VB-Cable so games and Discord can hear the changed voice.",
                     objectName="warn")
        msg.setWordWrap(True)
        get = QPushButton("Get VB-Cable")
        get.setCursor(Qt.PointingHandCursor)
        get.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(VB_CABLE_URL)))
        refresh = QPushButton("Refresh")
        refresh.setCursor(Qt.PointingHandCursor)
        refresh.clicked.connect(self._refresh_devices)
        cb.addWidget(msg, 1)
        cb.addWidget(get)
        cb.addWidget(refresh)
        card.body.addWidget(self.cable_banner)

        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("Hear myself"))
        mrow.addStretch()
        self.mon_switch = Switch()
        self.mon_switch.toggled.connect(self._on_monitor)
        mrow.addWidget(self.mon_switch)
        card.body.addLayout(mrow)
        hint = QLabel("Plays the changed voice in your headphones. Handy for tuning, distracting while you talk.",
                      objectName="hint")
        hint.setWordWrap(True)
        card.body.addWidget(hint)
        card.body.addWidget(labeled("Headphones", self.mon_combo))
        return card

    def _test_card(self):
        card = Card("Test my voice")
        hint = QLabel(f"Records {TEST_SECONDS} seconds while live, then lets you compare your real voice "
                      "with what others hear. Talk the way you do in game.", objectName="hint")
        hint.setWordWrap(True)
        card.body.addWidget(hint)
        row = QHBoxLayout()
        self.rec_btn = QPushButton("●  Record")
        self.rec_btn.setCursor(Qt.PointingHandCursor)
        self.rec_btn.clicked.connect(self._record_test)
        self.play_orig = QPushButton("▶  Original")
        self.play_wet = QPushButton("▶  Changed")
        for b in (self.play_orig, self.play_wet):
            b.setCursor(Qt.PointingHandCursor)
            b.setEnabled(False)
        self.play_orig.clicked.connect(lambda: self._play_test(0))
        self.play_wet.clicked.connect(lambda: self._play_test(1))
        row.addWidget(self.rec_btn)
        row.addWidget(self.play_orig)
        row.addWidget(self.play_wet)
        row.addStretch()
        card.body.addLayout(row)
        self.rec_progress = QProgressBar()
        self.rec_progress.setRange(0, 1000)
        self.rec_progress.hide()
        card.body.addWidget(self.rec_progress)
        return card

    def _bottom_bar(self):
        bar = QFrame(objectName="bottombar")
        col = QVBoxLayout(bar)
        col.setContentsMargins(20, 12, 20, 14)
        col.setSpacing(8)
        row = QHBoxLayout()
        self.start_btn = QPushButton("Start", objectName="primary")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._toggle_live)
        self.bypass_btn = QPushButton("Real voice")
        self.bypass_btn.setCheckable(True)
        self.bypass_btn.setCursor(Qt.PointingHandCursor)
        self.bypass_btn.setToolTip("Temporarily send your real voice")
        self.bypass_btn.setMinimumHeight(44)
        self.bypass_btn.toggled.connect(lambda on: setattr(self.engine, "bypass", on))
        row.addWidget(self.start_btn, 1)
        row.addWidget(self.bypass_btn)
        col.addLayout(row)
        self.status = QLabel("Off", objectName="stats")
        self.status.setWordWrap(True)
        col.addWidget(self.status)
        return bar

    # ---- settings <-> ui ----------------------------------------------------------

    def _load_settings_into_ui(self):
        s = self.s
        self.mode_seg.set_index(1 if s.mode == "ai" else 0)
        self._show_mode_page(1 if s.mode == "ai" else 0)
        self.deep_pitch.set_value(s.deep_pitch)
        self.deep_formant.set_value(s.deep_formant)
        self.deep_warmth.set_value(s.deep_warmth)
        self._mark_preset(s.deep_preset)
        self.ai_pitch.set_value(s.ai_pitch)
        self.ai_index.set_value(s.ai_index_rate)
        self.ai_protect.set_value(s.ai_protect)
        self.ai_chunk.set_value(s.ai_chunk_ms)
        self.ai_gate.set_value(s.ai_gate_db)
        self.f0_combo.blockSignals(True)
        self.f0_combo.setCurrentIndex(max(0, self.f0_combo.findData(s.ai_f0_method)))
        self.f0_combo.blockSignals(False)
        self.mic_gain.set_value(s.input_gain_db)
        self.out_gain.set_value(s.output_gain_db)
        self.mon_switch.setChecked(s.monitor)
        self._on_gain()
        self._update_theme_button()

    def _save_soon(self):
        self.save_timer.start(400)

    def _fill_combo(self, combo: QComboBox, names: list[str], selected: str, none_label: str = ""):
        combo.blockSignals(True)
        combo.clear()
        if none_label:
            combo.addItem(none_label, "")
        for n in names:
            combo.addItem(n, n)
        i = combo.findData(selected)
        combo.setCurrentIndex(i if i >= 0 else 0)
        combo.blockSignals(False)

    def _refresh_devices(self):
        try:
            inputs, outputs = audio.list_devices("input"), audio.list_devices("output")
        except Exception as e:
            self._set_status(f"Couldn't list audio devices: {e}", error=True)
            return
        cable = audio.find_virtual_cable()
        s = self.s
        s.input_device = s.input_device if s.input_device in inputs else audio.default_device("input")
        speakers = audio.default_device("output")
        if s.output_device not in outputs or (cable and s.output_device == speakers):
            # Sending the changed voice to your own speakers is never what you want once a cable exists.
            s.output_device = cable or speakers
        if s.monitor_device not in outputs:
            s.monitor_device = audio.default_device("output")
        self._fill_combo(self.in_combo, inputs, s.input_device)
        self._fill_combo(self.out_combo, outputs, s.output_device)
        self._fill_combo(self.mon_combo, outputs, s.monitor_device)
        self.cable_banner.setVisible(cable is None)

    def _refresh_voices(self, select: str = ""):
        voices = ai.list_voices()
        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()
        if not voices:
            self.voice_combo.addItem("No voices yet — click Add voice…", "")
        for v in voices:
            self.voice_combo.addItem(ai.voice_label(v), v)
        want = select or self.s.ai_voice
        i = self.voice_combo.findData(want)
        self.voice_combo.setCurrentIndex(i if i >= 0 else 0)
        self.voice_combo.blockSignals(False)
        self.s.ai_voice = self.voice_combo.currentData() or ""
        self._update_index_slider()

    def _update_index_slider(self):
        has = bool(self.s.ai_voice) and ai.index_for(self.s.ai_voice) is not None
        self.ai_index.setEnabled(has)
        self.ai_index.setToolTip("" if has else "This voice has no .index file, so this setting does nothing.")

    def _update_base_model_banner(self):
        missing = ai.missing_base_models()
        if not missing:
            self.base_banner.hide()
            return
        mb = sum(m for _, _, m in missing)
        self.base_label.setText(f"AI voice needs a one-time download of shared models (about {mb} MB): "
                                "speech features and pitch tracking.")
        self.base_btn.setText(f"Download {mb} MB")
        self.base_banner.show()

    # ---- theme -----------------------------------------------------------------------

    def _cycle_theme(self):
        order = ["system", "light", "dark"]
        self.s.theme = order[(order.index(self.s.theme) + 1) % 3]
        self._apply_theme()
        self._save_soon()

    def _apply_theme(self):
        theme.apply(self.app, self.s.theme)
        self._update_theme_button()
        for w in self.findChildren(QWidget):
            w.update()
        self._restyle(self.start_btn)

    def _update_theme_button(self):
        icon = {"system": "◐", "light": "☀", "dark": "☾"}[self.s.theme]
        self.theme_btn.setText(f"{icon}  {self.s.theme.capitalize()}")
        self.theme_btn.setToolTip("Theme: System, Light or Dark")

    @staticmethod
    def _restyle(w):
        w.style().unpolish(w)
        w.style().polish(w)

    # ---- event handlers ----------------------------------------------------------

    def _show_mode_page(self, i: int):
        for j, page in enumerate(self.mode_pages):
            page.setVisible(j == i)

    def _on_mode(self, i: int):
        self.s.mode = "ai" if i == 1 else "deep"
        self._show_mode_page(i)
        self._save_soon()
        if self.engine.running:
            self._go_live()

    def _mark_preset(self, name: str):
        for n, b in self.preset_btns.items():
            b.setChecked(n == name)

    def _on_preset(self, name: str):
        self.s.deep_preset = name
        self._mark_preset(name)
        if name in PRESETS:
            pitch, formant, warmth = PRESETS[name]
            self.deep_pitch.set_value(pitch)
            self.deep_formant.set_value(formant)
            self.deep_warmth.set_value(warmth)
            self._apply_deep()

    def _on_deep_slider(self, _):
        self.s.deep_preset = "Custom"
        self._mark_preset("Custom")
        self._apply_deep()

    def _apply_deep(self):
        s = self.s
        s.deep_pitch, s.deep_formant, s.deep_warmth = (
            self.deep_pitch.value(), self.deep_formant.value(), self.deep_warmth.value())
        self.deep.set_params(s.deep_pitch, s.deep_formant, s.deep_warmth)
        self._save_soon()

    def _on_ai_slider(self, _=None):
        s = self.s
        s.ai_pitch = int(self.ai_pitch.value())
        s.ai_index_rate = self.ai_index.value()
        s.ai_protect = self.ai_protect.value()
        s.ai_gate_db = int(self.ai_gate.value())
        if self.ai_voice is not None:
            self.ai_voice.set_params(s.ai_pitch, s.ai_index_rate, s.ai_protect)
            self.ai_voice.set_gate(s.ai_gate_db)
        self._save_soon()

    def _on_ai_reload_setting(self, _=None):
        self.s.ai_chunk_ms = int(self.ai_chunk.value())
        self.s.ai_f0_method = self.f0_combo.currentData()
        self._save_soon()
        if self.engine.running and self.s.mode == "ai":
            self.reload_timer = getattr(self, "reload_timer", None) or self._make_reload_timer()
            self.reload_timer.start(700)  # wait for the slider to settle

    def _make_reload_timer(self):
        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(self._go_live)
        return t

    def _on_voice_changed(self, _):
        self.s.ai_voice = self.voice_combo.currentData() or ""
        self._update_index_slider()
        self._save_soon()
        if self.engine.running and self.s.mode == "ai":
            self._go_live()

    def _add_voice(self):
        path, _ = QFileDialog.getOpenFileName(self, "Add a voice model", "", "Voice models (*.pth *.zip)")
        if not path:
            return
        try:
            rel = ai.import_voice(path)
        except Exception as e:
            self._set_status(f"Couldn't add that voice: {e}", error=True)
            return
        self._refresh_voices(select=rel)
        self._on_voice_changed(None)
        self._set_status(f"Added voice “{ai.voice_label(rel)}”.")

    def _on_device_changed(self, _):
        s = self.s
        s.input_device = self.in_combo.currentData() or ""
        s.output_device = self.out_combo.currentData() or ""
        s.monitor_device = self.mon_combo.currentData() or ""
        self._save_soon()
        if self.engine.running:
            self._start_engine(self.engine.processor)

    def _on_gain(self, _=None):
        self.s.input_gain_db = self.mic_gain.value()
        self.s.output_gain_db = self.out_gain.value()
        self.engine.input_gain = _db_to_lin(self.s.input_gain_db)
        self.engine.out.gain = _db_to_lin(self.s.output_gain_db)
        self._save_soon()

    def _on_monitor(self, on: bool):
        self.s.monitor = on
        self.engine.monitor_enabled = on
        self.engine.mon.fifo.clear()
        self._save_soon()

    # ---- going live ------------------------------------------------------------------

    def _toggle_live(self):
        if self.engine.running or self.loading:
            self.engine.stop()
            self.loading = False
            self._set_live_ui(False)
            self._set_status("Off")
        else:
            self._go_live()

    def _go_live(self):
        if self.s.mode == "deep":
            self.loading = False
            self.deep.set_params(self.s.deep_pitch, self.s.deep_formant, self.s.deep_warmth)
            self._start_engine(self.deep)
            return
        if ai.missing_base_models():
            self._set_status("Download the shared AI models first (button above).", error=True)
            self.mode_seg.set_index(1)
            return
        if not self.s.ai_voice:
            self._set_status("Add a voice model first.", error=True)
            return
        key = (self.s.ai_voice, self.s.ai_chunk_ms, self.s.ai_f0_method)
        if self.ai_voice is not None and self.ai_key == key:
            self._start_engine(self.ai_voice)
            return
        self.loading = True
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Loading voice…")
        self._set_status(f"Loading “{ai.voice_label(self.s.ai_voice)}” — the first time takes a little while.")
        s = self.s

        def work():
            try:
                v = ai.AIVoice(s.ai_voice, s.ai_chunk_ms, s.ai_f0_method, s.ai_gate_db)
                v.set_params(s.ai_pitch, s.ai_index_rate, s.ai_protect)
                self.bridge.voice_loaded.emit(key, v)
            except Exception as e:
                traceback.print_exc()
                self.bridge.voice_failed.emit(f"{type(e).__name__}: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _on_voice_loaded(self, key, voice):
        self.ai_voice, self.ai_key = voice, key
        current = (self.s.ai_voice, self.s.ai_chunk_ms, self.s.ai_f0_method)
        if not self.loading or self.s.mode != "ai" or key != current:
            return  # stopped, switched mode, or a newer load is coming
        self.loading = False
        self.ai_device.setText(f"Runs on: {voice.device}")
        self._start_engine(voice)

    def _on_voice_failed(self, msg: str):
        self.loading = False
        self.start_btn.setEnabled(True)
        self._set_live_ui(self.engine.running)
        self._set_status(f"Couldn't load the voice: {msg}", error=True)

    def _start_engine(self, processor):
        s = self.s
        try:
            self.engine.monitor_enabled = s.monitor
            self.engine.start(s.input_device, s.output_device, s.monitor_device, processor)
        except Exception as e:
            self.engine.stop()
            self._set_live_ui(False)
            self._set_status(str(e), error=True)
            return
        self._set_live_ui(True)
        self._set_status("Live")

    def _set_live_ui(self, live: bool):
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Stop" if live else "Start")
        self.start_btn.setProperty("live", "true" if live else "false")
        self._restyle(self.start_btn)
        self.rec_btn.setEnabled(live)

    # ---- downloads -----------------------------------------------------------------

    def _download_base(self):
        self.base_btn.setEnabled(False)
        self.base_progress.show()

        def work():
            try:
                ai.download_base_models(lambda f, label: self.bridge.download_progress.emit(f, label))
                self.bridge.download_done.emit("")
            except Exception as e:
                self.bridge.download_done.emit(f"{type(e).__name__}: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _on_download_progress(self, frac: float, label: str):
        self.base_progress.setValue(int(frac * 1000))
        self.base_label.setText(f"{label}… {frac * 100:.0f}%")

    def _on_download_done(self, err: str):
        self.base_btn.setEnabled(True)
        self.base_progress.hide()
        if err:
            self.base_label.setText(f"Download failed: {err}. Check your connection and try again.")
            return
        self._update_base_model_banner()
        self._set_status("Shared AI models downloaded.")

    def _detect_compute(self):
        try:
            self.bridge.device_name.emit(ai.compute_device())
        except Exception as e:
            self.bridge.device_name.emit(f"unavailable ({e})")

    # ---- voice test ------------------------------------------------------------------

    def _record_test(self):
        audio.stop_playback()
        self.engine.begin_capture(TEST_SECONDS)
        self.rec_progress.setValue(0)
        self.rec_progress.show()
        self.rec_btn.setEnabled(False)
        self.rec_btn.setText("●  Recording…")
        self.play_orig.setEnabled(False)
        self.play_wet.setEnabled(False)

    def _play_test(self, which: int):
        if not self.test_clips:
            return
        audio.stop_playback()
        device = self.s.monitor_device
        if device == self.s.output_device:  # never play the test into the cable
            device = ""
        audio.play(self.test_clips[which], device)

    # ---- periodic ui update --------------------------------------------------------

    def _tick(self):
        e = self.engine
        self.in_meter.set_level(e.in_peak if e.running else 0)
        self.out_meter.set_level(e.out.peak if e.running else 0)

        if self.rec_progress.isVisible():
            self.rec_progress.setValue(int(e.capture_progress() * 1000))
            clips = e.capture_result()
            if clips is not None:
                self.test_clips = clips
                self.rec_progress.hide()
                self.rec_btn.setText("●  Record")
                self.rec_btn.setEnabled(e.running)
                self.play_orig.setEnabled(True)
                self.play_wet.setEnabled(True)
                self._play_test(1)
            elif not e.running:
                self.rec_progress.hide()
                self.rec_btn.setText("●  Record")

        if e.running and not self.loading:
            if e.error:
                self._set_status(f"Processing error, sending your real voice: {e.error}", error=True)
                return
            load = e.load()
            parts = [f"Live · about {e.latency_ms():.0f} ms delay",
                     f"processing {load * 100:.0f}% of real time"]
            if e.bypass:
                parts.insert(0, "Real voice")
            text = " · ".join(parts)
            if load > 0.85:
                text += " — too slow; raise Latency" if self.s.mode == "ai" else " — computer is struggling"
            self._set_status(text, error=load > 0.85)

    def _set_status(self, text: str, error: bool = False):
        self.status.setText(text)
        name = "error" if error else "stats"
        if self.status.objectName() != name:
            self.status.setObjectName(name)
            self._restyle(self.status)

    def closeEvent(self, ev):
        self.engine.stop()
        audio.stop_playback()
        self.s.save()
        super().closeEvent(ev)


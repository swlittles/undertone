"""Small custom widgets that follow the active theme."""

from typing import Callable

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from . import theme


class Switch(QAbstractButton):
    """iOS-style toggle."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def sizeHint(self):
        return QSize(40, 22)

    def _animate(self, on):
        self._anim.stop()
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def setChecked(self, on):  # noqa: N802 (Qt naming)
        super().setChecked(on)
        self._anim.stop()
        self._pos = 1.0 if on else 0.0
        self.update()

    def get_knob(self):
        return self._pos

    def set_knob(self, v):
        self._pos = v
        self.update()

    knob = Property(float, get_knob, set_knob)

    def paintEvent(self, _):
        p = theme.current()
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        off, on = QColor(p.border), QColor(p.accent)
        mix = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos),
        )
        if not self.isEnabled():
            mix = QColor(p.inset)
        qp.setPen(Qt.NoPen)
        qp.setBrush(mix)
        qp.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * self._pos
        qp.setBrush(QColor("#FFFFFF"))
        qp.drawEllipse(QRectF(x, r.top() + 3, d, d))


class Meter(QWidget):
    """Horizontal level meter (0..1 peak, drawn on a dB-ish scale)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._level = 0.0
        self.setFixedHeight(8)

    def set_level(self, peak: float):
        import math

        db = 20 * math.log10(max(peak, 1e-6))
        level = min(1.0, max(0.0, (db + 60) / 60))
        if abs(level - self._level) > 0.004:
            self._level = level
            self.update()

    def paintEvent(self, _):
        p = theme.current()
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        qp.setPen(Qt.NoPen)
        qp.setBrush(QColor(p.inset))
        qp.drawRoundedRect(r, 4, 4)
        if self._level > 0:
            color = p.danger if self._level > 0.95 else p.accent
            qp.setBrush(QColor(color))
            qp.drawRoundedRect(QRectF(0, 0, self.width() * self._level, self.height()), 4, 4)


class Card(QFrame):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 16, 18, 18)
        self.body.setSpacing(12)
        if title:
            label = QLabel(title.upper())
            label.setObjectName("section")
            self.body.addWidget(label)


class Segmented(QFrame):
    """Two-or-more option toggle, like a pill tab bar."""

    changed = Signal(int)

    def __init__(self, labels: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("segment")
        row = QHBoxLayout(self)
        row.setContentsMargins(3, 3, 3, 3)
        row.setSpacing(3)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, text in enumerate(labels):
            b = QPushButton(text)
            b.setObjectName("segbtn")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.group.addButton(b, i)
            row.addWidget(b)
        self.group.idClicked.connect(self.changed.emit)

    def set_index(self, i: int):
        self.group.button(i).setChecked(True)

    def index(self) -> int:
        return self.group.checkedId()


class SliderRow(QWidget):
    """Label, live value readout and a slider over a float range."""

    valueChanged = Signal(float)
    released = Signal()

    def __init__(self, label: str, lo: float, hi: float, step: float, fmt: Callable[[float], str], hint: str = ""):
        super().__init__()
        self.lo, self.step, self.fmt = lo, step, fmt
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        top = QHBoxLayout()
        self.label = QLabel(label)
        self.value_label = QLabel()
        self.value_label.setObjectName("value")
        top.addWidget(self.label)
        top.addStretch()
        top.addWidget(self.value_label)
        col.addLayout(top)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, round((hi - lo) / step))
        self.slider.setCursor(Qt.PointingHandCursor)
        self.slider.valueChanged.connect(self._changed)
        self.slider.sliderReleased.connect(self.released.emit)
        col.addWidget(self.slider)
        if hint:
            h = QLabel(hint)
            h.setObjectName("hint")
            h.setWordWrap(True)
            col.addWidget(h)
            self.setToolTip(hint)

    def value(self) -> float:
        return round(self.lo + self.slider.value() * self.step, 6)

    def set_value(self, v: float):
        self.slider.blockSignals(True)
        self.slider.setValue(round((v - self.lo) / self.step))
        self.slider.blockSignals(False)
        self.value_label.setText(self.fmt(self.value()))

    def _changed(self, _):
        v = self.value()
        self.value_label.setText(self.fmt(v))
        self.valueChanged.emit(v)


def labeled(text: str, widget: QWidget, hint: str = "") -> QWidget:
    w = QWidget()
    col = QVBoxLayout(w)
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(6)
    col.addWidget(QLabel(text))
    col.addWidget(widget)
    if hint:
        h = QLabel(hint)
        h.setObjectName("hint")
        h.setWordWrap(True)
        col.addWidget(h)
    return w

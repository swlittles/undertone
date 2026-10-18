"""Regenerate undertone/assets/icon.png and undertone.ico (needs Pillow)."""

import math
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen

OUT = Path(__file__).resolve().parents[1] / "undertone" / "assets"


def draw(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    qp = QPainter(img)
    qp.setRenderHint(QPainter.Antialiasing)
    qp.setPen(Qt.NoPen)
    qp.setBrush(QColor("#D97757"))
    qp.drawRoundedRect(QRectF(0, 0, size, size), size * 0.23, size * 0.23)
    # Spark: rays of alternating length, like Claude's mark.
    c = QPointF(size / 2, size / 2)
    pen = QPen(QColor("#FFFFFF"), size * 0.085, Qt.SolidLine, Qt.RoundCap)
    qp.setPen(pen)
    for i in range(12):
        a = math.pi * 2 * i / 12
        r = size * (0.33 if i % 2 == 0 else 0.24)
        qp.drawLine(QPointF(c.x() + math.cos(a) * size * 0.07, c.y() + math.sin(a) * size * 0.07),
                    QPointF(c.x() + math.cos(a) * r, c.y() + math.sin(a) * r))
    qp.end()
    return img


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    draw(512).save(str(OUT / "icon.png"))
    Image.open(OUT / "icon.png").save(OUT / "undertone.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print("wrote", OUT)

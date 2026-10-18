"""Claude Code–style palette (warm ivory / charcoal with Claude orange) and Qt stylesheet."""

import sys
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str
    panel: str
    inset: str
    border: str
    text: str
    text2: str
    muted: str
    accent: str
    accent_hover: str
    accent_pressed: str
    on_accent: str
    success: str
    warning: str
    danger: str


LIGHT = Palette(
    name="light",
    bg="#FAF9F5",
    panel="#FFFFFF",
    inset="#F0EEE6",
    border="#E5E2D9",
    text="#141413",
    text2="#3D3D3A",
    muted="#83827D",
    accent="#D97757",
    accent_hover="#C6613F",
    accent_pressed="#B4532F",
    on_accent="#FFFFFF",
    success="#5E8C4F",
    warning="#B9822A",
    danger="#BF4D43",
)

DARK = Palette(
    name="dark",
    bg="#262624",
    panel="#30302E",
    inset="#1F1E1D",
    border="#41413D",
    text="#F5F4EE",
    text2="#D6D4CB",
    muted="#9C9A92",
    accent="#D97757",
    accent_hover="#E3896A",
    accent_pressed="#C6613F",
    on_accent="#FFFFFF",
    success="#7FB069",
    warning="#E0A84A",
    danger="#E06C60",
)

_current = LIGHT
_FONT = 'font-family: "Segoe UI";' if sys.platform == "win32" else ""  # elsewhere: system UI font


def current() -> Palette:
    return _current


def resolve(choice: str) -> Palette:
    if choice == "light":
        return LIGHT
    if choice == "dark":
        return DARK
    scheme = QGuiApplication.styleHints().colorScheme()
    return DARK if scheme == Qt.ColorScheme.Dark else LIGHT


def apply(app, choice: str) -> Palette:
    global _current
    _current = resolve(choice)
    app.setStyleSheet(stylesheet(_current))
    return _current


def _arrow(p: Palette) -> str:
    """Qt stylesheets can't draw a chevron, so write a tiny SVG per theme."""
    from ..paths import data_dir

    path = data_dir() / f"arrow-{p.name}.svg"
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" viewBox="0 0 10 6">'
           f'<path d="M1 1l4 4 4-4" fill="none" stroke="{p.muted}" stroke-width="1.6" '
           f'stroke-linecap="round" stroke-linejoin="round"/></svg>')
    if not path.exists() or path.read_text() != svg:
        path.write_text(svg)
    return path.as_posix()


def stylesheet(p: Palette) -> str:
    return f"""
* {{
    {_FONT}
    font-size: 13px;
    color: {p.text};
}}
QMainWindow, QDialog, QWidget#root, QScrollArea, QWidget#content {{
    background: {p.bg};
    border: none;
}}
QToolTip {{
    background: {p.panel}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 6px; padding: 6px 8px;
}}

QFrame#card {{
    background: {p.panel};
    border: 1px solid {p.border};
    border-radius: 14px;
}}
QFrame#banner {{
    background: {p.inset};
    border: 1px solid {p.border};
    border-radius: 10px;
}}
QFrame#bottombar {{
    background: {p.panel};
    border-top: 1px solid {p.border};
}}

QLabel#title {{ font-size: 20px; font-weight: 600; }}
QLabel#logo {{ font-size: 22px; color: {p.accent}; }}
QLabel#section {{
    font-size: 11px; font-weight: 600; letter-spacing: 1px; color: {p.muted};
}}
QLabel#hint {{ color: {p.muted}; font-size: 12px; }}
QLabel#value {{ color: {p.text2}; font-size: 12px; font-weight: 600; }}
QLabel#warn {{ color: {p.warning}; }}
QLabel#error {{ color: {p.danger}; }}
QLabel#stats {{ color: {p.muted}; font-size: 12px; }}

QPushButton {{
    background: {p.panel};
    border: 1px solid {p.border};
    border-radius: 9px;
    padding: 7px 14px;
    color: {p.text};
}}
QPushButton:hover {{ background: {p.inset}; }}
QPushButton:pressed {{ background: {p.border}; }}
QPushButton:disabled {{ color: {p.muted}; background: {p.inset}; }}
QPushButton:checked {{
    background: {p.accent}; border-color: {p.accent}; color: {p.on_accent};
}}

QPushButton#primary {{
    background: {p.accent}; border: none; color: {p.on_accent};
    font-size: 15px; font-weight: 600; border-radius: 12px; padding: 12px 22px;
}}
QPushButton#primary:hover {{ background: {p.accent_hover}; }}
QPushButton#primary:pressed {{ background: {p.accent_pressed}; }}
QPushButton#primary[live="true"] {{
    background: {p.inset}; color: {p.text}; border: 1px solid {p.border};
}}
QPushButton#primary[live="true"]:hover {{ background: {p.border}; }}
QPushButton#primary:disabled {{ background: {p.inset}; color: {p.muted}; }}

QPushButton#ghost {{
    background: transparent; border: none; padding: 6px 8px; border-radius: 8px; font-size: 16px;
}}
QPushButton#ghost:hover {{ background: {p.inset}; }}

QPushButton#chip {{
    border-radius: 12px; padding: 4px 13px;
}}

QFrame#segment {{
    background: {p.inset}; border-radius: 11px; border: 1px solid {p.border};
}}
QPushButton#segbtn {{
    background: transparent; border: none; border-radius: 8px; padding: 8px 10px;
    font-weight: 600; color: {p.muted};
}}
QPushButton#segbtn:hover {{ color: {p.text}; }}
QPushButton#segbtn:checked {{
    background: {p.panel}; color: {p.text}; border: 1px solid {p.border};
}}

QComboBox {{
    background: {p.inset}; border: 1px solid {p.border}; border-radius: 9px;
    padding: 6px 10px; min-height: 20px;
}}
QComboBox:hover {{ border-color: {p.muted}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: url("{_arrow(p)}"); width: 10px; height: 6px; margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {p.panel}; border: 1px solid {p.border}; border-radius: 8px;
    selection-background-color: {p.accent}; selection-color: {p.on_accent};
    padding: 4px; outline: none;
}}

QSlider::groove:horizontal {{
    height: 6px; background: {p.inset}; border-radius: 3px; border: 1px solid {p.border};
}}
QSlider::sub-page:horizontal {{ background: {p.accent}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: {p.panel}; border: 2px solid {p.accent};
    width: 14px; height: 14px; margin: -6px 0; border-radius: 9px;
}}
QSlider::handle:horizontal:hover {{ background: {p.accent}; }}
QSlider::sub-page:horizontal:disabled {{ background: {p.border}; }}
QSlider::handle:horizontal:disabled {{ border-color: {p.border}; }}

QProgressBar {{
    background: {p.inset}; border: 1px solid {p.border}; border-radius: 5px;
    height: 10px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 4px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p.muted}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
"""

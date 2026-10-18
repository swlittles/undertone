"""User settings, saved as JSON between runs."""

import json
from dataclasses import asdict, dataclass, fields

from .paths import SETTINGS_FILE


@dataclass
class Settings:
    theme: str = "system"  # system | light | dark
    shortcut_root: str = ""  # app folder the desktop shortcut was made for (Windows release)
    mode: str = "deep"  # deep | ai

    input_device: str = ""
    output_device: str = ""
    monitor_device: str = ""
    monitor: bool = False
    input_gain_db: float = 0.0
    output_gain_db: float = 0.0

    # Deep voice
    deep_preset: str = "Deeper"
    deep_pitch: float = -3.0  # semitones
    deep_formant: float = 0.92  # < 1 = bigger-sounding vocal tract
    deep_warmth: float = 2.0  # dB of low-shelf boost

    # AI voice
    ai_voice: str = ""  # path of a .pth relative to the voices folder
    ai_pitch: int = 0  # semitones
    ai_index_rate: float = 0.5
    ai_protect: float = 0.33
    ai_chunk_ms: int = 160
    ai_f0_method: str = "rmvpe"
    ai_gate_db: int = -50

    def save(self) -> None:
        SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> "Settings":
        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

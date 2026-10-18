"""AI voice replacement: RVC models run in real time through Applio's engine.

The speaker's words and timing are kept; the sound of the voice comes entirely
from the chosen voice model. Loading is slow (several seconds), so callers
should construct AIVoice off the UI thread.
"""

import os
import sys
import threading
import zipfile
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from ..audio.engine import SR
from ..paths import BASE_MODELS, ENGINE_DIR, VENDOR, VOICES, data_dir

_HF = "https://huggingface.co/IAHispano/Applio/resolve/main/Resources"
BASE_FILES = [
    # (path under BASE_MODELS, url, approximate MB)
    ("predictors/rmvpe.pt", f"{_HF}/predictors/rmvpe.pt", 181),
    ("predictors/fcpe.pt", f"{_HF}/predictors/fcpe.pt", 43),
    ("embedders/contentvec/pytorch_model.bin", f"{_HF}/embedders/contentvec/pytorch_model.bin", 378),
    ("embedders/contentvec/config.json", f"{_HF}/embedders/contentvec/config.json", 0),
]

CROSSFADE_S = 0.04


def missing_base_models() -> list[tuple[str, str, int]]:
    return [f for f in BASE_FILES if not (BASE_MODELS / f[0]).is_file()]


def download_base_models(progress: Callable[[float, str], None]) -> None:
    """Download whatever is missing. progress(fraction, label) is called often."""
    import requests

    todo = missing_base_models()
    total = sum(max(mb, 1) for _, _, mb in todo) * 1024 * 1024
    done = 0
    for rel, url, _ in todo:
        dest = BASE_MODELS / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_suffix(dest.suffix + ".part")
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(part, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    progress(min(done / total, 1.0), f"Downloading {Path(rel).name}")
        part.replace(dest)
    progress(1.0, "Base models ready")


# ---- voices folder --------------------------------------------------------


def list_voices() -> list[str]:
    """Voice models (.pth) under voices/, as paths relative to that folder."""
    VOICES.mkdir(parents=True, exist_ok=True)
    return sorted(
        str(p.relative_to(VOICES)).replace("\\", "/")
        for p in VOICES.rglob("*.pth")
        if not p.name.startswith(("D_", "G_"))  # training checkpoints, not voices
    )


def voice_label(rel: str) -> str:
    p = Path(rel)
    return p.parent.name if p.parent != Path(".") else p.stem


def index_for(rel: str) -> Optional[Path]:
    """The retrieval index that came with a voice, if any (same folder)."""
    pth = VOICES / rel
    candidates = sorted(pth.parent.glob("*.index"))
    if not candidates:
        return None
    stem = pth.stem.lower()
    for c in candidates:
        if stem in c.stem.lower():
            return c
    return candidates[0] if pth.parent != VOICES else None


def import_voice(src: str) -> str:
    """Copy a .pth (plus a sibling .index) or unpack a .zip into voices/. Returns its rel path."""
    import shutil

    src_path = Path(src)
    VOICES.mkdir(parents=True, exist_ok=True)
    if src_path.suffix.lower() == ".zip":
        dest = VOICES / src_path.stem
        dest.mkdir(exist_ok=True)
        with zipfile.ZipFile(src_path) as z:
            for member in z.infolist():
                name = Path(member.filename).name
                if name.lower().endswith((".pth", ".index")) and not name.startswith(("D_", "G_")):
                    with z.open(member) as fin, open(dest / name, "wb") as fout:
                        shutil.copyfileobj(fin, fout)
        found = sorted(dest.glob("*.pth"))
        if not found:
            raise ValueError("That zip has no .pth voice model in it.")
        return str(found[0].relative_to(VOICES)).replace("\\", "/")

    if src_path.suffix.lower() != ".pth":
        raise ValueError("Pick a .pth voice model or a .zip containing one.")
    dest = VOICES / src_path.stem
    dest.mkdir(exist_ok=True)
    shutil.copy2(src_path, dest / src_path.name)
    for idx in src_path.parent.glob("*.index"):
        if src_path.stem.lower() in idx.stem.lower() or len(list(src_path.parent.glob("*.index"))) == 1:
            shutil.copy2(idx, dest / idx.name)
    return f"{dest.name}/{src_path.name}"


# ---- engine -------------------------------------------------------------------

_import_lock = threading.Lock()


def _import_applio():
    """Applio resolves model paths (rvc/models/...) relative to the working directory."""
    with _import_lock:
        os.environ.setdefault("APPLIO_CONFIG_DIR", str(data_dir() / "applio"))
        ENGINE_DIR.mkdir(parents=True, exist_ok=True)
        os.chdir(ENGINE_DIR)
        if str(VENDOR) not in sys.path:
            sys.path.insert(0, str(VENDOR))
        import warnings

        warnings.filterwarnings("ignore")
        from rvc.realtime.core import VoiceChanger

        return VoiceChanger


def compute_device() -> str:
    """Human-readable name of what the AI will run on."""
    import torch

    if torch.cuda.is_available():
        return torch.cuda.get_device_name(0)
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "Apple GPU (Metal)"
    return "CPU (slow — no supported GPU found)"


class AIVoice:
    def __init__(self, voice_rel: str, chunk_ms: int = 160, f0_method: str = "rmvpe", gate_db: int = -50):
        import torch

        VoiceChanger = _import_applio()
        model = VOICES / voice_rel
        if not model.is_file():
            raise FileNotFoundError(f"Voice model not found: {voice_rel}")
        index = index_for(voice_rel)

        block = int(SR * chunk_ms / 1000)
        self.block_size = max(480, block - block % 480)
        self.pitch = 0
        self.index_rate = 0.5 if index else 0.0
        self.protect = 0.33
        self.has_index = index is not None
        extra = 1.5 if torch.cuda.is_available() else 1.0  # context the model sees each block

        self._vc = VoiceChanger(
            self.block_size, CROSSFADE_S, extra,
            model_path=str(model), index_path=str(index) if index else "",
            f0_method=f0_method, embedder_model="contentvec", silent_threshold=gate_db,
        )
        self.device = compute_device()
        self.warmup_ms = self._vc.warmup(**self._params())

    def _params(self) -> dict:
        return {
            "f0_up_key": int(self.pitch),
            "index_rate": float(self.index_rate) if self.has_index else 0.0,
            "protect": float(self.protect),
        }

    def set_params(self, pitch: int, index_rate: float, protect: float) -> None:
        self.pitch, self.index_rate, self.protect = pitch, index_rate, protect

    def set_gate(self, gate_db: int) -> None:
        self._vc.vc_model.input_sensitivity = 10 ** (gate_db / 20)

    def latency_ms(self) -> float:
        return CROSSFADE_S * 1000

    def reset(self) -> None:
        m = self._vc.vc_model
        for buf in (m.audio_buffer, m.convert_buffer, m.pitch_buffer, m.pitchf_buffer, self._vc.sola_buffer):
            buf.zero_()

    def process(self, x: np.ndarray) -> np.ndarray:
        y, _vol, _perf = self._vc.on_request(np.asarray(x, dtype=np.float32), **self._params())
        return y

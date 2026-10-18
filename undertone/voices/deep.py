"""Deeper version of your own voice: pitch and vocal size moved separately.

Cheap voice changers lower pitch and formants together, which sounds like a
slowed-down tape. A real deep voice is mostly lower pitch with a slightly
bigger vocal tract, so we lower the formants by much less than the pitch.
Rubber Band's R3 engine does the shifting with formant control in real time.
"""

import threading

import numpy as np
import pylibrb as rb
from scipy.signal import lfilter, lfilter_zi

from ..audio.engine import SR

PRESETS = {
    # name: (pitch semitones, formant factor, warmth dB)
    "Subtle": (-2.0, 0.96, 1.5),
    "Deeper": (-3.0, 0.92, 2.0),
    "Big": (-4.0, 0.89, 2.5),
    "Very deep": (-5.5, 0.86, 3.0),
}

_OPTIONS = int(
    rb.Option.PROCESS_REALTIME
    | rb.Option.ENGINE_FINER
    | rb.Option.WINDOW_SHORT
    | rb.Option.FORMANT_PRESERVED
    | rb.Option.CHANNELS_TOGETHER
)
_CUSHION = 512  # R3 emits audio in hops; hold this much back so output never runs dry


def low_shelf(freq: float, gain_db: float, sr: int = SR, slope: float = 0.8):
    """RBJ cookbook low-shelf biquad (b, a)."""
    a_lin = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * freq / sr
    alpha = np.sin(w0) / 2 * np.sqrt((a_lin + 1 / a_lin) * (1 / slope - 1) + 2)
    cos_w0 = np.cos(w0)
    sq = 2 * np.sqrt(a_lin) * alpha
    b = np.array([
        a_lin * ((a_lin + 1) - (a_lin - 1) * cos_w0 + sq),
        2 * a_lin * ((a_lin - 1) - (a_lin + 1) * cos_w0),
        a_lin * ((a_lin + 1) - (a_lin - 1) * cos_w0 - sq),
    ])
    a = np.array([
        (a_lin + 1) + (a_lin - 1) * cos_w0 + sq,
        -2 * ((a_lin - 1) + (a_lin + 1) * cos_w0),
        (a_lin + 1) + (a_lin - 1) * cos_w0 - sq,
    ])
    return b / a[0], a / a[0]


class DeepVoice:
    block_size = 480  # 10 ms

    def __init__(self, pitch: float = -3.0, formant: float = 0.92, warmth_db: float = 2.0):
        self._lock = threading.Lock()
        self.pitch, self.formant, self.warmth_db = pitch, formant, warmth_db
        self._rb = None
        self.reset()

    def set_params(self, pitch: float, formant: float, warmth_db: float) -> None:
        with self._lock:
            self.pitch, self.formant = pitch, formant
            if self._rb is not None:
                self._apply_scales()
            if warmth_db != self.warmth_db:
                self.warmth_db = warmth_db
                self._make_shelf()

    def _apply_scales(self) -> None:
        ratio = 2 ** (self.pitch / 12)
        self._rb.pitch_scale = ratio
        # Rubber Band's formant scale is relative to the pitch-shifted signal.
        self._rb.formant_scale = self.formant / ratio

    def _make_shelf(self) -> None:
        self._b, self._a = low_shelf(160.0, self.warmth_db)
        self._zi = lfilter_zi(self._b, self._a) * 0.0

    def reset(self) -> None:
        with self._lock:
            self._rb = rb.RubberBandStretcher(SR, 1, _OPTIONS, 1.0, 1.0)
            self._apply_scales()
            pad = self._rb.get_preferred_start_pad()
            self._skip = self._rb.get_start_delay()
            self._rb.process(np.zeros((1, pad), dtype=np.float32))
            self._pending = np.zeros(0, dtype=np.float32)
            self._primed = False
            self._make_shelf()

    def latency_ms(self) -> float:
        return measured_latency_ms()

    def process(self, x: np.ndarray) -> np.ndarray:
        n = len(x)
        with self._lock:
            self._rb.process(np.ascontiguousarray(x, dtype=np.float32)[None, :])
            avail = self._rb.available()
            if avail > 0:
                y = self._rb.retrieve(avail)[0]
                if self._skip:
                    cut = min(self._skip, len(y))
                    y, self._skip = y[cut:], self._skip - cut
                self._pending = np.concatenate([self._pending, y])

            if not self._primed and len(self._pending) >= n + _CUSHION:
                self._primed = True
            if not self._primed:
                return np.zeros(n, dtype=np.float32)
            out = self._pending[:n]
            self._pending = self._pending[n:]
            if len(out) < n:  # ran dry; rebuild the cushion
                self._primed = False
                out = np.concatenate([np.zeros(n - len(out), dtype=np.float32), out])

            if self.warmth_db:
                out, self._zi = lfilter(self._b, self._a, out, zi=self._zi)
            return np.clip(out, -1.0, 1.0).astype(np.float32)


_latency_ms = None


def measured_latency_ms() -> float:
    """Delay through the processor, found once by timing a click through it."""
    global _latency_ms
    if _latency_ms is None:
        d = DeepVoice(0.0, 1.0, 0.0)
        x = np.zeros(SR // 2, dtype=np.float32)
        x[SR // 8] = 1.0
        n = d.block_size
        y = np.concatenate([d.process(x[i : i + n]) for i in range(0, len(x) - n + 1, n)])
        _latency_ms = (int(np.argmax(np.abs(y))) - SR // 8) / SR * 1000
    return _latency_ms

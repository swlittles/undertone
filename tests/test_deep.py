import numpy as np
import pytest

from undertone.audio.engine import SR
from undertone.voices.deep import PRESETS, DeepVoice


def _voice_like(seconds=3.0, f0=140.0):
    """Harmonic-rich buzz through a couple of resonances: enough to track pitch and formants."""
    t = np.arange(int(seconds * SR)) / SR
    x = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 30))
    from scipy.signal import lfilter

    for fc, bw in ((700, 120), (1200, 150), (2600, 200)):
        r = np.exp(-np.pi * bw / SR)
        x = lfilter([1 - r], [1, -2 * r * np.cos(2 * np.pi * fc / SR), r * r], x)
    return (x / np.max(np.abs(x)) * 0.5).astype(np.float32)


def _run(d, x):
    n = d.block_size
    return np.concatenate([d.process(x[i : i + n]) for i in range(0, len(x) - n + 1, n)])


def _f0(y):
    seg = y[SR // 2 : SR // 2 + 8192] * np.hanning(8192)
    spec = np.abs(np.fft.rfft(seg, 8192 * 4))
    freqs = np.fft.rfftfreq(8192 * 4, 1 / SR)
    band = (freqs > 60) & (freqs < 400)
    # Strongest low harmonic ~ fundamental for this test signal.
    return freqs[band][np.argmax(spec[band])]


def test_output_length_and_level():
    d = DeepVoice(*PRESETS["Deeper"])
    x = _voice_like()
    y = _run(d, x)
    assert len(y) == len(x) - len(x) % d.block_size
    assert np.isfinite(y).all() and np.max(np.abs(y)) <= 1.0
    assert np.sqrt(np.mean(y[SR:] ** 2)) > 0.02  # not silent once primed


@pytest.mark.parametrize("semitones", [-3.0, -5.0])
def test_pitch_drops_by_requested_amount(semitones):
    x = _voice_like(f0=150.0)
    y = _run(DeepVoice(semitones, 0.92, 0.0), x)
    assert _f0(y) == pytest.approx(150.0 * 2 ** (semitones / 12), rel=0.03)


def test_latency_matches_report():
    d = DeepVoice(0.0, 1.0, 0.0)
    x = np.zeros(SR, dtype=np.float32)
    x[SR // 4] = 1.0  # click
    y = _run(d, x)
    delay_ms = (np.argmax(np.abs(y)) - SR // 4) / SR * 1000
    assert 0 < delay_ms < 80
    assert abs(delay_ms - d.latency_ms()) < 3


def test_live_parameter_change_does_not_break_stream():
    d = DeepVoice(-2.0, 0.95, 1.0)
    x = _voice_like()
    half = len(x) // 2 - (len(x) // 2) % d.block_size
    a = _run(d, x[:half])
    d.set_params(-5.0, 0.86, 3.0)
    b = _run(d, x[half:])
    assert np.isfinite(b).all() and np.sqrt(np.mean(b[SR // 2 :] ** 2)) > 0.02

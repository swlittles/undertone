"""Runs only when the shared models are downloaded and a test voice is given:
UNDERTONE_TEST_VOICE=path/to/voice.pth pytest tests/test_ai.py"""

import os
import shutil
import time

import numpy as np
import pytest

from undertone.audio.engine import SR
from undertone.paths import VOICES
from undertone.voices import ai

VOICE = os.environ.get("UNDERTONE_TEST_VOICE")
pytestmark = pytest.mark.skipif(
    not VOICE or ai.missing_base_models(), reason="needs UNDERTONE_TEST_VOICE and downloaded base models"
)


@pytest.fixture(scope="module")
def voice():
    rel = ai.import_voice(VOICE)
    yield ai.AIVoice(rel, chunk_ms=200)
    shutil.rmtree(VOICES / rel.split("/")[0], ignore_errors=True)


def test_converts_speech_in_real_time(voice):
    t = np.arange(SR * 3) / SR
    # Vowel-ish buzz with syllable-rate amplitude modulation.
    x = (0.3 * np.sign(np.sin(2 * np.pi * 130 * t)) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)
    n = voice.block_size
    times, out = [], []
    for i in range(0, len(x) - n + 1, n):
        t0 = time.perf_counter()
        out.append(voice.process(x[i : i + n]))
        times.append(time.perf_counter() - t0)
    y = np.concatenate(out)
    assert len(y) == len(out) * n and np.isfinite(y).all()
    assert np.sqrt(np.mean(y**2)) > 0.01
    assert np.median(times) < n / SR  # faster than real time


def test_noise_gate_silences_quiet_input(voice):
    voice.set_gate(-30)
    y = voice.process(np.full(voice.block_size, 1e-4, dtype=np.float32))
    voice.set_gate(-50)
    assert np.max(np.abs(y)) < 1e-3

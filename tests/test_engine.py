import threading
import time

import numpy as np

from undertone.audio.engine import SR, AudioEngine, Fifo


def test_fifo_roundtrip_and_wraparound():
    f = Fifo(capacity=10)
    f.write(np.arange(6, dtype=np.float32))
    assert list(f.read(4)) == [0, 1, 2, 3]
    f.write(np.arange(6, 14, dtype=np.float32))  # wraps past the end
    assert len(f) == 10
    assert list(f.read(10)) == [4, 5, *range(6, 14)]
    assert len(f.read(5)) == 0


def test_fifo_overflow_drops_oldest():
    f = Fifo(capacity=4)
    f.write(np.arange(6, dtype=np.float32))
    assert list(f.read(4)) == [2, 3, 4, 5]


def test_fifo_discard_to():
    f = Fifo(capacity=16)
    f.write(np.arange(10, dtype=np.float32))
    assert f.discard_to(3) == 7
    assert list(f.read(3)) == [7, 8, 9]


class Halver:
    block_size = 960

    def __init__(self):
        self.calls = 0

    def process(self, x):
        self.calls += 1
        return x * 0.5

    def latency_ms(self):
        return 0.0

    def reset(self):
        pass


def _run_worker(engine, proc, n_samples):
    engine.set_processor(proc)
    engine.running = True
    t = threading.Thread(target=engine._run, daemon=True)
    t.start()
    x = np.random.default_rng(0).uniform(-1, 1, n_samples).astype(np.float32)
    for i in range(0, n_samples, 480):  # like the 10 ms input callback
        engine.in_fifo.write(x[i : i + 480])
        time.sleep(0.001)
    time.sleep(0.2)
    engine.running = False
    t.join(1)
    return x


def test_worker_processes_in_processor_blocks():
    e = AudioEngine()
    proc = Halver()
    x = _run_worker(e, proc, 960 * 5)
    assert proc.calls == 5
    y = e.out.fifo.read(len(e.out.fifo))
    # Output is bounded to the backlog limit, and is the most recent processed audio.
    assert 0 < len(y) <= e.out.max_backlog(960)
    np.testing.assert_allclose(y, x[-len(y):] * 0.5, atol=1e-6)


def test_bypass_and_errors_pass_dry_voice():
    class Broken(Halver):
        def process(self, x):
            raise RuntimeError("boom")

    e = AudioEngine()
    x = _run_worker(e, Broken(), 960 * 2)
    assert "boom" in e.error
    y = e.out.fifo.read(len(e.out.fifo))
    np.testing.assert_allclose(y, x[-len(y):], atol=1e-6)


def test_capture_records_dry_and_wet():
    e = AudioEngine()
    e.begin_capture(960 * 3 / SR)
    _run_worker(e, Halver(), 960 * 4)
    dry, wet = e.capture_result()
    assert len(dry) == len(wet) >= 960 * 3
    np.testing.assert_allclose(wet, dry * 0.5, atol=1e-6)


def test_player_primes_then_reports_underrun():
    e = AudioEngine()
    p = e.out
    p.cushion = 480
    out = np.ones((480, 1), dtype=np.float32)
    p.callback(out, 480, None, None)
    assert not out.any()  # waits for the cushion
    p.fifo.write(np.ones(720, dtype=np.float32))
    p.callback(out, 480, None, None)
    assert out.all()
    p.callback(out, 480, None, None)  # only 240 left
    assert p.underruns == 1 and out[:240].all() and not out[240:].any()

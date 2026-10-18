"""Real-time audio: mic in, processed voice out to a virtual cable, optional monitor.

The input callback only queues samples. A worker thread runs the voice
processor in the block size it asks for, and the output callbacks drain what
the worker produced. Keeping heavy work off the device callbacks means a slow
block causes a short gap instead of glitching the audio driver.
"""

import sys
import threading
import time
from typing import Optional, Protocol

import numpy as np
import sounddevice as sd

SR = 48000
DEVICE_BLOCK = 480  # 10 ms device callbacks


class Processor(Protocol):
    block_size: int  # samples per process() call, at SR

    def process(self, x: np.ndarray) -> np.ndarray: ...

    def latency_ms(self) -> float: ...  # delay the algorithm itself adds

    def reset(self) -> None: ...


class Fifo:
    """Thread-safe mono float32 queue."""

    def __init__(self, capacity: int = SR * 4):
        self._buf = np.zeros(capacity, dtype=np.float32)
        self._start = 0
        self._len = 0
        self._lock = threading.Lock()
        self.ready = threading.Condition(self._lock)

    def __len__(self) -> int:
        return self._len

    def clear(self) -> None:
        with self._lock:
            self._start = self._len = 0

    def write(self, x: np.ndarray) -> None:
        cap = len(self._buf)
        x = np.asarray(x, dtype=np.float32)[-cap:]
        with self._lock:
            overflow = self._len + len(x) - cap
            if overflow > 0:  # drop the oldest audio rather than block
                self._start = (self._start + overflow) % cap
                self._len -= overflow
            end = (self._start + self._len) % cap
            first = min(len(x), cap - end)
            self._buf[end : end + first] = x[:first]
            self._buf[: len(x) - first] = x[first:]
            self._len += len(x)
            self.ready.notify_all()

    def read(self, n: int) -> np.ndarray:
        """Return up to n samples (fewer if not enough are queued)."""
        cap = len(self._buf)
        with self._lock:
            n = min(n, self._len)
            idx = (self._start + np.arange(n)) % cap
            out = self._buf[idx]
            self._start = (self._start + n) % cap
            self._len -= n
            return out

    def discard_to(self, keep: int) -> int:
        """Drop the oldest samples so at most `keep` remain. Returns how many were dropped."""
        cap = len(self._buf)
        with self._lock:
            drop = max(0, self._len - keep)
            self._start = (self._start + drop) % cap
            self._len -= drop
            return drop

    def wait_for(self, n: int, timeout: float) -> bool:
        with self.ready:
            return self.ready.wait_for(lambda: self._len >= n, timeout)


class Player:
    """Drains a Fifo into an output device, holding back a small cushion against jitter."""

    def __init__(self, cushion: int):
        self.fifo = Fifo()
        self.cushion = cushion
        self.primed = False
        self.underruns = 0
        self.gain = 1.0
        self.peak = 0.0

    def max_backlog(self, block: int) -> int:
        return block + self.cushion + 4 * DEVICE_BLOCK

    def callback(self, outdata, frames, _time, _status):
        if not self.primed and len(self.fifo) >= self.cushion:
            self.primed = True
        if not self.primed:
            outdata.fill(0)
            return
        y = self.fifo.read(frames) * self.gain
        if len(y) < frames:
            self.underruns += 1
            self.primed = False
            y = np.concatenate([y, np.zeros(frames - len(y), dtype=np.float32)])
        self.peak = max(self.peak * 0.8, float(np.max(np.abs(y))) if len(y) else 0.0)
        outdata[:] = y[:, None]


def _host_api_name(dev) -> str:
    return sd.query_hostapis(dev["hostapi"])["name"]


def _preferred_host_api() -> Optional[str]:
    if sys.platform == "win32":
        return "Windows WASAPI"  # lowest latency without exclusive-mode drivers
    if sys.platform == "darwin":
        return "Core Audio"
    return None


def list_devices(kind: str) -> list[str]:
    """Names of usable input or output devices on the preferred host API."""
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    want = _preferred_host_api()
    names = []
    for dev in sd.query_devices():
        if dev[key] > 0 and (want is None or _host_api_name(dev) == want):
            if dev["name"] not in names:
                names.append(dev["name"])
    return names


def find_device(name: str, kind: str) -> Optional[int]:
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    want = _preferred_host_api()
    for dev in sd.query_devices():
        if dev["name"] == name and dev[key] > 0 and (want is None or _host_api_name(dev) == want):
            return dev["index"]
    return None


def default_device(kind: str) -> str:
    try:
        idx = sd.default.device[0 if kind == "input" else 1]
        name = sd.query_devices(idx)["name"]
    except Exception:
        name = ""
    names = list_devices(kind)
    if name in names:
        return name
    # Default device may live on another host API; match by prefix.
    for n in names:
        if name and (n.startswith(name) or name.startswith(n)):
            return n
    return names[0] if names else ""


def find_virtual_cable() -> Optional[str]:
    """Output side of a virtual cable that apps can pick as a microphone."""
    for name in list_devices("output"):
        low = name.lower()
        if "cable input" in low or "blackhole" in low or "voicemeeter input" in low:
            return name
    return None


def _extra_settings():
    if sys.platform == "win32":
        # Let WASAPI convert rate/channels so 44.1 kHz devices still open at 48 kHz.
        return sd.WasapiSettings(auto_convert=True)
    return None


def _channels(index: int, kind: str) -> int:
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    return max(1, min(2, int(sd.query_devices(index)[key])))


class AudioEngine:
    def __init__(self):
        self.processor: Optional[Processor] = None
        self.running = False
        self.bypass = False
        self.input_gain = 1.0
        self.error: Optional[str] = None

        self.in_fifo = Fifo()
        self.out = Player(cushion=DEVICE_BLOCK)
        self.mon = Player(cushion=DEVICE_BLOCK)
        self.monitor_enabled = False

        self.in_peak = 0.0
        self.proc_ms = 0.0
        self.device_latency_ms = 0.0

        self._streams: list = []
        self._worker: Optional[threading.Thread] = None
        self._capture: Optional[dict] = None
        self._lock = threading.Lock()

    # ---- lifecycle -------------------------------------------------------

    def start(self, input_name: str, output_name: str, monitor_name: str, processor: Processor) -> None:
        self.stop()
        inp = find_device(input_name, "input")
        out = find_device(output_name, "output")
        if inp is None:
            raise RuntimeError(f"Microphone not found: {input_name or '(none)'}")
        if out is None:
            raise RuntimeError(f"Output device not found: {output_name or '(none)'}")
        mon = find_device(monitor_name, "output") if monitor_name else None

        self.error = None
        self.in_fifo.clear()
        self.set_processor(processor)
        extra = _extra_settings()
        in_ch = _channels(inp, "input")

        def in_cb(indata, frames, _time, _status):
            x = indata.mean(axis=1) if indata.shape[1] > 1 else indata[:, 0]
            x = x * self.input_gain
            self.in_peak = max(self.in_peak * 0.8, float(np.max(np.abs(x))))
            self.in_fifo.write(x)

        def out_stream(index, player):
            ch = _channels(index, "output")

            def cb(outdata, frames, t, status):
                buf = np.empty((frames, 1), dtype=np.float32)
                player.callback(buf, frames, t, status)
                outdata[:] = buf if ch == 1 else np.repeat(buf, ch, axis=1)

            return sd.OutputStream(
                samplerate=SR, blocksize=DEVICE_BLOCK, device=index, channels=ch,
                dtype="float32", latency="low", callback=cb, extra_settings=extra,
            )

        try:
            streams = [
                sd.InputStream(
                    samplerate=SR, blocksize=DEVICE_BLOCK, device=inp, channels=in_ch,
                    dtype="float32", latency="low", callback=in_cb, extra_settings=extra,
                ),
                out_stream(out, self.out),
            ]
            if mon is not None and mon != out:
                streams.append(out_stream(mon, self.mon))
        except Exception as e:
            raise RuntimeError(f"Could not open audio device: {e}") from e

        self.running = True
        self._worker = threading.Thread(target=self._run, name="undertone-dsp", daemon=True)
        self._worker.start()
        for s in streams:
            s.start()
        self._streams = streams
        self.device_latency_ms = 1000 * (streams[0].latency + streams[1].latency)

    def stop(self) -> None:
        self.running = False
        for s in self._streams:
            try:
                s.abort()
                s.close()
            except Exception:
                pass
        self._streams = []
        with self.in_fifo.ready:
            self.in_fifo.ready.notify_all()
        if self._worker is not None:
            self._worker.join(timeout=2)
            self._worker = None
        for p in (self.out, self.mon):
            p.fifo.clear()
            p.primed = False
        self.in_peak = self.out.peak = self.mon.peak = 0.0

    def set_processor(self, processor: Processor) -> None:
        with self._lock:
            processor.reset()
            self.processor = processor
            # AI blocks arrive in big chunks; keep a cushion so playback doesn't stutter
            # while the next one is computed.
            cushion = DEVICE_BLOCK * (2 if processor.block_size <= 2048 else 3)
            self.out.cushion = self.mon.cushion = cushion

    # ---- worker ----------------------------------------------------------

    def _run(self) -> None:
        while self.running:
            with self._lock:
                proc = self.processor
            n = proc.block_size
            if not self.in_fifo.wait_for(n, timeout=0.2):
                continue
            x = self.in_fifo.read(n)
            # If we fell behind (slow GPU, long stall), skip ahead instead of lagging forever.
            self.in_fifo.discard_to(n * 2)
            t = time.perf_counter()
            if self.bypass:
                y = x
            else:
                try:
                    y = np.asarray(proc.process(x), dtype=np.float32)
                except Exception as e:  # keep the call alive with the dry voice
                    self.error = f"{type(e).__name__}: {e}"
                    y = x
            ms = (time.perf_counter() - t) * 1000
            self.proc_ms = ms if self.proc_ms == 0 else self.proc_ms * 0.9 + ms * 0.1

            self.out.fifo.write(y)
            self.out.fifo.discard_to(self.out.max_backlog(n))
            if self.monitor_enabled:
                self.mon.fifo.write(y)
                self.mon.fifo.discard_to(self.mon.max_backlog(n))
            self._feed_capture(x, y)

    # ---- stats -----------------------------------------------------------

    def latency_ms(self) -> float:
        """Rough mic-to-output delay: block wait + compute + cushion + algorithm + drivers."""
        if not self.running or self.processor is None:
            return 0.0
        block = self.processor.block_size / SR * 1000
        cushion = self.out.cushion / SR * 1000
        return block + self.proc_ms + cushion + self.processor.latency_ms() + self.device_latency_ms

    def load(self) -> float:
        """Fraction of real time spent processing; above ~0.8 audio will break up."""
        if not self.processor:
            return 0.0
        return self.proc_ms / (self.processor.block_size / SR * 1000)

    # ---- voice test (record, then play back) ------------------------------

    def begin_capture(self, seconds: float) -> None:
        self._capture = {"need": int(seconds * SR), "dry": [], "wet": [], "have": 0, "done": False}

    def capture_progress(self) -> float:
        c = self._capture
        return 0.0 if c is None else min(1.0, c["have"] / c["need"])

    def capture_result(self) -> Optional[tuple[np.ndarray, np.ndarray]]:
        c = self._capture
        if c is None or not c["done"]:
            return None
        return np.concatenate(c["dry"]), np.concatenate(c["wet"])

    def _feed_capture(self, x, y) -> None:
        c = self._capture
        if c is None or c["done"]:
            return
        c["dry"].append(x.copy())
        c["wet"].append(y.copy())
        c["have"] += len(x)
        if c["have"] >= c["need"]:
            c["done"] = True


def play(audio: np.ndarray, device_name: str) -> None:
    """Play a clip (non-blocking) on the named output, or the system default."""
    idx = find_device(device_name, "output") if device_name else None
    if idx is None:
        sd.play(audio, SR)
    else:
        sd.play(audio, SR, device=idx, extra_settings=_extra_settings())


def stop_playback() -> None:
    sd.stop()

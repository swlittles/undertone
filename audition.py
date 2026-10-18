"""Render deeper-voice variants of a recording so you can judge realism offline.

Usage:
    python audition.py --record 15          # record 15 s from the default mic, then render
    python audition.py my_voice.wav         # render from an existing recording
    python audition.py my_voice.wav --pitch -4 --formant 0.9   # one custom variant

Each variant lowers pitch (how low the voice is) and formants (how big the
vocal tract sounds) independently. Cheap voice changers move both by the same
amount, which is what makes them sound like a slowed-down tape.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

import warnings

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
import pyworld  # noqa: E402

SR = 48000

# (name, pitch semitones, formant factor). Formant factor < 1 = larger-sounding speaker.
PRESETS = [
    ("01_subtle", -2.0, 0.95),
    ("02_deeper", -3.0, 0.92),
    ("03_big", -4.0, 0.90),
    ("04_very_deep", -5.0, 0.87),
    ("05_pitch_only", -4.0, 1.00),  # formants untouched: shows why pitch alone sounds off
    ("06_cheap_changer", -4.0, 2 ** (-4 / 12)),  # both moved together, like most apps
]


def record(seconds: float) -> np.ndarray:
    import sounddevice as sd

    print(f"Recording {seconds:.0f} s — talk normally, like you would in a game...")
    audio = sd.rec(int(seconds * SR), samplerate=SR, channels=1, dtype="float64")
    sd.wait()
    print("Done.")
    return audio[:, 0]


def warp_envelope(sp: np.ndarray, factor: float) -> np.ndarray:
    """Move formant peaks to `factor` times their frequency."""
    if factor == 1.0:
        return sp
    bins = sp.shape[1]
    src = np.arange(bins) / factor  # new(f) = old(f / factor)
    src = np.clip(src, 0, bins - 1)
    lo = np.floor(src).astype(int)
    hi = np.minimum(lo + 1, bins - 1)
    frac = src - lo
    # Interpolate in the log domain so peaks keep their shape.
    log_sp = np.log(np.maximum(sp, 1e-16))
    return np.exp(log_sp[:, lo] * (1 - frac) + log_sp[:, hi] * frac)


def analyse(x: np.ndarray, sr: int):
    x = np.ascontiguousarray(x, dtype=np.float64)
    f0, t = pyworld.harvest(x, sr, f0_floor=50.0, f0_ceil=600.0)
    sp = pyworld.cheaptrick(x, f0, t, sr)
    ap = pyworld.d4c(x, f0, t, sr)
    return f0, sp, ap


def render(f0, sp, ap, sr, semitones: float, formant: float) -> np.ndarray:
    env = np.ascontiguousarray(warp_envelope(sp, formant))
    y = pyworld.synthesize(f0 * 2 ** (semitones / 12), env, ap, sr)
    peak = np.max(np.abs(y))
    return y / peak * 0.9 if peak > 0 else y


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", nargs="?", help="WAV/FLAC file of your voice")
    p.add_argument("--record", type=float, metavar="SECONDS", help="record from the mic instead")
    p.add_argument("--pitch", type=float, help="custom variant: semitones (e.g. -4)")
    p.add_argument("--formant", type=float, help="custom variant: formant factor (e.g. 0.9)")
    p.add_argument("--out", default="out", help="output folder (default: out)")
    a = p.parse_args()

    out = Path(a.out)
    out.mkdir(exist_ok=True)

    if a.record:
        x, sr = record(a.record), SR
        sf.write(out / "00_original.wav", x, sr)
    elif a.input:
        x, sr = sf.read(a.input, dtype="float64", always_2d=True)
        x = x.mean(axis=1)
        sf.write(out / "00_original.wav", x, sr)
    else:
        p.error("give an input file or --record SECONDS")

    presets = PRESETS
    if a.pitch is not None or a.formant is not None:
        pitch = a.pitch if a.pitch is not None else 0.0
        formant = a.formant if a.formant is not None else 1.0
        presets = [(f"custom_p{pitch:+g}_f{formant:g}", pitch, formant)]

    print("Analysing voice...")
    f0, sp, ap = analyse(x, sr)
    for name, semis, formant in presets:
        path = out / f"{name}.wav"
        sf.write(path, render(f0, sp, ap, sr, semis, formant), sr)
        print(f"  {path}  (pitch {semis:+g} st, formant x{formant:.2f})")
    print(f"\nListen to {out}/ and note which (if any) sounds like a real person.")


if __name__ == "__main__":
    sys.exit(main())

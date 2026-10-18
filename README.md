# Undertone

A voice changer aimed at sounding like a real person, not a filter.

## Step 1: deeper-voice audition (offline)

Before building anything real-time, check whether a deeper version of your own
voice can sound real. This renders several variants of a recording so you can
compare them.

### Windows setup (once)

1. Install Python 3.12 from python.org (tick "Add python.exe to PATH").
2. In PowerShell, from this folder:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### Run

```powershell
.venv\Scripts\python audition.py --record 15
```

Talk normally for 15 seconds, like you would in a game. The variants land in `out\`:

| File | Pitch | Formants | What it tests |
|---|---|---|---|
| `00_original` | — | — | your voice, for reference |
| `01_subtle` | -2 st | x0.95 | slightly deeper |
| `02_deeper` | -3 st | x0.92 | clearly deeper |
| `03_big` | -4 st | x0.90 | bigger-sounding person |
| `04_very_deep` | -5 st | x0.87 | as far as it goes before it sounds fake |
| `05_pitch_only` | -4 st | x1.00 | why lowering pitch alone sounds wrong |
| `06_cheap_changer` | -4 st | x0.79 | what most voice changer apps do |

Try your own mix with `--pitch -3.5 --formant 0.91`, or pass an existing
recording instead of `--record`: `python audition.py my_voice.wav`.

Use a decent mic in a quiet room. Background noise and room echo make every
variant sound worse.

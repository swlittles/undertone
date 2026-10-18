#!/bin/bash
# macOS / Linux setup. Needs Python 3.12 (brew install python@3.12).
set -euo pipefail
cd "$(dirname "$0")"
PY=$(command -v python3.12 || true)
[ -z "$PY" ] && { echo "Python 3.12 not found. On a Mac: brew install python@3.12"; exit 1; }
[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install torch==2.11.0 torchaudio==2.11.0
.venv/bin/python -m pip install -r requirements.txt
echo
echo "Done. Start with ./run.sh"
echo "For apps to hear the changed voice on a Mac, install BlackHole: https://existential.audio/blackhole/"

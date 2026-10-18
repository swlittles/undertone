# Undertone

A voice changer that tries to sound like a real person, not a filter. Two modes:

- **Deep voice**: your own voice, lower and bigger. Pitch and vocal size (formants) move
  separately, which is what makes it sound like a deeper-voiced person rather than a
  slowed-down recording. About 100 ms of delay, runs on any CPU.
- **AI voice**: replaces your voice with an RVC voice model. You still do the talking;
  the voice people hear is the model's. Needs a decent NVIDIA GPU for low delay.

## Windows setup

1. Download the latest **Undertone-…-windows.zip** from
   [Releases](https://github.com/swlittles/undertone/releases).
2. Right-click it, choose **Extract All…**, and open the extracted folder.
3. Double-click **Undertone.bat**. It has its own Python, so there's nothing else to
   install. The first launch puts an **Undertone** shortcut on your desktop. If
   SmartScreen warns you, click **More info → Run anyway**.
4. Install the free [VB-Cable](https://vb-audio.com/Cable/) virtual audio cable and reboot.
   This is the "virtual microphone" that Discord and games listen to.
5. In Undertone (the **Setup** guide in the app walks through this and opens by itself
   the first time):
   - **Microphone**: your real mic.
   - **Send changed voice to**: `CABLE Input (VB-Audio Virtual Cable)`.
   - In Discord / your game, set the input device to `CABLE Output (VB-Audio Virtual Cable)`.
   - Press **Start**.

Undertone updates itself: when a new release is out, a banner offers **Update**, which
downloads it in the background and installs it when you restart or close the app.
Settings, voices and downloads live in `%APPDATA%\Undertone` and
`%LOCALAPPDATA%\Undertone`, so updates never touch them. (Versions before 0.2.1 need
one manual update: download the new zip, extract it and run **Undertone.bat** from the
new folder; the desktop shortcut moves to it and you can delete the old folder.)

If something goes wrong, run **Undertone (debug).bat** to see errors, or read
`%APPDATA%\Undertone\undertone.log`.

<details>
<summary>Running from a git checkout instead</summary>

`git clone https://github.com/swlittles/undertone.git`, then double-click
**install.bat** (installs Python 3.12 via winget if needed, PyTorch and everything
else into `.venv`). **update.bat** pulls the latest code.
</details>

## Trying the two modes

**Test my voice** records 6 seconds while you're live and lets you play back your real
voice and the changed one. That's the quickest way to judge realism. Talk like you do
in game, not like you're reading.

### Deep voice
Start with the **Deeper** or **Big** preset. If it sounds fake, lower **Vocal size**
less, not more: real deep voices get most of their depth from pitch. **Warmth** adds
low-end body.

### AI voice
1. Click **Download** in the AI voice panel once. On the release build that's the AI
   engine (PyTorch, about 2.6 GB for NVIDIA GPUs) plus 600 MB of shared models.
2. Click **Add voice…** and pick a voice model: an RVC v2 `.pth` file, or a `.zip`
   containing one (and ideally its `.index` file). Pick a voice you have permission to
   use. Many free models are of real people, so look for an original voice, or train
   your own from recordings of someone who agrees to it (Applio can do this).
3. Press **Start**. The first load takes a few seconds.
4. Settings:
   - **Pitch shift**: move your pitch into the voice's range (0 for a same-gender voice).
   - **Latency**: chunk size. Lower means less delay but more GPU work. On an RTX card
     try 80–120 ms. If the status line says "too slow", raise it.
   - **Voice match**: how strongly to pull toward the model's voice (needs the `.index`).
   - **Noise gate**: stops fan and keyboard noise turning into voice.

### About delay
The status line shows the estimated mic-to-output delay. People you talk to can't hear
it: they never hear your real voice to compare, and Discord and games already add
100 ms or more. You'll only notice it if you turn on **Hear myself**, so leave that
off while playing.

## Mac

`./install.sh`, then `./run.sh`. Use [BlackHole](https://existential.audio/blackhole/)
instead of VB-Cable. AI voice runs on the Apple GPU but is slower than on an NVIDIA card.

## Development

```bash
.venv/bin/python -m pytest          # unit tests
UNDERTONE_TEST_VOICE=/path/to/voice.pth .venv/bin/python -m pytest tests/test_ai.py
```

Releases: push a tag matching `undertone/__init__.py`'s `__version__` (e.g. `v0.2.0`).
`.github/workflows/release.yml` builds the portable zip on Windows
(`scripts/build_windows.ps1`: embeddable Python plus `requirements.txt`, no PyTorch),
tests it (`scripts/test_windows.ps1`), and publishes the release. The app downloads
PyTorch into `%LOCALAPPDATA%\Undertone\rt` on first use (`undertone/runtime.py`).
Installed copies find the release through the GitHub API and update themselves
(`undertone/updater.py`, `undertone/assets/apply_update.ps1`), so every release needs
the `Undertone-<version>-windows.zip` asset the workflow uploads.

Layout: `undertone/audio/engine.py` (devices, buffering, worker thread),
`undertone/voices/deep.py` (Rubber Band pitch + formant), `undertone/voices/ai.py`
(RVC through the vendored Applio engine in `vendor/`), `undertone/ui/` (Qt GUI and theme).

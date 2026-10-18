# Undertone

A voice changer that tries to sound like a real person, not a filter. Two modes:

- **Deep voice**: your own voice, lower and bigger. Pitch and vocal size (formants) move
  separately, which is what makes it sound like a deeper-voiced person rather than a
  slowed-down recording. About 100 ms of delay, runs on any CPU.
- **AI voice**: replaces your voice with an RVC voice model. You still do the talking;
  the voice people hear is the model's. Needs a decent NVIDIA GPU for low delay.

## Windows setup

1. Install [Git](https://git-scm.com/download/win) if you don't have it, then:
   ```powershell
   git clone https://github.com/swlittles/undertone.git
   cd undertone
   ```
2. Double-click **install.bat**. It installs Python 3.12 if needed (via winget), PyTorch
   (CUDA build if it finds an NVIDIA GPU, about 3 GB) and everything else, then puts an
   **Undertone** shortcut on your desktop.
3. Install the free [VB-Cable](https://vb-audio.com/Cable/) virtual audio cable and reboot.
   This is the "virtual microphone" that Discord and games listen to.
4. Open Undertone:
   - **Microphone**: your real mic.
   - **Send changed voice to**: `CABLE Input (VB-Audio Virtual Cable)`.
   - In Discord / your game, set the input device to `CABLE Output (VB-Audio Virtual Cable)`.
   - Press **Start**.

To update later: double-click **update.bat**. If something goes wrong, run
**Undertone (debug).bat** to see errors, or read `%APPDATA%\Undertone\undertone.log`.

## Trying the two modes

**Test my voice** records 6 seconds while you're live and lets you play back your real
voice and the changed one. That's the quickest way to judge realism. Talk like you do
in game, not like you're reading.

### Deep voice
Start with the **Deeper** or **Big** preset. If it sounds fake, lower **Vocal size**
less, not more: real deep voices get most of their depth from pitch. **Warmth** adds
low-end body.

### AI voice
1. Click **Download** in the AI voice panel once (about 600 MB of shared models).
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

Layout: `undertone/audio/engine.py` (devices, buffering, worker thread),
`undertone/voices/deep.py` (Rubber Band pitch + formant), `undertone/voices/ai.py`
(RVC through the vendored Applio engine in `vendor/`), `undertone/ui/` (Qt GUI and theme).

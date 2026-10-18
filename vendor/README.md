# vendor/rvc

A trimmed copy of the real-time RVC engine from [Applio](https://github.com/IAHispano/Applio)
(MIT licence, see `LICENSE-Applio`), taken at commit `5379cf261fa7d8085c3b077aa42dabca7c85310b`.
Only the modules the real-time path imports are included; training, the web UI and
TTS are left out.

Local changes:

- `rvc/lib/predictors/Swift.py`: `onnxruntime` is imported when the SWIFT predictor
  is used instead of at module load, so it isn't a hard dependency.

Shared models (`rvc/models/`) are downloaded by the app on first use and aren't committed.
Applio resolves paths relative to the working directory, so Undertone changes into this
folder before loading the engine (`undertone/voices/ai.py`).

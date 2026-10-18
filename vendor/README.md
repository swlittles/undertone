# vendor/rvc

A trimmed copy of the real-time RVC engine from [Applio](https://github.com/IAHispano/Applio)
(MIT licence, see `LICENSE-Applio`), taken at commit `5379cf261fa7d8085c3b077aa42dabca7c85310b`.
Only the modules the real-time path imports are included; training, the web UI and
TTS are left out.

Local changes:

- `rvc/lib/predictors/Swift.py`: `onnxruntime` is imported when the SWIFT predictor
  is used instead of at module load, so it isn't a hard dependency.

Applio opens its shared models as `rvc/models/...` relative to the working directory.
Undertone downloads them to `<local app data>/Undertone/engine/rvc/models/` and changes
into that folder before loading the engine (`undertone/voices/ai.py`), with this folder
on `sys.path` for the code.

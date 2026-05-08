# Simple Player Example

Windows desktop video player example for `ffmpeg-pywrapper`.

Install player dependencies:

```powershell
uv sync --extra player --group player
```

Run:

```powershell
uv run --extra player --group player python examples/simple_player/main.py
```

The example opens local `.mp4`, `.mkv`, `.mov`, `.avi`, and `.webm` files. It
uses PySide6 for the GUI and PyAV/sounddevice for FFmpeg-backed decoding and
audio output.

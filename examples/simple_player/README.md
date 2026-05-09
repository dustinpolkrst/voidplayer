# VoidPlayer Example

Windows desktop video player example for `VoidPlayer`.

Install player dependencies:

```powershell
uv sync --extra player --group player
```

Run:

```powershell
uv run --extra player --group player python examples/simple_player/main.py
```

Run with a bundled or custom theme:

```powershell
uv run --extra player --group player python examples/simple_player/main.py --theme default
uv run --extra player --group player python examples/simple_player/main.py --theme-path C:\path\to\theme
```

Themes live in `examples/simple_player/themes`. Community themes should edit
`theme.toml` tokens and keep the matching `style.qss` selectors intact.

The example opens local `.mp4`, `.mkv`, `.mov`, `.avi`, and `.webm` files. It
uses PySide6 for the GUI and PyAV/sounddevice for FFmpeg-backed decoding and
audio output.

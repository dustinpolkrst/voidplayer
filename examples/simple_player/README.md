# VoidPlayer Example

Compatibility wrapper for the packaged `VoidPlayer` desktop app.

Install dependencies:

```powershell
uv sync
```

Run:

```powershell
uv run voidplayer
uv run python examples/simple_player/main.py
```

Run with a bundled or custom theme:

```powershell
uv run voidplayer --theme default
uv run voidplayer --theme-path C:\path\to\theme
```

Themes live in `src/ffmpeg_pywrapper/player/themes`. Community themes should edit
`theme.toml` tokens and keep the matching `style.qss` selectors intact.

The example opens local `.mp4`, `.mkv`, `.mov`, `.avi`, and `.webm` files. It
uses PySide6 for the GUI and PyAV/sounddevice for FFmpeg-backed decoding and
audio output.

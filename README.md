# VoidPlayer

<img width="1165" height="839" alt="image" src="https://github.com/user-attachments/assets/9620ea0c-e537-4495-b806-bbc0bf5699c1" />

<br>
<br>

VoidPlayer is a hackable anime streaming client built with PySide6, FFmpeg,
PyAV, and sounddevice. It is designed to be easy to inspect, modify, and theme
while still opening directly into a polished anime home screen with search,
sub/dub mode selection, continue watching, resume timestamps, next-episode
playback, and bundled dark themes.

The original `ffmpeg_pywrapper` package and `ffmpeg-pywrapper` CLI remain
available for scripting and compatibility, but the main product experience is
now the anime player.

## What The App Does

- Starts on an anime home screen instead of a generic media-player canvas.
- Searches anime from inside the app.
- Supports sub and dub search modes.
- Resolves fast playable anime streams.
- Plays hardsubbed/built-in subtitle streams when the selected source provides
  them.
- Saves anime watch history for continue watching.
- Shows continue-watching entries with saved resume timestamps.
- Resumes anime episodes from the last known position.
- Resolves and plays the next episode from the current anime metadata.
- Keeps a simple playback surface: Home, play/pause, stop, next episode, seek,
  volume, fullscreen, and mute.
- Includes bundled dark themes: VoidPlayer, Catppuccin Frappe, Catppuccin
  Macchiato, and Catppuccin Mocha.

Anime browsing uses public third-party sources and is inspired by the
GPL-3.0-or-later `ani-cli` project. VoidPlayer does not host, control, or
redistribute anime content. The anime feature is gated by a first-use
disclaimer inside the app.

## Under The Hood

VoidPlayer keeps the GUI anime-focused while preserving the lower-level media
stack:

- `AnimeClient` searches show metadata, resolves episode streams, and fetches
  next-episode information.
- Anime playback is represented as a `MediaSource` with stream URL, headers,
  display name, and anime metadata such as show id, title, episode, and mode.
- Continue watching is stored in the user config with title, show id, episode,
  sub/dub mode, stream URL, display name, timestamp, subtitle URL metadata when
  present, and update time.
- The player saves progress on periodic state updates, app close, next episode,
  and when returning Home.
- The desktop app starts from anime search and continue watching; local-file
  opening belongs to the lower-level wrapper/CLI compatibility layer.
- The FFmpeg wrapper package remains available for probe, convert, trim, and
  thumbnail scripting.

## Requirements

VoidPlayer does not bundle FFmpeg binaries. Install FFmpeg separately and make
sure both commands are on `PATH`:

```powershell
ffmpeg -version
ffprobe -version
```

You also need Python 3.13 and `uv` available from your shell:

```powershell
python --version
uv --version
```

Install `uv` from the official Astral instructions if it is not already on your
system: <https://docs.astral.sh/uv/getting-started/installation/>

## Install From Source

```powershell
git clone https://github.com/dustinpolkrst/voidplayer.git
cd voidplayer
uv sync --dev
```

Run the anime player:

```powershell
uv run animeplayer
```

The `voidplayer` launcher opens the same app:

```powershell
uv run voidplayer
```

Local-file compatibility launch:

```powershell
uv run voidplayer input.mp4
```

## Install As A Tool

From a local checkout:

```powershell
uv tool install .
animeplayer
```

From GitHub:

```powershell
uv tool install git+https://github.com/dustinpolkrst/voidplayer.git
animeplayer
```

Use `uv tool upgrade voidplayer` after pulling or publishing a newer version.

## How To Use

1. Launch `animeplayer` or `voidplayer`.
2. Accept the anime source disclaimer.
3. Search for a show from the home screen.
4. Choose `Sub` or `Dub`.
5. Select an episode in the anime search dialog.
6. Use `Next Episode` when you want to continue the show.
7. Press `Home` at any time to return to the home screen; your anime timestamp
   is saved for Continue Watching.

Use `View > Theme` to switch themes. The selected theme is saved in the user
config directory and applied on the next launch.

## Hackable By Design

VoidPlayer is intentionally small and hackable. The app shell lives in Python,
the look lives in QSS/TOML theme files, and the anime provider logic is isolated
from the playback engine. You can change the player without learning a large
frontend stack or adding build tooling.

Useful places to start:

- `src/ffmpeg_pywrapper/player/app.py` - PySide app shell and anime home UI.
- `src/ffmpeg_pywrapper/anime.py` - anime search and stream resolution.
- `src/ffmpeg_pywrapper/player/themes/` - bundled themes.
- `src/ffmpeg_pywrapper/player/assets/` - SVG icons used by the player.
- `tests/test_player_smoke.py` - GUI smoke tests for the app shell.

## Custom Themes

Themes are directories with two files:

```text
my-theme/
  theme.toml
  style.qss
```

`theme.toml` defines tokens:

```toml
[color]
window_background = "#0d1017"
video_background = "#05070b"
control_background = "#151a23"
accent = "#4f8cff"
text_primary = "#e7eaf0"
text_secondary = "#aeb7c6"
border_control = "#252c3a"

[font]
time_label = 'Consolas, "Cascadia Mono", monospace'

[size]
control_radius = "8px"
button_radius = "6px"
```

`style.qss` is a Qt stylesheet template. Reference tokens with
`{{ section.name }}`:

```css
QMainWindow {
    background: {{ color.window_background }};
    color: {{ color.text_primary }};
}

QFrame#controlBar {
    background: {{ color.control_background }};
    border: 1px solid {{ color.border_control }};
    border-radius: {{ size.control_radius }};
}
```

Start by copying an existing bundled theme:

```powershell
Copy-Item -Recurse src\ffmpeg_pywrapper\player\themes\catppuccin-mocha .\my-theme
uv run voidplayer --theme-path .\my-theme
```

If a token used by `style.qss` is missing from `theme.toml`, VoidPlayer raises
a theme error and falls back to the default theme.

## Keyboard Shortcuts

```text
Space          Play/pause
Left / Right   Seek 5 seconds
Shift+Arrows   Seek 30 seconds
Up / Down      Volume
F              Fullscreen
M              Mute
N              Next episode
Esc            Exit fullscreen
```

## Development

```powershell
uv sync --dev
uv run pytest
uv build
python -m graphify update . --force
```

## FFmpeg Tools

The FFmpeg wrapper CLI remains available for compatibility and scripting:

```powershell
python -m ffmpeg_pywrapper probe input.mp4 --json
python -m ffmpeg_pywrapper describe input.mp4
python -m ffmpeg_pywrapper convert input.mp4 output.mkv --video-codec libx264 --audio-codec aac --overwrite
python -m ffmpeg_pywrapper trim input.mp4 clip.mp4 --start 00:00:05 --duration 10 --overwrite
python -m ffmpeg_pywrapper thumbnail input.mp4 thumb.jpg --timestamp 00:00:01 --overwrite
ffmpeg-pywrapper describe input.mp4
```

The Python API is still exposed:

```python
from ffmpeg_pywrapper import convert, probe, thumbnail, trim

metadata = probe("input.mp4")
print(metadata.streams_by_type("video"))

convert("input.mp4", "output.mp4", video_codec="libx264", audio_codec="aac", overwrite=True)
trim("input.mp4", "clip.mp4", start="00:00:05", duration=10, overwrite=True)
thumbnail("input.mp4", "thumb.jpg", timestamp="00:00:01", overwrite=True)
```

All process execution uses argument lists with `shell=False`.

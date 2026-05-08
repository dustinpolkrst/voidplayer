# VoidPlayer

VoidPlayer is an open-source, hacker-styled video player powered by FFmpeg,
PyAV, and sounddevice. It also keeps a small, typed Python wrapper around
system `ffmpeg` and `ffprobe` for scripting and inspection workflows.

The package is intentionally pure Python. It does not bundle FFmpeg binaries;
install FFmpeg separately and make sure `ffmpeg` and `ffprobe` are on `PATH`, or
pass explicit executable paths with `FFmpegConfig`.

## Development

```powershell
uv sync --dev
uv run pytest
uv build
```

To run the Windows desktop player example:

```powershell
uv sync --extra player --group player
uv run --extra player --group player python examples/simple_player/main.py
```

## CLI

```powershell
voidplayer input.mp4
```

## Python Quick Start

```python
from ffmpeg_pywrapper import convert, probe, thumbnail, trim

metadata = probe("input.mp4")
print(metadata.streams_by_type("video"))

convert("input.mp4", "output.mp4", video_codec="libx264", audio_codec="aac", overwrite=True)
trim("input.mp4", "clip.mp4", start="00:00:05", duration=10, overwrite=True)
thumbnail("input.mp4", "thumb.jpg", timestamp="00:00:01", overwrite=True)
```

## Inspect Commands

Use `build_command` when you need full FFmpeg-native option pass-through:

```python
from ffmpeg_pywrapper import build_command

args = build_command(
    ["input.mp4"],
    "output.mkv",
    output_options={"c:v": "libx265", "crf": 24, "preset": "slow"},
    overwrite=True,
)
print(args)
```

All process execution uses argument lists with `shell=False`.

## Media Description

```python
from ffmpeg_pywrapper import describe_media

info = describe_media("input.mp4")
print(info.duration, info.primary_video, info.has_audio)
```

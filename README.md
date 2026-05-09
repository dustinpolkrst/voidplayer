# VoidPlayer

VoidPlayer is an open-source, hacker-styled video player powered by FFmpeg,
PyAV, and sounddevice. It also keeps a small, typed Python wrapper around
system `ffmpeg` and `ffprobe` for scripting and inspection workflows.

The package is intentionally pure Python. It does not bundle FFmpeg binaries;
install FFmpeg separately and make sure `ffmpeg` and `ffprobe` are on `PATH`, or
pass explicit executable paths with `FFmpegConfig`.

On Windows, install FFmpeg from your package manager or from the official
project builds, then verify both commands are available:

```powershell
ffmpeg -version
ffprobe -version
```

## Development

```powershell
uv sync --dev
uv run pytest
uv build
```

To run the Windows desktop player:

```powershell
uv run voidplayer
uv run voidplayer input.mp4
```

## CLI

```powershell
python -m ffmpeg_pywrapper probe input.mp4 --json
python -m ffmpeg_pywrapper describe input.mp4
python -m ffmpeg_pywrapper convert input.mp4 output.mkv --video-codec libx264 --audio-codec aac --overwrite
python -m ffmpeg_pywrapper trim input.mp4 clip.mp4 --start 00:00:05 --duration 10 --overwrite
python -m ffmpeg_pywrapper thumbnail input.mp4 thumb.jpg --timestamp 00:00:01 --overwrite
ffmpeg-pywrapper describe input.mp4
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

## Progress and Cancellation

```python
import threading
from ffmpeg_pywrapper import FFmpegCancelledError, run_ffmpeg

cancel = threading.Event()

try:
    result = run_ffmpeg(
        ["ffmpeg", "-progress", "pipe:1", "-i", "input.mp4", "output.mp4"],
        stream_output=True,
        on_progress=lambda progress: print(progress.frame, progress.time),
        cancellation_event=cancel,
    )
except FFmpegCancelledError:
    print("conversion cancelled")
```

The callback receives parsed `Progress` objects while `FFmpegResult.progress`
still contains the collected progress blocks after completion.

## Media Description

```python
from ffmpeg_pywrapper import describe_media

info = describe_media("input.mp4")
print(info.duration, info.primary_video, info.has_audio)
print(info.audio_streams, info.subtitle_streams)
```

## Player Features

VoidPlayer supports opening multiple local files as a playlist, previous/next
transport controls, recent-file persistence under the user config directory,
audio stream selection for media with multiple audio tracks, fullscreen
playback, keyboard seeking, mute, playback speed controls, text subtitles, frame
capture, clip export, per-file resume state, subtitle delay controls, repeat and
shuffle playback, chapter navigation, a media inspector, and best-effort
timeline preview generation.

Keyboard shortcuts:

```text
Space          Play/pause
Left / Right   Seek 5 seconds
Shift+Arrows   Seek 30 seconds
Up / Down      Volume
F              Fullscreen
M              Mute
N / P          Next / previous item
[ / ]          Subtitle delay -/+ 250ms
Esc            Exit fullscreen
```

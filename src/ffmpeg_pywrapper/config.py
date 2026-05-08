from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import which

from .errors import FFmpegExecutableNotFound


@dataclass(frozen=True, slots=True)
class FFmpegConfig:
    """Executable locations for system FFmpeg tools."""

    ffmpeg: str | Path = "ffmpeg"
    ffprobe: str | Path = "ffprobe"

    def resolve_ffmpeg(self) -> str:
        return _resolve_executable(self.ffmpeg, "ffmpeg")

    def resolve_ffprobe(self) -> str:
        return _resolve_executable(self.ffprobe, "ffprobe")


def _resolve_executable(executable: str | Path, label: str) -> str:
    value = str(executable)
    path = Path(value)
    if path.is_absolute() or any(sep in value for sep in ("/", "\\")):
        if path.exists():
            return str(path)
        raise FFmpegExecutableNotFound(f"{label} executable was not found: {value}")

    resolved = which(value)
    if resolved is None:
        raise FFmpegExecutableNotFound(
            f"{label} executable was not found on PATH. Install FFmpeg or pass an explicit executable path."
        )
    return resolved

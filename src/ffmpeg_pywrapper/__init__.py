"""VoidPlayer runtime helpers and typed FFmpeg/FFprobe APIs."""

from .commands import build_command, convert, thumbnail, trim
from .config import FFmpegConfig
from .errors import (
    FFmpegError,
    FFmpegCancelledError,
    FFmpegExecutableNotFound,
    FFmpegInvalidCommand,
    FFmpegProcessError,
    FFmpegTimeoutError,
    FFmpegUnsupportedCodec,
    PlaybackError,
    UnsupportedMediaError,
)
from .media import MediaInfo, StreamInfo, describe_media, format_timestamp, seconds_from_timestamp
from .probe import FFProbeResult, probe
from .runner import FFmpegResult, Progress, run_ffmpeg

__all__ = [
    "FFmpegConfig",
    "FFmpegError",
    "FFmpegCancelledError",
    "FFmpegExecutableNotFound",
    "FFmpegInvalidCommand",
    "FFmpegProcessError",
    "FFmpegResult",
    "FFmpegTimeoutError",
    "FFmpegUnsupportedCodec",
    "FFProbeResult",
    "MediaInfo",
    "PlaybackError",
    "Progress",
    "StreamInfo",
    "UnsupportedMediaError",
    "build_command",
    "convert",
    "describe_media",
    "format_timestamp",
    "probe",
    "run_ffmpeg",
    "seconds_from_timestamp",
    "thumbnail",
    "trim",
]

from __future__ import annotations

import re
from dataclasses import dataclass


class FFmpegError(Exception):
    """Base exception for wrapper errors."""


class FFmpegExecutableNotFound(FFmpegError):
    """Raised when ffmpeg or ffprobe cannot be found."""


class FFmpegTimeoutError(FFmpegError):
    """Raised when a process exceeds its timeout."""


class FFmpegCancelledError(FFmpegError):
    """Raised when a process is cancelled cooperatively."""


class FFmpegInvalidCommand(FFmpegError):
    """Raised when FFmpeg rejects the supplied command."""


class FFmpegUnsupportedCodec(FFmpegError):
    """Raised when FFmpeg reports an unavailable codec."""


class PlaybackError(FFmpegError):
    """Base exception for playback-specific failures."""


class UnsupportedMediaError(PlaybackError):
    """Raised when no playable media stream is available."""


class DecodeError(PlaybackError):
    """Raised when media decoding fails."""


class AudioOutputError(PlaybackError):
    """Raised when audio output cannot be initialized."""


@dataclass(slots=True)
class FFmpegProcessError(FFmpegError):
    """Raised when FFmpeg exits unsuccessfully."""

    message: str
    arguments: list[str]
    returncode: int
    stdout: str
    stderr: str

    def __str__(self) -> str:
        return self.message


def classify_process_error(arguments: list[str], returncode: int, stdout: str, stderr: str) -> FFmpegError:
    message = _last_relevant_line(stderr) or f"FFmpeg exited with status {returncode}"
    lower = message.lower()
    if _matches(lower, ["unknown encoder", "encoder not found", "unknown decoder", "decoder not found"]):
        return FFmpegUnsupportedCodec(message)
    if _matches(
        lower,
        [
            "option not found",
            "unrecognized option",
            "trailing option",
            "invalid argument",
            "codec not currently supported in container",
        ],
    ):
        return FFmpegInvalidCommand(message)
    return FFmpegProcessError(message, arguments, returncode, stdout, stderr)


def _matches(value: str, needles: list[str]) -> bool:
    return any(needle in value for needle in needles)


def _last_relevant_line(stderr: str) -> str:
    for line in reversed(stderr.splitlines()):
        stripped = line.strip()
        if stripped and not re.match(r"^(frame=|size=|video:|audio:)", stripped):
            return stripped
    return ""

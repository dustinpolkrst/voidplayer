from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from .config import FFmpegConfig
from .probe import FFProbeResult, probe


@dataclass(frozen=True, slots=True)
class StreamInfo:
    index: int
    codec_type: str
    codec_name: str | None
    language: str | None = None
    title: str | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: float | None = None
    sample_rate: int | None = None
    channels: int | None = None


@dataclass(frozen=True, slots=True)
class MediaInfo:
    path: Path
    duration: float | None
    streams: tuple[StreamInfo, ...]

    @property
    def video_streams(self) -> tuple[StreamInfo, ...]:
        return tuple(stream for stream in self.streams if stream.codec_type == "video")

    @property
    def audio_streams(self) -> tuple[StreamInfo, ...]:
        return tuple(stream for stream in self.streams if stream.codec_type == "audio")

    @property
    def subtitle_streams(self) -> tuple[StreamInfo, ...]:
        return tuple(stream for stream in self.streams if stream.codec_type == "subtitle")

    @property
    def has_video(self) -> bool:
        return bool(self.video_streams)

    @property
    def has_audio(self) -> bool:
        return bool(self.audio_streams)

    @property
    def has_subtitles(self) -> bool:
        return bool(self.subtitle_streams)

    @property
    def primary_video(self) -> StreamInfo | None:
        return self.video_streams[0] if self.video_streams else None

    @property
    def primary_audio(self) -> StreamInfo | None:
        return self.audio_streams[0] if self.audio_streams else None

    @property
    def primary_subtitle(self) -> StreamInfo | None:
        return self.subtitle_streams[0] if self.subtitle_streams else None


def describe_media(
    path: str | Path,
    *,
    config: FFmpegConfig | None = None,
    timeout: float | None = None,
) -> MediaInfo:
    result = probe(path, config=config, timeout=timeout)
    return media_info_from_probe(path, result)


def media_info_from_probe(path: str | Path, result: FFProbeResult) -> MediaInfo:
    return MediaInfo(
        path=Path(path),
        duration=_optional_float(result.format.get("duration")),
        streams=tuple(_stream_info(stream) for stream in result.streams),
    )


def seconds_from_timestamp(value: str | int | float | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return max(0.0, float(value))

    parts = value.split(":")
    try:
        if len(parts) == 1:
            seconds = float(parts[0])
        elif len(parts) == 2:
            seconds = int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {value!r}") from exc
    return max(0.0, seconds)


def format_timestamp(seconds: float | int | None) -> str:
    total = max(0.0, float(seconds or 0.0))
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:05.2f}"


def _stream_info(stream: dict[str, Any]) -> StreamInfo:
    tags = stream.get("tags") if isinstance(stream.get("tags"), dict) else {}
    return StreamInfo(
        index=int(stream.get("index", 0)),
        codec_type=str(stream.get("codec_type", "")),
        codec_name=stream.get("codec_name"),
        language=tags.get("language"),
        title=tags.get("title"),
        width=_optional_int(stream.get("width")),
        height=_optional_int(stream.get("height")),
        frame_rate=_frame_rate(stream.get("avg_frame_rate") or stream.get("r_frame_rate")),
        sample_rate=_optional_int(stream.get("sample_rate")),
        channels=_optional_int(stream.get("channels")),
    )


def _optional_float(value: Any) -> float | None:
    if value in (None, "N/A"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value in (None, "N/A"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _frame_rate(value: Any) -> float | None:
    if value in (None, "N/A", "0/0"):
        return None
    try:
        return float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return None

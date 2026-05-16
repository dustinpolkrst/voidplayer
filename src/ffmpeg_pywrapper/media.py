from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from ._core import rust_core
from .config import FFmpegConfig
from .probe import FFProbeResult, probe


@dataclass(frozen=True, slots=True)
class MediaSource:
    location: str
    title: str | None = None
    headers: dict[str, str] | None = None
    subtitle_url: str | None = None
    metadata: dict[str, str] | None = None

    @classmethod
    def from_path(cls, path: str | Path) -> "MediaSource":
        value = Path(path)
        return cls(location=str(value), title=value.name)

    @property
    def is_remote(self) -> bool:
        return self.location.startswith(("http://", "https://"))

    @property
    def display_name(self) -> str:
        return self.title or self.location

    @property
    def local_path(self) -> Path | None:
        return None if self.is_remote else Path(self.location)

    def ffmpeg_input_options(self) -> dict[str, str]:
        if not self.headers:
            return {}
        headers = "".join(f"{key}: {value}\r\n" for key, value in self.headers.items())
        return {"headers": headers}


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
    path: Path | str
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
    path: str | Path | MediaSource,
    *,
    config: FFmpegConfig | None = None,
    timeout: float | None = None,
) -> MediaInfo:
    source = ensure_media_source(path)
    result = probe(source.location, config=config, timeout=timeout, input_options=source.ffmpeg_input_options())
    return media_info_from_probe(source.location, result)


def media_info_from_probe(path: str | Path, result: FFProbeResult) -> MediaInfo:
    media_path: Path | str = str(path) if str(path).startswith(("http://", "https://")) else Path(path)
    return MediaInfo(
        path=media_path,
        duration=_optional_float(result.format.get("duration")),
        streams=tuple(_stream_info(stream) for stream in result.streams),
    )


def ensure_media_source(source: str | Path | MediaSource) -> MediaSource:
    if isinstance(source, MediaSource):
        return source
    value = str(source)
    if value.startswith(("http://", "https://")):
        return MediaSource(location=value, title=value)
    return MediaSource.from_path(source)


def seconds_from_timestamp(value: str | int | float | None) -> float:
    if rust_core is not None:
        return float(rust_core.seconds_from_timestamp(value))
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
    if rust_core is not None:
        return str(rust_core.format_timestamp(None if seconds is None else float(seconds)))
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

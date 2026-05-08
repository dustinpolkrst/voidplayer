from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, slots=True)
class Progress:
    frame: int | None = None
    fps: float | None = None
    stream_size: int | None = None
    time: timedelta | None = None
    bitrate: str | None = None
    speed: str | None = None
    raw: dict[str, str] | None = None


def parse_progress_blocks(stdout: str) -> list[Progress]:
    blocks: list[Progress] = []
    current: dict[str, str] = {}

    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        current[key] = value
        if key == "progress":
            blocks.append(progress_from_mapping(current))
            current = {}

    if current:
        blocks.append(progress_from_mapping(current))
    return blocks


def progress_from_mapping(values: dict[str, str]) -> Progress:
    return Progress(
        frame=_parse_int(values.get("frame")),
        fps=_parse_float(values.get("fps")),
        stream_size=_parse_int(values.get("total_size")),
        time=_parse_time(values.get("out_time_us"), values.get("out_time_ms"), values.get("out_time")),
        bitrate=values.get("bitrate"),
        speed=values.get("speed"),
        raw=dict(values),
    )


def _parse_int(value: str | None) -> int | None:
    if value in (None, "N/A"):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_float(value: str | None) -> float | None:
    if value in (None, "N/A"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_time(out_time_us: str | None, out_time_ms: str | None, out_time: str | None) -> timedelta | None:
    value = _parse_int(out_time_us)
    if value is not None:
        return timedelta(microseconds=value)

    value = _parse_int(out_time_ms)
    if value is not None:
        return timedelta(microseconds=value)

    if not out_time:
        return None
    try:
        hours, minutes, seconds = out_time.split(":")
        return timedelta(hours=int(hours), minutes=int(minutes), seconds=float(seconds))
    except ValueError:
        return None

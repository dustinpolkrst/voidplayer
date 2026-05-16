from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._core import rust_core
from .commands import thumbnail
from .media import format_timestamp


@dataclass(frozen=True, slots=True)
class Chapter:
    id: int
    start: float
    end: float
    title: str


def parse_chapters(data: dict[str, Any]) -> tuple[Chapter, ...]:
    chapters: list[Chapter] = []
    for index, raw in enumerate(data.get("chapters", [])):
        if not isinstance(raw, dict):
            continue
        tags = raw.get("tags") if isinstance(raw.get("tags"), dict) else {}
        chapters.append(
            Chapter(
                id=int(raw.get("id", index)),
                start=_chapter_time(raw.get("start_time"), raw.get("start")),
                end=_chapter_time(raw.get("end_time"), raw.get("end")),
                title=str(tags.get("title") or f"Chapter {index + 1}"),
            )
        )
    return tuple(chapters)


def preview_timestamps(duration: float | None, *, interval: float = 30.0, max_count: int = 20) -> tuple[float, ...]:
    if rust_core is not None:
        return tuple(float(value) for value in rust_core.preview_timestamps(duration, interval=interval, max_count=max_count))
    if duration is None or duration <= 0:
        return ()
    step = max(interval, duration / max_count)
    stamps: list[float] = []
    current = 0.0
    while current < duration and len(stamps) < max_count:
        stamps.append(round(current, 3))
        current += step
    if duration not in stamps:
        stamps.append(round(duration, 3))
    return tuple(stamps[: max_count + 1])


def thumbnail_cache_dir(base_dir: Path, media_path: str | Path) -> Path:
    path = Path(media_path)
    try:
        modified = str(path.stat().st_mtime_ns)
    except OSError:
        modified = "missing"
    cache_input = str(path.resolve() if path.exists() else path)
    key = (
        str(rust_core.thumbnail_cache_key(cache_input, modified))
        if rust_core is not None
        else hashlib.sha1(f"{cache_input}:{modified}".encode("utf-8")).hexdigest()[:16]
    )
    return base_dir / "timeline-previews" / key


def generate_timeline_thumbnails(media_path: str | Path, duration: float | None, output_dir: Path) -> dict[float, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: dict[float, Path] = {}
    for stamp in preview_timestamps(duration):
        output = output_dir / f"{int(stamp * 1000):010d}.jpg"
        if not output.exists():
            thumbnail(media_path, output, timestamp=format_timestamp(stamp), overwrite=True, options={"q:v": 3})
        generated[stamp] = output
    return generated


def nearest_preview(previews: dict[float, Path], timestamp: float) -> Path | None:
    if not previews:
        return None
    stamp = min(previews, key=lambda item: abs(item - timestamp))
    return previews[stamp]


def _chapter_time(primary: object, fallback: object) -> float:
    for value in (primary, fallback):
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0

from __future__ import annotations

import os
from pathlib import Path

from ffmpeg_pywrapper.timeline import generate_timeline_thumbnails, parse_chapters, preview_timestamps, thumbnail_cache_dir


def test_parse_chapters_from_probe_payload() -> None:
    chapters = parse_chapters(
        {
            "chapters": [
                {"id": 7, "start_time": "1.5", "end_time": "10", "tags": {"title": "Intro"}},
                {"start": 10, "end": 20},
            ]
        }
    )

    assert chapters[0].id == 7
    assert chapters[0].start == 1.5
    assert chapters[0].title == "Intro"
    assert chapters[1].title == "Chapter 2"


def test_preview_timestamps_are_bounded() -> None:
    stamps = preview_timestamps(300, interval=30, max_count=3)

    assert len(stamps) <= 4
    assert stamps[0] == 0


def test_thumbnail_cache_dir_changes_with_mtime(tmp_path: Path) -> None:
    media = tmp_path / "movie.mp4"
    media.write_text("a", encoding="utf-8")
    os.utime(media, (1, 1))
    first = thumbnail_cache_dir(tmp_path / "cache", media)
    media.write_text("b", encoding="utf-8")
    os.utime(media, (2, 2))
    second = thumbnail_cache_dir(tmp_path / "cache", media)

    assert first != second


def test_generate_timeline_thumbnails_uses_thumbnail_helper(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def fake_thumbnail(input_path, output, *, timestamp, overwrite, options):  # noqa: ANN001
        calls.append((input_path, output, timestamp, overwrite, options))
        output.write_text("image", encoding="utf-8")

    monkeypatch.setattr("ffmpeg_pywrapper.timeline.thumbnail", fake_thumbnail)

    generated = generate_timeline_thumbnails("movie.mp4", 10, tmp_path)

    assert generated
    assert calls

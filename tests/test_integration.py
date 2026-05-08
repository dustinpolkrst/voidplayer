from __future__ import annotations

from pathlib import Path
from shutil import which

import pytest

from ffmpeg_pywrapper import convert, probe, thumbnail, trim
from ffmpeg_pywrapper.runner import run_ffmpeg

pytestmark = pytest.mark.integration


def test_media_flow_with_system_ffmpeg(tmp_path: Path) -> None:
    if which("ffmpeg") is None or which("ffprobe") is None:
        pytest.skip("ffmpeg and ffprobe are required")

    source = tmp_path / "source.mp4"
    trimmed = tmp_path / "trimmed.mp4"
    converted = tmp_path / "converted.mkv"
    image = tmp_path / "thumb.jpg"

    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=64x64:rate=5:duration=1",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        timeout=15,
    )

    metadata = probe(source)
    assert metadata.streams_by_type("video")

    trim(source, trimmed, duration=0.5, overwrite=True, options={"c": "copy"}, timeout=15)
    convert(trimmed, converted, video_codec="copy", audio_codec="copy", overwrite=True, timeout=15)
    thumbnail(source, image, timestamp=0, overwrite=True, timeout=15)

    assert trimmed.exists()
    assert converted.exists()
    assert image.exists()


def test_generate_webm_fixture_when_supported(tmp_path: Path) -> None:
    if which("ffmpeg") is None or which("ffprobe") is None:
        pytest.skip("ffmpeg and ffprobe are required")

    output = tmp_path / "sample.webm"
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=64x64:rate=5:duration=0.5",
            "-c:v",
            "libvpx-vp9",
            str(output),
        ],
        timeout=20,
    )

    metadata = probe(output)
    assert metadata.streams_by_type("video")

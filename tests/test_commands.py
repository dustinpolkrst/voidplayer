from __future__ import annotations

from pathlib import Path

from ffmpeg_pywrapper import FFmpegConfig, build_command
from ffmpeg_pywrapper.options import normalize_options


def test_normalize_options_preserves_order_and_stream_specifiers() -> None:
    args = normalize_options({"loglevel": "error", "c:v": "libx264", "y": True, "n": False, "t": None})

    assert args == ["-loglevel", "error", "-c:v", "libx264", "-y"]


def test_build_command_orders_global_inputs_and_output_options(tmp_path: Path) -> None:
    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg.write_text("")
    command = build_command(
        ["in.mp4"],
        "out.mp4",
        config=FFmpegConfig(ffmpeg=ffmpeg),
        global_options={"hide_banner": True},
        input_options={"ss": "00:00:01"},
        output_options={"c:v": "libx264", "c:a": "copy"},
        overwrite=True,
        progress=True,
    )

    assert command == [
        str(ffmpeg),
        "-hide_banner",
        "-y",
        "-progress",
        "pipe:1",
        "-ss",
        "00:00:01",
        "-i",
        "in.mp4",
        "-c:v",
        "libx264",
        "-c:a",
        "copy",
        "out.mp4",
    ]

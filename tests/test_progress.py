from __future__ import annotations

from datetime import timedelta

from ffmpeg_pywrapper.progress import parse_progress_blocks


def test_parse_progress_blocks() -> None:
    blocks = parse_progress_blocks("frame=10\nfps=25.0\nout_time_us=500000\nspeed=1.0x\nprogress=continue\n")

    assert len(blocks) == 1
    assert blocks[0].frame == 10
    assert blocks[0].fps == 25.0
    assert blocks[0].time == timedelta(milliseconds=500)

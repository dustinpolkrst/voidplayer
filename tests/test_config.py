from __future__ import annotations

import pytest

from ffmpeg_pywrapper import FFmpegConfig, FFmpegExecutableNotFound


def test_missing_absolute_executable_raises() -> None:
    with pytest.raises(FFmpegExecutableNotFound):
        FFmpegConfig(ffmpeg="C:/definitely/missing/ffmpeg.exe").resolve_ffmpeg()

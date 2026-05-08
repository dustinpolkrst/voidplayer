from __future__ import annotations

import subprocess

import pytest

from ffmpeg_pywrapper import FFmpegTimeoutError, run_ffmpeg


def test_run_ffmpeg_timeout(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(FFmpegTimeoutError):
        run_ffmpeg(["ffmpeg", "-version"], timeout=1)

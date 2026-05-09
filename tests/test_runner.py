from __future__ import annotations

import subprocess
import sys

import pytest

from ffmpeg_pywrapper import FFmpegProcessError, FFmpegTimeoutError, run_ffmpeg


def test_run_ffmpeg_timeout(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(FFmpegTimeoutError):
        run_ffmpeg(["ffmpeg", "-version"], timeout=1)


def test_run_ffmpeg_default_uses_subprocess_run(monkeypatch) -> None:
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_ffmpeg(["ffmpeg", "-version"])

    assert result.stdout == "ok"
    assert calls[0][1]["capture_output"] is True


def test_run_ffmpeg_bounded_stdout_keeps_tail() -> None:
    result = run_ffmpeg(
        [sys.executable, "-c", "import sys; sys.stdout.write('abcdef')"],
        max_output_bytes=3,
    )

    assert result.stdout == "def"


def test_run_ffmpeg_bounded_stderr_is_used_for_errors() -> None:
    with pytest.raises(FFmpegProcessError) as exc_info:
        run_ffmpeg(
            [sys.executable, "-c", "import sys; sys.stderr.write('alpha\\nbeta\\ngamma\\n'); sys.exit(2)"],
            max_output_bytes=13,
        )

    assert exc_info.value.stderr.splitlines() == ["beta", "gamma"]
    assert str(exc_info.value) == "gamma"


def test_run_ffmpeg_stream_output_parses_progress() -> None:
    result = run_ffmpeg(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.write('frame=1\\nout_time_us=1000\\nprogress=continue\\nframe=2\\nprogress=end\\n')",
        ],
        stream_output=True,
    )

    assert [block.frame for block in result.progress] == [1, 2]


def test_run_ffmpeg_popen_timeout_kills_process() -> None:
    with pytest.raises(FFmpegTimeoutError):
        run_ffmpeg(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout=0.1,
            max_output_bytes=1024,
        )

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .errors import FFmpegTimeoutError, classify_process_error
from .progress import Progress, parse_progress_blocks


@dataclass(frozen=True, slots=True)
class FFmpegResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    progress: list[Progress] = field(default_factory=list)


def run_ffmpeg(
    args: Sequence[str | Path],
    *,
    input_data: bytes | str | None = None,
    timeout: float | None = None,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> FFmpegResult:
    """Run an FFmpeg-family command safely with shell=False."""

    argv = [str(arg) for arg in args]
    text_mode = not isinstance(input_data, bytes)
    try:
        completed = subprocess.run(
            argv,
            input=input_data,
            capture_output=True,
            text=text_mode,
            timeout=timeout,
            cwd=cwd,
            env=env,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegTimeoutError(f"Process timed out after {timeout} seconds: {argv}") from exc

    stdout = _decode(completed.stdout)
    stderr = _decode(completed.stderr)
    if completed.returncode != 0:
        raise classify_process_error(argv, completed.returncode, stdout, stderr)

    return FFmpegResult(
        args=argv,
        returncode=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        progress=parse_progress_blocks(stdout),
    )


def _decode(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value

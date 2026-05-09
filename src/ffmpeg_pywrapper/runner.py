from __future__ import annotations

import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .errors import FFmpegTimeoutError, classify_process_error
from .progress import Progress, parse_progress_blocks, progress_from_mapping


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
    max_output_bytes: int | None = None,
    stream_output: bool = False,
) -> FFmpegResult:
    """Run an FFmpeg-family command safely with shell=False."""

    argv = [str(arg) for arg in args]
    if max_output_bytes is not None or stream_output:
        return _run_ffmpeg_popen(
            argv,
            input_data=input_data,
            timeout=timeout,
            cwd=cwd,
            env=env,
            max_output_bytes=max_output_bytes,
            stream_output=stream_output,
        )

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


class _BoundedBuffer:
    def __init__(self, limit: int | None) -> None:
        self.limit = limit
        self._data = bytearray()

    def append(self, chunk: bytes) -> None:
        if not chunk:
            return
        if self.limit is None:
            self._data.extend(chunk)
            return
        if self.limit <= 0:
            self._data.clear()
            return
        self._data.extend(chunk)
        if len(self._data) > self.limit:
            del self._data[: len(self._data) - self.limit]

    def decode(self) -> str:
        return bytes(self._data).decode("utf-8", errors="replace")


def _run_ffmpeg_popen(
    argv: list[str],
    *,
    input_data: bytes | str | None,
    timeout: float | None,
    cwd: str | Path | None,
    env: dict[str, str] | None,
    max_output_bytes: int | None,
    stream_output: bool,
) -> FFmpegResult:
    output_limit = max_output_bytes if max_output_bytes is not None else 1024 * 1024
    stdout_buffer = _BoundedBuffer(output_limit)
    stderr_buffer = _BoundedBuffer(output_limit)
    progress: list[Progress] = []
    progress_current: dict[str, str] = {}

    process = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE if input_data is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=env,
        shell=False,
    )

    def read_stdout() -> None:
        assert process.stdout is not None
        for chunk in iter(process.stdout.readline, b""):
            stdout_buffer.append(chunk)
            if stream_output:
                line = chunk.decode("utf-8", errors="replace").strip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                progress_current[key] = value
                if key == "progress":
                    progress.append(progress_from_mapping(progress_current))
                    progress_current.clear()

    def read_stderr() -> None:
        assert process.stderr is not None
        for chunk in iter(lambda: process.stderr.read(8192), b""):
            stderr_buffer.append(chunk)

    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    try:
        if input_data is not None:
            assert process.stdin is not None
            payload = input_data if isinstance(input_data, bytes) else input_data.encode()
            process.stdin.write(payload)
            process.stdin.close()
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise FFmpegTimeoutError(f"Process timed out after {timeout} seconds: {argv}") from exc
    finally:
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)

    stdout = stdout_buffer.decode()
    stderr = stderr_buffer.decode()
    if stream_output and progress_current:
        progress.append(progress_from_mapping(progress_current))
    if not stream_output:
        progress = parse_progress_blocks(stdout)
    if returncode != 0:
        raise classify_process_error(argv, returncode, stdout, stderr)

    return FFmpegResult(
        args=argv,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        progress=progress,
    )


def _decode(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value

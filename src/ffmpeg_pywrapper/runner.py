from __future__ import annotations

import subprocess
import types
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ._core import rust_core
from .errors import FFmpegCancelledError, FFmpegTimeoutError, classify_process_error
from .progress import Progress, parse_progress_blocks, progress_from_mapping

ProgressCallback = Callable[[Progress], None]


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
    on_progress: ProgressCallback | None = None,
    cancellation_event: threading.Event | None = None,
) -> FFmpegResult:
    """Run an FFmpeg-family command safely with shell=False."""

    argv = [str(arg) for arg in args]
    if (
        rust_core is not None
        and input_data is None
        and not stream_output
        and on_progress is None
        and cancellation_event is None
        and isinstance(subprocess.run, types.FunctionType)
        and subprocess.run.__module__ == "subprocess"
    ):
        try:
            result = rust_core.run_ffmpeg_full_py(
                argv,
                timeout=timeout,
                cwd=str(cwd) if cwd is not None else None,
                env=env,
                max_output_bytes=max_output_bytes,
            )
        except RuntimeError as exc:
            if str(exc).startswith("timeout:"):
                raise FFmpegTimeoutError(f"Process timed out after {timeout} seconds: {argv}") from exc
            raise
        stdout = str(result.stdout)
        stderr = str(result.stderr)
        returncode = int(result.returncode)
        if returncode != 0:
            raise classify_process_error(argv, returncode, stdout, stderr)
        return FFmpegResult(
            args=list(result.args),
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            progress=[progress_from_mapping(dict(block)) for block in result.progress],
        )

    if max_output_bytes is not None or stream_output or on_progress is not None or cancellation_event is not None:
        return _run_ffmpeg_popen(
            argv,
            input_data=input_data,
            timeout=timeout,
            cwd=cwd,
            env=env,
            max_output_bytes=max_output_bytes,
            stream_output=stream_output,
            on_progress=on_progress,
            cancellation_event=cancellation_event,
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
    on_progress: ProgressCallback | None,
    cancellation_event: threading.Event | None,
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
            if stream_output or on_progress is not None:
                line = chunk.decode("utf-8", errors="replace").strip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                progress_current[key] = value
                if key == "progress":
                    block = progress_from_mapping(progress_current)
                    progress.append(block)
                    if on_progress is not None:
                        on_progress(block)
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
        started_at = time.monotonic()
        while True:
            if cancellation_event is not None and cancellation_event.is_set():
                process.kill()
                process.wait()
                raise FFmpegCancelledError(f"Process was cancelled: {argv}")
            returncode = process.poll()
            if returncode is not None:
                break
            if timeout is not None and time.monotonic() - started_at >= timeout:
                raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)
            time.sleep(0.02)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise FFmpegTimeoutError(f"Process timed out after {timeout} seconds: {argv}") from exc
    finally:
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)

    stdout = stdout_buffer.decode()
    stderr = stderr_buffer.decode()
    if (stream_output or on_progress is not None) and progress_current:
        block = progress_from_mapping(progress_current)
        progress.append(block)
        if on_progress is not None:
            on_progress(block)
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

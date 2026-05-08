from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .config import FFmpegConfig
from .options import Options, normalize_options
from .runner import FFmpegResult, run_ffmpeg


def build_command(
    inputs: Sequence[str | Path],
    output: str | Path,
    *,
    config: FFmpegConfig | None = None,
    global_options: Options | None = None,
    input_options: Options | None = None,
    output_options: Options | None = None,
    overwrite: bool = False,
    progress: bool = False,
) -> list[str]:
    """Build a plain argv list for a single-output FFmpeg command."""

    cfg = config or FFmpegConfig()
    args = [cfg.resolve_ffmpeg()]
    args.extend(normalize_options(global_options))
    args.append("-y" if overwrite else "-n")

    if progress:
        args.extend(["-progress", "pipe:1"])

    for input_path in inputs:
        args.extend(normalize_options(input_options))
        args.extend(["-i", str(input_path)])

    args.extend(normalize_options(output_options))
    args.append(str(output))
    return args


def convert(
    input: str | Path,
    output: str | Path,
    *,
    video_codec: str | None = None,
    audio_codec: str | None = None,
    overwrite: bool = False,
    options: Options | None = None,
    config: FFmpegConfig | None = None,
    timeout: float | None = None,
) -> FFmpegResult:
    output_options = dict(options or {})
    if video_codec:
        output_options["c:v"] = video_codec
    if audio_codec:
        output_options["c:a"] = audio_codec
    args = build_command([input], output, output_options=output_options, overwrite=overwrite, progress=True, config=config)
    return run_ffmpeg(args, timeout=timeout)


def trim(
    input: str | Path,
    output: str | Path,
    *,
    start: str | float | None = None,
    duration: str | float | None = None,
    overwrite: bool = False,
    options: Options | None = None,
    config: FFmpegConfig | None = None,
    timeout: float | None = None,
) -> FFmpegResult:
    input_options: dict[str, object] = {}
    if start is not None:
        input_options["ss"] = start

    output_options = dict(options or {})
    if duration is not None:
        output_options["t"] = duration

    args = build_command(
        [input],
        output,
        input_options=input_options,
        output_options=output_options,
        overwrite=overwrite,
        progress=True,
        config=config,
    )
    return run_ffmpeg(args, timeout=timeout)


def thumbnail(
    input: str | Path,
    output: str | Path,
    *,
    timestamp: str | float,
    overwrite: bool = False,
    options: Options | None = None,
    config: FFmpegConfig | None = None,
    timeout: float | None = None,
) -> FFmpegResult:
    output_options = {"frames:v": 1, **dict(options or {})}
    args = build_command(
        [input],
        output,
        input_options={"ss": timestamp},
        output_options=output_options,
        overwrite=overwrite,
        config=config,
    )
    return run_ffmpeg(args, timeout=timeout)

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import FFmpegConfig
from .runner import run_ffmpeg


@dataclass(frozen=True, slots=True)
class FFProbeResult:
    data: dict[str, Any]

    @property
    def format(self) -> dict[str, Any]:
        return self.data.get("format", {})

    @property
    def streams(self) -> list[dict[str, Any]]:
        return list(self.data.get("streams", []))

    def streams_by_type(self, codec_type: str) -> list[dict[str, Any]]:
        return [stream for stream in self.streams if stream.get("codec_type") == codec_type]


def probe(
    path: str | Path,
    *,
    config: FFmpegConfig | None = None,
    timeout: float | None = None,
    input_options: dict[str, str] | None = None,
) -> FFProbeResult:
    cfg = config or FFmpegConfig()
    args = [
        cfg.resolve_ffprobe(),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
    ]
    for key, value in (input_options or {}).items():
        args.extend([f"-{key}", value])
    args.append(str(path))
    result = run_ffmpeg(args, timeout=timeout)
    return FFProbeResult(json.loads(result.stdout or "{}"))

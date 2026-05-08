from __future__ import annotations

import subprocess
from pathlib import Path

from ffmpeg_pywrapper import FFmpegConfig, probe


def test_probe_parses_json(monkeypatch, tmp_path: Path) -> None:
    ffprobe = tmp_path / "ffprobe"
    ffprobe.write_text("")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout='{"streams":[{"codec_type":"video"}],"format":{"duration":"1.0"}}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = probe("input.mp4", config=FFmpegConfig(ffprobe=ffprobe))

    assert result.format["duration"] == "1.0"
    assert len(result.streams_by_type("video")) == 1

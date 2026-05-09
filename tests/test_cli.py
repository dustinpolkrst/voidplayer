from __future__ import annotations

from pathlib import Path

from ffmpeg_pywrapper import __main__ as cli
from ffmpeg_pywrapper.media import MediaInfo, StreamInfo
from ffmpeg_pywrapper.probe import FFProbeResult


def test_cli_probe_outputs_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "probe", lambda _path: FFProbeResult({"format": {"duration": "1.0"}, "streams": []}))

    assert cli.main(["probe", "input.mp4", "--json"]) == 0

    assert '"duration": "1.0"' in capsys.readouterr().out


def test_cli_describe_uses_media_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "describe_media",
        lambda path: MediaInfo(
            path=Path(path),
            duration=2.5,
            streams=(StreamInfo(index=0, codec_type="video", codec_name="h264", width=1920, height=1080),),
        ),
    )

    assert cli.main(["describe", "input.mp4"]) == 0

    output = capsys.readouterr().out
    assert "duration: 2.5" in output
    assert "#0 video h264 1920x1080" in output


def test_cli_convert_passes_options(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(cli, "convert", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert cli.main(["convert", "in.mp4", "out.mkv", "--video-codec", "libx264", "--audio-codec", "aac", "--overwrite"]) == 0

    assert calls == [
        (
            (Path("in.mp4"), Path("out.mkv")),
            {"video_codec": "libx264", "audio_codec": "aac", "overwrite": True},
        )
    ]


def test_cli_trim_and_thumbnail_pass_options(monkeypatch) -> None:
    trim_calls = []
    thumb_calls = []
    monkeypatch.setattr(cli, "trim", lambda *args, **kwargs: trim_calls.append((args, kwargs)))
    monkeypatch.setattr(cli, "thumbnail", lambda *args, **kwargs: thumb_calls.append((args, kwargs)))

    assert cli.main(["trim", "in.mp4", "clip.mp4", "--start", "1", "--duration", "2", "--overwrite"]) == 0
    assert cli.main(["thumbnail", "in.mp4", "thumb.jpg", "--timestamp", "3", "--overwrite"]) == 0

    assert trim_calls == [((Path("in.mp4"), Path("clip.mp4")), {"start": "1", "duration": "2", "overwrite": True})]
    assert thumb_calls == [((Path("in.mp4"), Path("thumb.jpg")), {"timestamp": "3", "overwrite": True})]

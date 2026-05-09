from __future__ import annotations

from ffmpeg_pywrapper.media import format_timestamp, media_info_from_probe, seconds_from_timestamp
from ffmpeg_pywrapper.probe import FFProbeResult


def test_media_info_selects_primary_streams() -> None:
    info = media_info_from_probe(
        "sample.mp4",
        FFProbeResult(
            {
                "format": {"duration": "12.5"},
                "streams": [
                    {
                        "index": 0,
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1920,
                        "height": 1080,
                        "avg_frame_rate": "30000/1001",
                    },
                    {"index": 1, "codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
                ],
            }
        ),
    )

    assert info.duration == 12.5
    assert info.primary_video is not None
    assert info.primary_video.frame_rate == 30000 / 1001
    assert info.primary_audio is not None
    assert info.primary_audio.sample_rate == 48000


def test_media_info_exposes_subtitles_and_stream_tags() -> None:
    info = media_info_from_probe(
        "movie.mkv",
        FFProbeResult(
            {
                "format": {"duration": "10"},
                "streams": [
                    {"index": 0, "codec_type": "video", "codec_name": "h264"},
                    {"index": 1, "codec_type": "audio", "codec_name": "aac", "tags": {"language": "eng"}},
                    {"index": 2, "codec_type": "subtitle", "codec_name": "subrip", "tags": {"title": "English CC"}},
                ],
            }
        ),
    )

    assert info.primary_audio is not None
    assert info.primary_audio.language == "eng"
    assert info.has_subtitles is True
    assert info.primary_subtitle is not None
    assert info.primary_subtitle.title == "English CC"


def test_timestamp_helpers() -> None:
    assert seconds_from_timestamp("01:02:03.5") == 3723.5
    assert seconds_from_timestamp("02:03") == 123
    assert format_timestamp(3723.5) == "01:02:03.50"

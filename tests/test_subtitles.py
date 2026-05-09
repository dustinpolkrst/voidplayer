from __future__ import annotations

from ffmpeg_pywrapper.subtitles import parse_ass, parse_srt, parse_vtt


def test_parse_srt_and_lookup_text() -> None:
    cues = parse_srt(
        """1
00:00:01,000 --> 00:00:02,500
Hello <i>world</i>

2
00:00:03,000 --> 00:00:04,000
Next
"""
    )

    assert len(cues) == 2
    assert cues[0].start == 1
    assert cues[0].end == 2.5
    assert cues[0].text == "Hello world"


def test_parse_vtt_skips_header() -> None:
    cues = parse_vtt(
        """WEBVTT

00:00:05.000 --> 00:00:06.000
Caption
"""
    )

    assert cues[0].start == 5
    assert cues[0].text == "Caption"


def test_parse_ass_dialogue_lines() -> None:
    cues = parse_ass(
        """[Events]
Dialogue: 0,0:00:01.00,0:00:03.50,Default,,0,0,0,,Hello{\\i1}\\Nthere
"""
    )

    assert cues[0].start == 1
    assert cues[0].end == 3.5
    assert cues[0].text == "Hello\nthere"

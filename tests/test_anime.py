from __future__ import annotations

from ffmpeg_pywrapper.anime import (
    AnimeClient,
    AnimeStream,
    parse_provider_response,
    parse_source_urls,
    parse_source_urls_from_text,
    select_quality,
)


def test_parse_source_urls_strips_provider_prefix() -> None:
    assert parse_source_urls([{"sourceUrl": "--/clock.json?id=abc"}, {"sourceUrl": "https://example.test/video"}]) == [
        "/clock.json?id=abc",
        "https://example.test/video",
    ]


def test_parse_provider_response_extracts_direct_links_and_subtitle_metadata() -> None:
    response = (
        '{"link":"https:\\/\\/cdn.example.test\\/episode-720.mp4","resolutionStr":"720p"},'
        '{"hls","url":"https:\\/\\/cdn.example.test\\/master.m3u8","hardsub_lang":"en-US",'
        '"subtitles":[{"lang":"en","label":"English","default":"default","src":"https:\\/\\/cdn.example.test\\/sub.vtt"}],'
        '"Referer":"https:\\/\\/embed.example.test\\/"}'
    )

    streams = parse_provider_response(response, title="Example", episode="3")

    assert streams[0].quality == "720p"
    assert streams[0].url == "https://cdn.example.test/episode-720.mp4"
    assert any(stream.subtitle_url == "https://cdn.example.test/sub.vtt" for stream in streams)
    assert any(stream.referrer == "https://embed.example.test/" for stream in streams)


def test_select_quality_defaults_to_best_when_missing() -> None:
    streams = [
        AnimeStream(url="https://example.test/480.mp4", quality="480p", title="Example", episode="1"),
        AnimeStream(url="https://example.test/1080.mp4", quality="1080p", title="Example", episode="1"),
    ]

    assert select_quality(streams, "best").quality == "1080p"
    assert select_quality(streams, "worst").quality == "480p"
    assert select_quality(streams, "720p").quality == "1080p"


def test_stream_to_media_source_preserves_headers_and_subtitle() -> None:
    stream = AnimeStream(
        url="https://example.test/master.m3u8",
        quality="1080p",
        title="Example",
        episode="12",
        referrer="https://embed.example.test/",
        subtitle_url="https://example.test/sub.vtt",
    )

    source = stream.to_media_source()

    assert source.display_name == "Example - Episode 12"
    assert source.subtitle_url == "https://example.test/sub.vtt"
    assert "Referer: https://embed.example.test/\r\n" in source.ffmpeg_input_options()["headers"]


def test_parse_source_urls_from_text_handles_json_shape() -> None:
    assert parse_source_urls_from_text('{"episode":{"sourceUrls":[{"sourceUrl":"--1757"}]}}') == ["/o"]


def test_decode_source_url_handles_plain_url() -> None:
    assert parse_source_urls([{"sourceUrl": "https://example.test/video.mp4"}]) == ["https://example.test/video.mp4"]


def test_anime_client_imports_with_runtime_dependencies() -> None:
    assert AnimeClient is not None

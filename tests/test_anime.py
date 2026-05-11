from __future__ import annotations

from ffmpeg_pywrapper.anime import (
    AnimeClient,
    AnimeClientError,
    AnimeEpisode,
    AnimeProviderStage,
    AnimeResolvedCache,
    AnimeSearchResult,
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
    assert source.metadata == {
        "kind": "anime",
        "title": "Example",
        "episode": "12",
        "mode": "sub",
    }
    assert "Referer: https://embed.example.test/\r\n" in source.ffmpeg_input_options()["headers"]


def test_parse_source_urls_from_text_handles_json_shape() -> None:
    assert parse_source_urls_from_text('{"episode":{"sourceUrls":[{"sourceUrl":"--1757"}]}}') == ["/o"]


def test_decode_source_url_handles_plain_url() -> None:
    assert parse_source_urls([{"sourceUrl": "https://example.test/video.mp4"}]) == ["https://example.test/video.mp4"]


def test_anime_client_imports_with_runtime_dependencies() -> None:
    assert AnimeClient is not None


def test_anime_client_search_uses_session_cache(monkeypatch) -> None:
    client = AnimeClient()
    calls = []

    def fake_post(payload):  # noqa: ANN001
        calls.append(payload)
        return {
            "data": {
                "shows": {
                    "edges": [
                        {
                            "_id": "show-1",
                            "name": "Example",
                            "availableEpisodes": {"sub": 12},
                        }
                    ]
                }
            }
        }

    monkeypatch.setattr(client, "_post_graphql", fake_post)

    assert client.search("Example")
    assert client.search("Example")
    assert len(calls) == 1


def test_fast_streams_returns_direct_without_resolving_slow_providers(monkeypatch) -> None:
    client = AnimeClient()
    episode = AnimeEpisode(
        show_id="show-1",
        title="Example",
        number="1",
    )
    monkeypatch.setattr(
        client,
        "_episode_provider_links",
        lambda _episode: (
            [
                "https://tools.fast4speed.rsvp/media/show/sub/1",
                "https://slow.example.test/embed",
            ],
            {},
        ),
    )
    monkeypatch.setattr(client, "_resolve_provider", lambda *_args: (_ for _ in ()).throw(AssertionError("slow provider should not run")))

    streams = client.fast_streams(episode)

    assert len(streams) == 1
    assert streams[0].quality == "direct"
    assert streams[0].to_media_source().metadata["show_id"] == "show-1"


def test_next_episode_returns_following_episode(monkeypatch) -> None:
    client = AnimeClient()
    monkeypatch.setattr(
        client,
        "episodes",
        lambda _show, *, mode="sub": [
            AnimeEpisode(show_id="show-1", title="Example", number="1", mode="sub"),
            AnimeEpisode(show_id="show-1", title="Example", number="2", mode="sub"),
        ],
    )

    episode = AnimeEpisode(show_id="show-1", title="Example", number="1", mode="sub")

    assert client.next_episode(episode) == AnimeEpisode(show_id="show-1", title="Example", number="2", mode="sub")


def test_anime_client_error_includes_stage_and_retry_hint() -> None:
    error = AnimeClientError("Episode source data is unavailable.", stage=AnimeProviderStage.EPISODE_SOURCES)

    assert str(error) == "Could not load episode sources. Episode source data is unavailable. Try again or choose another episode."
    assert error.stage is AnimeProviderStage.EPISODE_SOURCES
    assert error.debug_detail == "Episode source data is unavailable."


def test_resolved_cache_round_trips_episode_metadata_and_streams(tmp_path) -> None:  # noqa: ANN001
    cache_path = tmp_path / "anime-cache.json"
    cache = AnimeResolvedCache(cache_path, now=lambda: 1000.0)
    show = AnimeSearchResult(show_id="show-1", title="Example", episode_count=2)
    episodes = [
        AnimeEpisode(show_id="show-1", title="Example", number="1", mode="sub"),
        AnimeEpisode(show_id="show-1", title="Example", number="2", mode="sub"),
    ]
    streams = [
        AnimeStream(
            url="https://cdn.example.test/episode-1.m3u8",
            quality="1080p",
            title="Example",
            episode="1",
            show_id="show-1",
            mode="sub",
            referrer="https://embed.example.test/",
            subtitle_url="https://cdn.example.test/sub.vtt",
        )
    ]

    cache.set_search_results("Example", "sub", [show])
    cache.set_episodes("show-1", "sub", episodes)
    cache.set_streams("show-1", "sub", "1", streams)

    restored = AnimeResolvedCache(cache_path, now=lambda: 1001.0)

    assert restored.search_results(" example ", "sub") == [show]
    assert restored.episodes("show-1", "sub") == episodes
    assert restored.streams("show-1", "sub", "1") == streams


def test_resolved_cache_expires_streams_before_episode_metadata(tmp_path) -> None:  # noqa: ANN001
    cache_path = tmp_path / "anime-cache.json"
    cache = AnimeResolvedCache(cache_path, now=lambda: 1000.0, metadata_ttl=100.0, stream_ttl=10.0)
    show = AnimeSearchResult(show_id="show-1", title="Example", episode_count=1)
    episode = AnimeEpisode(show_id="show-1", title="Example", number="1", mode="sub")
    stream = AnimeStream(url="https://cdn.example.test/episode-1.m3u8", quality="1080p", title="Example", episode="1", show_id="show-1")

    cache.set_search_results("Example", "sub", [show])
    cache.set_episodes("show-1", "sub", [episode])
    cache.set_streams("show-1", "sub", "1", [stream])
    expired = AnimeResolvedCache(cache_path, now=lambda: 1011.0, metadata_ttl=100.0, stream_ttl=10.0)

    assert expired.search_results("Example", "sub") == [show]
    assert expired.episodes("show-1", "sub") == [episode]
    assert expired.streams("show-1", "sub", "1") is None


def test_anime_client_uses_persistent_cache_for_search_episodes_and_streams(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    cache_path = tmp_path / "anime-cache.json"
    first = AnimeClient(cache_path=cache_path)
    episode = AnimeEpisode(show_id="show-1", title="Example", number="1", mode="sub")
    monkeypatch.setattr(
        first,
        "_post_graphql",
        lambda payload: {
            "data": {
                "shows": {"edges": [{"_id": "show-1", "name": "Example", "availableEpisodes": {"sub": 1}}]},
                "show": {"availableEpisodesDetail": {"sub": ["1"]}},
            }
        },
    )
    monkeypatch.setattr(first, "_resolve_streams", lambda _episode, *, fast_only: [AnimeStream(url="https://cdn.example.test/1.m3u8", quality="1080p", title="Example", episode="1", show_id="show-1")])

    assert first.search("Example")
    assert first.episodes(AnimeSearchResult(show_id="show-1", title="Example"), mode="sub")
    assert first.fast_streams(episode)

    second = AnimeClient(cache_path=cache_path)
    monkeypatch.setattr(second, "_post_graphql", lambda _payload: (_ for _ in ()).throw(AssertionError("network search should not run")))
    monkeypatch.setattr(second, "_resolve_streams", lambda _episode, *, fast_only: (_ for _ in ()).throw(AssertionError("network streams should not run")))

    assert second.search("Example")[0].show_id == "show-1"
    assert second.episodes(AnimeSearchResult(show_id="show-1", title="Example"), mode="sub")[0].number == "1"
    assert second.fast_streams(episode)[0].url == "https://cdn.example.test/1.m3u8"


def test_resolve_streams_reports_slow_provider_stage_when_no_provider_returns_streams(monkeypatch) -> None:
    client = AnimeClient()
    episode = AnimeEpisode(show_id="show-1", title="Example", number="1", mode="sub")
    monkeypatch.setattr(client, "_episode_provider_links", lambda _episode: (["https://slow.example.test/embed"], {}))
    monkeypatch.setattr(client, "_resolve_slow_providers", lambda _links, _episode: [])

    try:
        client.streams(episode)
    except AnimeClientError as exc:
        assert exc.stage is AnimeProviderStage.SLOW_PROVIDER
        assert "fallback stream sources" in str(exc)
    else:  # pragma: no cover - assertion clarity
        raise AssertionError("Expected AnimeClientError")

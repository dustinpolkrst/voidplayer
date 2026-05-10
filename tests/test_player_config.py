from __future__ import annotations

from ffmpeg_pywrapper.player.config_store import (
    AnimeHistoryItem,
    anime_history_from_config,
    load_config,
    resumable_position,
    save_config,
    set_anime_history_item,
)


def test_anime_history_round_trip_preserves_unknown_keys(tmp_path) -> None:  # noqa: ANN001
    config_path = tmp_path / "config.json"
    item = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="3",
        mode="sub",
        stream_url="https://example.test/episode-3.mp4",
        display_name="Example - Episode 3",
        position=45,
        subtitle_url="https://example.test/episode-3.vtt",
    )
    config = set_anime_history_item({"theme": "catppuccin-mocha"}, item)
    save_config(config_path, config)

    loaded = load_config(config_path)
    history = anime_history_from_config(loaded)

    assert loaded["theme"] == "catppuccin-mocha"
    assert len(history) == 1
    assert history[0].title == "Example"
    assert history[0].show_id == "show-1"
    assert history[0].episode == "3"
    assert history[0].mode == "sub"
    assert history[0].stream_url == "https://example.test/episode-3.mp4"
    assert history[0].display_name == "Example - Episode 3"
    assert history[0].position == 45
    assert history[0].subtitle_url == "https://example.test/episode-3.vtt"
    assert history[0].updated_at > 0


def test_anime_history_deduplicates_by_show_episode_and_mode() -> None:
    first = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="1",
        mode="dub",
        stream_url="https://example.test/old.mp4",
        display_name="Old",
    )
    second = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="1",
        mode="dub",
        stream_url="https://example.test/new.mp4",
        display_name="New",
        position=12,
    )

    history = anime_history_from_config(set_anime_history_item(set_anime_history_item({}, first), second))

    assert len(history) == 1
    assert history[0].stream_url == "https://example.test/new.mp4"
    assert history[0].position == 12


def test_invalid_anime_history_returns_empty() -> None:
    assert anime_history_from_config({"anime_history": "bad"}) == []
    assert anime_history_from_config({"anime_history": [{"title": "Incomplete"}]}) == []


def test_resumable_position_skips_edges() -> None:
    assert resumable_position(4, 100) is None
    assert resumable_position(98, 100) is None
    assert resumable_position(50, 100) == 50
    assert resumable_position(150, 100) is None


def test_corrupt_config_returns_empty(tmp_path) -> None:  # noqa: ANN001
    config = tmp_path / "config.json"
    config.write_text("{not json", encoding="utf-8")

    assert load_config(config) == {}

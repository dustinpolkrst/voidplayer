from __future__ import annotations

from ffmpeg_pywrapper.player.config_store import (
    AnimeHistoryItem,
    anime_history_from_config,
    anime_history_progress,
    load_config,
    remove_anime_history_item,
    resumable_position,
    save_config,
    set_anime_history_item,
    should_continue_with_next_episode,
    sorted_anime_history,
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


def test_anime_history_round_trip_preserves_duration(tmp_path) -> None:  # noqa: ANN001
    config_path = tmp_path / "config.json"
    item = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="3",
        mode="sub",
        stream_url="https://example.test/episode-3.mp4",
        display_name="Example - Episode 3",
        position=45,
        duration=100,
    )

    save_config(config_path, set_anime_history_item({}, item))
    history = anime_history_from_config(load_config(config_path))

    assert history[0].duration == 100


def test_remove_anime_history_item_preserves_other_entries() -> None:
    first = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="1",
        mode="sub",
        stream_url="https://example.test/1.mp4",
        display_name="Example - Episode 1",
    )
    second = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="2",
        mode="sub",
        stream_url="https://example.test/2.mp4",
        display_name="Example - Episode 2",
    )
    config = set_anime_history_item(set_anime_history_item({}, first), second)

    updated = remove_anime_history_item(config, show_id="show-1", episode="2", mode="sub")
    history = anime_history_from_config(updated)

    assert len(history) == 1
    assert history[0].episode == "1"


def test_sorted_anime_history_orders_last_watched_first() -> None:
    older = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="1",
        mode="sub",
        stream_url="https://example.test/1.mp4",
        display_name="Example - Episode 1",
        updated_at=10,
    )
    newer = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="2",
        mode="sub",
        stream_url="https://example.test/2.mp4",
        display_name="Example - Episode 2",
        updated_at=20,
    )

    assert [item.episode for item in sorted_anime_history([older, newer])] == ["2", "1"]


def test_anime_history_progress_formats_known_duration() -> None:
    item = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="1",
        mode="sub",
        stream_url="https://example.test/1.mp4",
        display_name="Example - Episode 1",
        position=50,
        duration=200,
    )

    assert anime_history_progress(item) == "25%"


def test_should_continue_with_next_episode_when_near_end() -> None:
    near_end = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="1",
        mode="sub",
        stream_url="https://example.test/1.mp4",
        display_name="Example - Episode 1",
        position=296,
        duration=300,
    )
    middle = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="1",
        mode="sub",
        stream_url="https://example.test/1.mp4",
        display_name="Example - Episode 1",
        position=120,
        duration=300,
    )

    assert should_continue_with_next_episode(near_end) is True
    assert should_continue_with_next_episode(middle) is False


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

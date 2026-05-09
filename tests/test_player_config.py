from __future__ import annotations

from pathlib import Path

from ffmpeg_pywrapper.player.config_store import (
    AnimeHistoryItem,
    anime_history_from_config,
    MediaState,
    load_config,
    media_state_from_config,
    recent_files_from_config,
    resumable_position,
    save_config,
    set_anime_history_item,
    set_media_state,
    set_recent_files,
)


def test_recent_files_config_preserves_unknown_keys(tmp_path: Path) -> None:
    config = {"theme": "custom"}
    updated = set_recent_files(config, [Path("a.mp4"), Path("a.mp4"), Path("b.mp4")])

    assert updated["theme"] == "custom"
    assert recent_files_from_config(updated) == [Path("a.mp4"), Path("b.mp4")]


def test_media_state_round_trip(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    state = MediaState(position=25, audio_stream_index=2, subtitle_source="subs.srt", subtitle_delay=0.25, volume=0.5, playback_speed=1.5)
    config = set_media_state({}, tmp_path / "movie.mp4", state)
    save_config(config_path, config)

    loaded = media_state_from_config(load_config(config_path), tmp_path / "movie.mp4")

    assert loaded is not None
    assert loaded.position == 25
    assert loaded.audio_stream_index == 2
    assert loaded.subtitle_source == "subs.srt"
    assert loaded.subtitle_delay == 0.25
    assert loaded.volume == 0.5
    assert loaded.playback_speed == 1.5


def test_anime_history_round_trip_preserves_unknown_keys(tmp_path: Path) -> None:
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
    assert resumable_position(MediaState(position=4), 100) is None
    assert resumable_position(MediaState(position=98), 100) is None
    assert resumable_position(MediaState(position=50), 100) == 50
    assert resumable_position(MediaState(position=150), 100) is None


def test_corrupt_config_returns_empty(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text("{not json", encoding="utf-8")

    assert load_config(config) == {}

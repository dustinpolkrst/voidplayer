from __future__ import annotations

from pathlib import Path

from ffmpeg_pywrapper.player.config_store import (
    MediaState,
    load_config,
    media_state_from_config,
    recent_files_from_config,
    resumable_position,
    save_config,
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


def test_resumable_position_skips_edges() -> None:
    assert resumable_position(MediaState(position=4), 100) is None
    assert resumable_position(MediaState(position=98), 100) is None
    assert resumable_position(MediaState(position=50), 100) == 50
    assert resumable_position(MediaState(position=150), 100) is None


def test_corrupt_config_returns_empty(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text("{not json", encoding="utf-8")

    assert load_config(config) == {}

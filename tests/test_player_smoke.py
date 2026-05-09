from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from ffmpeg_pywrapper.media import MediaInfo, MediaSource, StreamInfo


def _window(monkeypatch, tmp_path=None):  # noqa: ANN001
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    if tmp_path is not None:
        monkeypatch.setattr(app_module, "user_config_path", lambda: tmp_path / "config.json")
    monkeypatch.setattr(app_module, "load_recent_files", lambda path=None: [])
    monkeypatch.setattr(app_module, "save_recent_files", lambda recent_files, path=None, *, limit=10: None)
    app = qt_widgets.QApplication.instance() or qt_widgets.QApplication(["voidplayer-test"])
    return app_module, app_module.PlayerWindow(theme_name="default")


def test_player_window_starts_as_anime_only_shell(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)

    try:
        assert window.windowTitle() == "VoidPlayer"
        assert "#0d1017" in window.styleSheet()
        assert "#4f8cff" in window.styleSheet()
        assert window.anime_home.objectName() == "animeHome"
        assert window.anime_home.findChild(app_module.QLabel, "animeHomeEyebrow").text() == "ANIME STREAMING"
        assert window.anime_home.findChild(app_module.QFrame, "animeHomeSearchPanel") is not None
        assert window.anime_home.findChild(app_module.QFrame, "animeContinuePanel") is not None
        assert window.anime_home.findChild(app_module.QLabel, "animeHomeTitle").text() == "What are we watching?"
        assert window.anime_home_search_input.placeholderText() == "Search anime"
        assert window.anime_continue_list.item(0).text() == "No anime history yet"
        assert window.video_label.objectName() == "videoSurface"
        assert window.home_button.toolTip() == "Home"
        assert window.play_button.toolTip() == "Play"
        assert window.stop_button.toolTip() == "Stop"
        assert window.next_button.toolTip() == "Next Episode"
        assert window.seek_slider.objectName() == "seekSlider"
        assert window.now_playing_label.objectName() == "nowPlayingLabel"
        assert not hasattr(window, "open_button")
        assert not hasattr(window, "add_playlist_button")
        assert not hasattr(window, "drawer_button")
        assert not hasattr(window, "previous_button")
        assert not hasattr(window, "speed_combo")
        assert not hasattr(window, "audio_stream_combo")
        assert not hasattr(window, "subtitle_combo")
        menus = [action.text() for action in window.menuBar().actions()]
        assert menus == ["Anime", "View", "Help"]
        assert [action.text() for action in window.anime_menu.actions()] == ["Home", "Search Anime...", "Next Episode"]
        assert [action.text() for action in window.view_menu.actions()] == ["Fullscreen", "Mute", "Inspector", "Theme"]
        assert app_module.resource_path("assets", "app-icon.svg").is_file()
    finally:
        window.close()


def test_initial_local_media_launch_still_loads_directly(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    monkeypatch.setattr(app_module, "user_config_path", lambda: tmp_path / "config.json")
    monkeypatch.setattr(app_module, "load_recent_files", lambda path=None: [])
    monkeypatch.setattr(app_module, "save_recent_files", lambda recent_files, path=None, *, limit=10: None)
    loaded = []
    monkeypatch.setattr(app_module.PlayerWindow, "load_and_play", lambda self, source: loaded.append(source))

    app = qt_widgets.QApplication.instance() or qt_widgets.QApplication(["voidplayer-test"])
    media_path = tmp_path / "episode.mkv"
    window = app_module.PlayerWindow(theme_name="default", initial_media=media_path)

    try:
        assert loaded == [app_module.MediaSource.from_path(media_path)]
        assert window.current_source == app_module.MediaSource.from_path(media_path)
        assert window.playlist == [app_module.MediaSource.from_path(media_path)]
    finally:
        window.close()


def test_anime_home_continue_item_plays_single_current_source(monkeypatch, tmp_path) -> None:
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    config_path = tmp_path / "config.json"
    config = app_module.set_anime_history_item(
        {},
        app_module.AnimeHistoryItem(
            title="Example",
            show_id="show-1",
            episode="7",
            mode="sub",
            stream_url="https://example.test/episode-7.mp4",
            display_name="Example - Episode 7",
            position=61,
            subtitle_url="https://example.test/episode-7.vtt",
        ),
    )
    app_module.save_config(config_path, config)

    class ImmediateThread:
        def __init__(self, target, daemon=False):  # noqa: ANN001, FBT002
            self.target = target

        def start(self) -> None:
            self.target()

    class FakeAnimeClient:
        def fast_stream_for_episode(self, episode):  # noqa: ANN001
            return app_module.AnimeStream(
                url="https://example.test/fresh-episode-7.mp4",
                quality="direct",
                title=episode.title,
                episode=episode.number,
                show_id=episode.show_id,
                mode=episode.mode,
                referrer="https://allanime.day",
            )

    monkeypatch.setattr(app_module.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(app_module, "user_config_path", lambda: config_path)
    app_module, window = _window(monkeypatch)
    window.config["anime_disclaimer_accepted"] = True
    window.anime_client = FakeAnimeClient()
    loaded = []
    monkeypatch.setattr(window, "load_and_play", lambda source: loaded.append(source))

    try:
        item = window.anime_continue_list.item(0)
        window.play_anime_history_item(item)

        assert window.current_source is not None
        assert window.current_source.location == "https://example.test/fresh-episode-7.mp4"
        assert window.current_source.metadata == {
            "kind": "anime",
            "show_id": "show-1",
            "title": "Example",
            "episode": "7",
            "mode": "sub",
            "resume_position": "61.000000",
        }
        assert loaded == [window.current_source]
    finally:
        window.close()


def test_continue_watching_resumes_saved_anime_position(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)
    source = MediaSource(
        location="https://example.test/fresh-episode-8.mp4",
        title="Example - Episode 8",
        metadata={"kind": "anime", "show_id": "show-1", "title": "Example", "episode": "8", "mode": "sub", "resume_position": "61.0"},
    )
    media = MediaInfo(path=source.location, duration=120.0, streams=(StreamInfo(index=0, codec_type="video", codec_name="h264"),))
    seeks = []
    monkeypatch.setattr(window.player, "load", lambda loaded_source: media)
    monkeypatch.setattr(window.player, "seek", lambda position: seeks.append(position))
    monkeypatch.setattr(window.player, "play", lambda: None)

    try:
        window.play_source(source)

        assert window.current_source == source
        assert seeks == [61.0]
        assert "Resumed at" in window.statusBar().currentMessage()
    finally:
        window.close()


def test_anime_source_load_updates_continue_watching(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)
    source = MediaSource(
        location="https://example.test/episode-4.mp4",
        title="Example - Episode 4",
        metadata={"kind": "anime", "show_id": "show-1", "title": "Example", "episode": "4", "mode": "dub"},
    )
    media = MediaInfo(path=source.location, duration=100.0, streams=(StreamInfo(index=0, codec_type="video", codec_name="h264"),))
    monkeypatch.setattr(window.player, "load", lambda loaded_source: media)
    monkeypatch.setattr(window.player, "play", lambda: None)

    try:
        window.play_source(source)

        history = app_module.anime_history_from_config(app_module.load_config(tmp_path / "config.json"))
        assert len(history) == 1
        assert history[0].display_name == "Example - Episode 4"
        assert history[0].mode == "dub"
        assert window.anime_continue_list.item(0).text().startswith("Example - Episode 4")
        assert window.now_playing_label.text() == "Now playing: Example - Episode 4 (DUB)"
    finally:
        window.close()


def test_show_anime_home_saves_and_clears_current_source(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)
    source = MediaSource(
        location="https://example.test/episode-9.mp4",
        title="Example - Episode 9",
        metadata={"kind": "anime", "show_id": "show-1", "title": "Example", "episode": "9", "mode": "sub"},
    )
    media = MediaInfo(path=source.location, duration=120.0, streams=(StreamInfo(index=0, codec_type="video", codec_name="h264"),))
    monkeypatch.setattr(window.player, "load", lambda loaded_source: media)
    monkeypatch.setattr(window.player, "play", lambda: None)
    monkeypatch.setattr(window.player, "stop", lambda: None)
    monkeypatch.setattr(window.player, "master_position", lambda: 0.0)

    try:
        window.play_source(source)
        window._last_position = 44.0
        window.show_anime_home()

        assert window.anime_home.isHidden() is False
        assert window.current_source is None
        assert window.playlist == []
        assert window.now_playing_label.text() == ""
        assert window.seek_slider.value() == 0
        history = app_module.anime_history_from_config(app_module.load_config(tmp_path / "config.json"))
        assert history[0].position == 44.0
    finally:
        window.close()


def test_video_click_toggles_playback_when_media_loaded(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)
    qt_core = pytest.importorskip("PySide6.QtCore")

    class Event:
        def button(self):  # noqa: ANN201
            return qt_core.Qt.MouseButton.LeftButton

    calls = []
    window.player.media = MediaInfo(path="movie.mp4", duration=10, streams=())
    monkeypatch.setattr(window, "toggle_playback", lambda: calls.append("toggle"))

    try:
        window._video_click(Event())

        assert calls == ["toggle"]
    finally:
        window.close()


def test_anime_home_layout_stacks_on_smaller_windows(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)

    try:
        window.resize(700, 620)
        window._update_anime_home_layout()

        assert window.anime_home_layout.direction() == app_module.QBoxLayout.Direction.TopToBottom
        assert window.anime_home_search_row.direction() == app_module.QBoxLayout.Direction.LeftToRight
        assert window.anime_continue_panel.minimumHeight() == 220

        window.resize(560, 620)
        window._update_anime_home_layout()

        assert window.anime_home_search_row.direction() == app_module.QBoxLayout.Direction.TopToBottom
    finally:
        window.close()


def test_theme_menu_lists_dark_catppuccin_themes(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)

    try:
        labels = [action.text() for action in window.theme_menu.actions()]

        assert labels == ["VoidPlayer", "Catppuccin Frappe", "Catppuccin Macchiato", "Catppuccin Mocha"]
        assert window.current_theme_name == "default"
        assert app_module.PACKAGED_THEMES["catppuccin-mocha"] == "Catppuccin Mocha"
    finally:
        window.close()


def test_select_theme_applies_and_persists_packaged_theme(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)

    try:
        window.select_theme("catppuccin-mocha")

        assert window.current_theme_name == "catppuccin-mocha"
        assert "#1e1e2e" in window.styleSheet()
        assert app_module.load_config(tmp_path / "config.json")["theme"] == "catppuccin-mocha"
    finally:
        window.close()


def test_custom_toolbar_svgs_are_small_icon_friendly() -> None:
    from ffmpeg_pywrapper.player.app import resource_path

    for icon_name in ("chevron-down.svg", "play.svg", "pause.svg", "stop.svg", "next.svg"):
        svg = resource_path("assets", icon_name).read_text(encoding="utf-8")
        assert 'viewBox="0 0 64 64"' in svg
        assert "<text" not in svg.lower()


def test_combo_chevron_svg_matches_theme_icon_constraints() -> None:
    from ffmpeg_pywrapper.player.app import resource_path

    svg = resource_path("assets", "chevron-down.svg").read_text(encoding="utf-8")

    assert 'viewBox="0 0 64 64"' in svg
    assert 'stroke="#aeb7c6"' in svg
    assert 'stroke-width="6"' in svg
    assert 'fill="none"' in svg
    assert "background" not in svg.lower()


def test_recent_files_round_trip(tmp_path) -> None:
    from ffmpeg_pywrapper.player.app import load_recent_files, save_recent_files

    config = tmp_path / "config.json"
    save_recent_files([tmp_path / "a.mp4", tmp_path / "b.mp4", tmp_path / "a.mp4"], config_path=config)

    assert load_recent_files(config) == [tmp_path / "a.mp4", tmp_path / "b.mp4"]


def test_remote_load_does_not_run_duplicate_probe(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)
    source = MediaSource(location="https://example.test/video.mp4", title="Remote")
    media = MediaInfo(path=source.location, duration=10.0, streams=(StreamInfo(index=0, codec_type="video", codec_name="h264"),))
    monkeypatch.setattr(window.player, "load", lambda loaded_source: media)
    monkeypatch.setattr(window.player, "play", lambda: None)
    monkeypatch.setattr(app_module, "probe", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("remote probe should be skipped")))

    try:
        window.play_source(source)

        assert window._current_probe_data is None
        assert window.chapters == ()
        assert "Remote" in window.statusBar().currentMessage()
    finally:
        window.close()


def test_anime_browser_dialog_constructs_offscreen(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    app = qt_widgets.QApplication.instance() or qt_widgets.QApplication(["voidplayer-test"])
    dialog = app_module.AnimeBrowserDialog()

    try:
        assert dialog.windowTitle() == "Search Anime"
        assert dialog.mode == "sub"
        assert dialog.search_input.objectName() == "animeSearchInput"
        assert dialog.results_list.objectName() == "animeResultsList"
        assert dialog.play_button.isEnabled() is False
    finally:
        dialog.close()


def test_play_next_on_anime_source_resolves_and_replaces_current(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)

    class ImmediateThread:
        def __init__(self, target, daemon=False):  # noqa: ANN001, FBT002
            self.target = target

        def start(self) -> None:
            self.target()

    class FakeAnimeClient:
        def next_episode(self, episode):  # noqa: ANN001
            return app_module.AnimeEpisode(show_id=episode.show_id, title=episode.title, number="2", mode=episode.mode)

        def fast_stream_for_episode(self, episode):  # noqa: ANN001
            return app_module.AnimeStream(
                url="https://example.test/episode-2.mp4",
                quality="direct",
                title=episode.title,
                episode=episode.number,
                show_id=episode.show_id,
                mode=episode.mode,
            )

    monkeypatch.setattr(app_module.threading, "Thread", ImmediateThread)
    window.anime_client = FakeAnimeClient()
    loaded = []
    monkeypatch.setattr(window, "load_and_play", lambda source: loaded.append(source))
    window.current_source = MediaSource(
        location="https://example.test/episode-1.mp4",
        title="Example - Episode 1",
        metadata={"kind": "anime", "show_id": "show-1", "title": "Example", "episode": "1", "mode": "sub"},
    )

    try:
        window.play_next()

        assert window.current_source is not None
        assert window.current_source.metadata["episode"] == "2"
        assert window.current_source.location == "https://example.test/episode-2.mp4"
        assert loaded == [window.current_source]
    finally:
        window.close()


def test_next_anime_episode_updates_continue_watching(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)

    class ImmediateThread:
        def __init__(self, target, daemon=False):  # noqa: ANN001, FBT002
            self.target = target

        def start(self) -> None:
            self.target()

    class FakeAnimeClient:
        def next_episode(self, episode):  # noqa: ANN001
            return app_module.AnimeEpisode(show_id=episode.show_id, title=episode.title, number="2", mode=episode.mode)

        def fast_stream_for_episode(self, episode):  # noqa: ANN001
            return app_module.AnimeStream(
                url="https://example.test/episode-2.mp4",
                quality="direct",
                title=episode.title,
                episode=episode.number,
                show_id=episode.show_id,
                mode=episode.mode,
            )

    monkeypatch.setattr(app_module.threading, "Thread", ImmediateThread)
    window.anime_client = FakeAnimeClient()
    media = MediaInfo(path="https://example.test/episode-2.mp4", duration=100, streams=(StreamInfo(index=0, codec_type="video", codec_name="h264"),))
    monkeypatch.setattr(window.player, "load", lambda source: media)
    monkeypatch.setattr(window.player, "play", lambda: None)
    window.current_source = MediaSource(
        location="https://example.test/episode-1.mp4",
        title="Example - Episode 1",
        metadata={"kind": "anime", "show_id": "show-1", "title": "Example", "episode": "1", "mode": "sub"},
    )

    try:
        window.play_next()

        history = app_module.anime_history_from_config(app_module.load_config(tmp_path / "config.json"))
        assert len(history) == 2
        assert history[0].episode == "2"
        assert history[0].stream_url == "https://example.test/episode-2.mp4"
        assert history[1].episode == "1"
    finally:
        window.close()


def test_anime_browser_ignores_stale_search_results(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    app = qt_widgets.QApplication.instance() or qt_widgets.QApplication(["voidplayer-test"])
    dialog = app_module.AnimeBrowserDialog()

    try:
        dialog._active_search_request = "search:2"
        dialog._handle_worker_result("search:1", [], None)

        assert dialog.results_list.count() == 0
        assert dialog.search_button.isEnabled() is True
    finally:
        dialog.close()

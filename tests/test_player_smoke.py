from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def test_player_window_starts_offscreen_with_default_theme(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    monkeypatch.setattr(app_module, "load_recent_files", lambda path=None: [])
    monkeypatch.setattr(app_module, "save_recent_files", lambda recent_files, path=None, *, limit=10: None)
    QApplication = qt_widgets.QApplication

    app = QApplication.instance() or QApplication(["voidplayer-test"])
    window = app_module.PlayerWindow(theme_name="default")

    try:
        assert window.windowTitle() == "VoidPlayer"
        assert "#0d1017" in window.styleSheet()
        assert "#4f8cff" in window.styleSheet()
        assert window.video_label.objectName() == "videoSurface"
        assert window.play_button.toolTip() == "Play"
        assert window.stop_button.toolTip() == "Stop"
        assert window.add_playlist_button.toolTip() == "Add to Playlist"
        assert window.previous_button.toolTip() == "Previous"
        assert window.next_button.toolTip() == "Next"
        assert window.seek_slider.objectName() == "seekSlider"
        assert window.seek_slider.minimumHeight() >= 34
        assert window.audio_stream_combo.objectName() == "audioStreamCombo"
        assert window.subtitle_combo.objectName() == "subtitleCombo"
        assert window.playlist_panel.objectName() == "playlistPanel"
        assert window.playlist_header.objectName() == "playlistHeader"
        assert window.playlist_widget.minimumWidth() >= 300
        assert window.speed_combo.currentText() == "1x"
        window.toggle_playlist_drawer()
        assert window.playlist_panel.isHidden() is False
        window.toggle_playlist_drawer()
        window.toggle_mute()
        assert window.player.settings.muted is True
        assert app_module.resource_path("assets", "app-icon.svg").is_file()
        assert app_module.resource_path("assets", "open-media.svg").is_file()
        for icon_name in (
            "add-playlist.svg",
            "playlist.svg",
            "previous.svg",
            "play.svg",
            "pause.svg",
            "stop.svg",
            "next.svg",
            "remove.svg",
            "clear.svg",
        ):
            assert app_module.resource_path("assets", icon_name).is_file()
        assert app_module.resource_path("themes", "default", "theme.toml").is_file()
    finally:
        window.close()


def test_custom_toolbar_svgs_are_small_icon_friendly() -> None:
    from ffmpeg_pywrapper.player.app import resource_path

    icon_names = (
        "open-media.svg",
        "add-playlist.svg",
        "playlist.svg",
        "previous.svg",
        "play.svg",
        "pause.svg",
        "stop.svg",
        "next.svg",
        "remove.svg",
        "clear.svg",
    )

    for icon_name in icon_names:
        svg = resource_path("assets", icon_name).read_text(encoding="utf-8")
        assert 'viewBox="0 0 64 64"' in svg
        assert "<text" not in svg.lower()


def test_recent_files_round_trip(tmp_path) -> None:
    from ffmpeg_pywrapper.player.app import load_recent_files, save_recent_files

    config = tmp_path / "config.json"
    save_recent_files([tmp_path / "a.mp4", tmp_path / "b.mp4", tmp_path / "a.mp4"], config_path=config)

    assert load_recent_files(config) == [tmp_path / "a.mp4", tmp_path / "b.mp4"]


def test_playlist_drawer_tracks_current_item(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    monkeypatch.setattr(app_module, "load_recent_files", lambda path=None: [])
    monkeypatch.setattr(app_module, "save_recent_files", lambda recent_files, path=None, *, limit=10: None)
    QApplication = qt_widgets.QApplication

    app = QApplication.instance() or QApplication(["voidplayer-test"])
    window = app_module.PlayerWindow(theme_name="default")
    loaded = []
    monkeypatch.setattr(window, "load_and_play", lambda path: loaded.append(path))

    try:
        window.set_playlist([Path("a.mp4"), Path("b.mp4")], start_index=1)

        assert loaded == [Path("b.mp4")]
        assert window.playlist_widget.count() == 2
        assert window.playlist_widget.currentRow() == 1
        assert window.playlist_count_label.text() == "2 items"
    finally:
        window.close()


def test_add_to_playlist_appends_without_changing_current(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    monkeypatch.setattr(app_module, "load_recent_files", lambda path=None: [])
    monkeypatch.setattr(app_module, "save_recent_files", lambda recent_files, path=None, *, limit=10: None)
    QApplication = qt_widgets.QApplication

    app = QApplication.instance() or QApplication(["voidplayer-test"])
    window = app_module.PlayerWindow(theme_name="default")
    loaded = []
    monkeypatch.setattr(window, "load_and_play", lambda path: loaded.append(path))

    try:
        window.set_playlist([Path("a.mp4"), Path("b.mp4")], start_index=1)
        window.add_to_playlist([Path("c.mp4"), Path("d.mp4")])

        assert window.playlist == [Path("a.mp4"), Path("b.mp4"), Path("c.mp4"), Path("d.mp4")]
        assert window.playlist_index == 1
        assert loaded == [Path("b.mp4")]
        assert window.playlist_count_label.text() == "4 items"
    finally:
        window.close()


def test_playlist_repeat_and_remove(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    monkeypatch.setattr(app_module, "load_recent_files", lambda path=None: [])
    monkeypatch.setattr(app_module, "save_recent_files", lambda recent_files, path=None, *, limit=10: None)
    QApplication = qt_widgets.QApplication

    app = QApplication.instance() or QApplication(["voidplayer-test"])
    window = app_module.PlayerWindow(theme_name="default")
    loaded = []
    monkeypatch.setattr(window, "load_and_play", lambda path: loaded.append(path))
    monkeypatch.setattr(window, "save_current_media_state", lambda: None)

    try:
        window.set_playlist([Path("a.mp4"), Path("b.mp4")], start_index=1)
        window.repeat_mode = "all"
        window.play_next()
        assert window.playlist_index == 0
        window.remove_selected_playlist_item()
        assert len(window.playlist) == 1
    finally:
        window.close()

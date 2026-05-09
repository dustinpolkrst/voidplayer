from __future__ import annotations

import importlib

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
        assert window.previous_button.toolTip() == "Previous"
        assert window.next_button.toolTip() == "Next"
        assert window.seek_slider.objectName() == "seekSlider"
        assert window.audio_stream_combo.objectName() == "audioStreamCombo"
        assert app_module.resource_path("assets", "app-icon.svg").is_file()
        assert app_module.resource_path("themes", "default", "theme.toml").is_file()
    finally:
        window.close()


def test_recent_files_round_trip(tmp_path) -> None:
    from ffmpeg_pywrapper.player.app import load_recent_files, save_recent_files

    config = tmp_path / "config.json"
    save_recent_files([tmp_path / "a.mp4", tmp_path / "b.mp4", tmp_path / "a.mp4"], config_path=config)

    assert load_recent_files(config) == [tmp_path / "a.mp4", tmp_path / "b.mp4"]

from __future__ import annotations

import importlib

import pytest


def test_player_window_starts_offscreen_with_default_theme(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
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
        assert window.seek_slider.objectName() == "seekSlider"
        assert app_module.resource_path("assets", "app-icon.svg").is_file()
        assert app_module.resource_path("themes", "default", "theme.toml").is_file()
    finally:
        window.close()

from __future__ import annotations

from pathlib import Path

import pytest

from ffmpeg_pywrapper.player import app as player_app
from ffmpeg_pywrapper.player import theme as theme_module


def test_default_theme_renders_current_colors() -> None:
    theme = theme_module.load_theme()
    stylesheet = theme_module.render_stylesheet(theme)

    assert "#070a12" in stylesheet
    assert "#1b8cff" in stylesheet
    assert "chevron-down.svg" in stylesheet
    assert "QLabel#animeHomeEyebrow" in stylesheet
    assert "QFrame#animeHomeSearchPanel" in stylesheet
    assert "QFrame#animeContinuePanel" in stylesheet
    assert "qlineargradient" in stylesheet
    assert "rgba(27, 140, 255, 0.34)" in stylesheet
    assert "QFrame#controlBar" in stylesheet
    assert "border-left: 4px solid transparent" not in stylesheet
    assert "{{" not in stylesheet


def test_packaged_themes_render_cinematic_panel_tokens() -> None:
    for theme_name in theme_module.PACKAGED_THEMES:
        stylesheet = theme_module.render_stylesheet(theme_module.load_theme(theme_name))

        assert "QFrame#animeHome" in stylesheet
        assert "QFrame#animeContinuePanel" in stylesheet
        assert "QFrame#controlBar" in stylesheet
        assert "rgba(" in stylesheet
        assert "qlineargradient" in stylesheet
        assert "{{" not in stylesheet


def test_packaged_dark_catppuccin_themes_render() -> None:
    for theme_name in ("catppuccin-frappe", "catppuccin-macchiato", "catppuccin-mocha"):
        theme = theme_module.load_theme(theme_name)
        stylesheet = theme_module.render_stylesheet(theme)

        assert theme_name in theme.path
        assert "chevron-down.svg" in stylesheet
        assert "QLabel#animeHomeEyebrow" in stylesheet
        assert "QFrame#animeHomeSearchPanel" in stylesheet
        assert "QFrame#animeContinuePanel" in stylesheet
        assert "{{" not in stylesheet


def test_continue_watching_action_button_is_styled_in_all_packaged_themes() -> None:
    for theme_name in theme_module.PACKAGED_THEMES:
        stylesheet = theme_module.render_stylesheet(theme_module.load_theme(theme_name))

        assert "QPushButton#animeContinueActionButton {" in stylesheet
        assert "QPushButton#animeContinueActionButton:hover" in stylesheet
        assert "QPushButton#animeContinueActionButton:disabled" in stylesheet
        assert "QListWidget#animeContinueList::item" in stylesheet
        assert "{{" not in stylesheet


def test_show_detail_widgets_are_styled_in_all_packaged_themes() -> None:
    for theme_name in theme_module.PACKAGED_THEMES:
        stylesheet = theme_module.render_stylesheet(theme_module.load_theme(theme_name))

        assert "QFrame#animeShowDetail" in stylesheet
        assert "QListWidget#animeShowEpisodeList" in stylesheet


def test_packaged_resources_are_available() -> None:
    assert player_app.resource_path("assets", "app-icon.svg").name == "app-icon.svg"
    theme = theme_module.load_theme()

    assert "themes" in theme.path
    assert "default" in theme.path


def test_missing_required_token_raises_theme_error(tmp_path: Path) -> None:
    theme_dir = tmp_path / "broken"
    theme_dir.mkdir()
    (theme_dir / "theme.toml").write_text("[color]\nwindow_background = '#000000'\n", encoding="utf-8")
    (theme_dir / "style.qss").write_text("QMainWindow { color: {{ color.text_primary }}; }", encoding="utf-8")

    with pytest.raises(theme_module.ThemeError, match="color.text_primary"):
        theme_module.load_theme("broken", theme_dir)


def test_custom_theme_path_loads_and_renders(tmp_path: Path) -> None:
    theme_dir = tmp_path / "custom"
    theme_dir.mkdir()
    (theme_dir / "theme.toml").write_text(
        """
[color]
window_background = "#111111"
text_primary = "#eeeeee"
""",
        encoding="utf-8",
    )
    (theme_dir / "style.qss").write_text(
        "QMainWindow { background: {{ color.window_background }}; color: {{ color.text_primary }}; }",
        encoding="utf-8",
    )

    theme = theme_module.load_theme("custom", theme_dir)
    stylesheet = theme_module.render_stylesheet(theme)

    assert "#111111" in stylesheet
    assert "#eeeeee" in stylesheet


def test_player_theme_fallback_loads_default() -> None:
    class StatusBar:
        def __init__(self) -> None:
            self.message = ""

        def showMessage(self, message: str) -> None:
            self.message = message

    class Window:
        def __init__(self) -> None:
            self.status_bar = StatusBar()
            self.stylesheet = ""

        def statusBar(self) -> StatusBar:
            return self.status_bar

        def setStyleSheet(self, stylesheet: str) -> None:
            self.stylesheet = stylesheet

    window = Window()

    player_app.PlayerWindow._apply_theme(window, "missing-theme", None)

    assert "#070a12" in window.stylesheet
    assert "loaded default theme" in window.status_bar.message

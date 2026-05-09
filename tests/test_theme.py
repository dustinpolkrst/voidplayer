from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


PLAYER_DIR = Path(__file__).resolve().parents[1] / "examples" / "simple_player"


@pytest.fixture
def theme_module(monkeypatch):
    monkeypatch.syspath_prepend(str(PLAYER_DIR))
    module_path = PLAYER_DIR / "theme.py"
    spec = importlib.util.spec_from_file_location("simple_player_theme", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_default_theme_renders_current_colors(theme_module) -> None:
    theme = theme_module.load_theme()
    stylesheet = theme_module.render_stylesheet(theme)

    assert "#0d1017" in stylesheet
    assert "#4f8cff" in stylesheet
    assert "{{" not in stylesheet


def test_missing_required_token_raises_theme_error(theme_module, tmp_path: Path) -> None:
    theme_dir = tmp_path / "broken"
    theme_dir.mkdir()
    (theme_dir / "theme.toml").write_text("[color]\nwindow_background = '#000000'\n", encoding="utf-8")
    (theme_dir / "style.qss").write_text("QMainWindow { color: {{ color.text_primary }}; }", encoding="utf-8")

    with pytest.raises(theme_module.ThemeError, match="color.text_primary"):
        theme_module.load_theme("broken", theme_dir)


def test_custom_theme_path_loads_and_renders(theme_module, tmp_path: Path) -> None:
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


def test_player_theme_fallback_loads_default(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(PLAYER_DIR))
    module_path = PLAYER_DIR / "main.py"
    spec = importlib.util.spec_from_file_location("simple_player_main_theme_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

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

    module.PlayerWindow._apply_theme(window, "missing-theme", None)

    assert "#0d1017" in window.stylesheet
    assert "loaded default theme" in window.status_bar.message

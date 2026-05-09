from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import ExitStack
from importlib.resources import as_file, files
from pathlib import Path

from ffmpeg_pywrapper import format_timestamp
from ffmpeg_pywrapper.playback import DecodeLoopPlayer, PlaybackState, VideoFrame, configure_debug_logging

from .theme import DEFAULT_THEME, ThemeError, load_theme, render_stylesheet

try:
    from PIL.ImageQt import ImageQt
    from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
    from PySide6.QtGui import QAction, QIcon, QImage, QKeySequence, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QSlider,
        QStyle,
        QStatusBar,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - manual app dependency guard
    raise SystemExit("Install VoidPlayer with its GUI dependencies before launching the player.") from exc


def resource_path(*parts: str) -> Path:
    resource = files(__package__).joinpath(*parts)
    return Path(str(resource))


def user_config_path() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "VoidPlayer" / "config.json"
    return Path.home() / ".config" / "voidplayer" / "config.json"


def load_recent_files(config_path: Path | None = None) -> list[Path]:
    path = config_path or user_config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    files = data.get("recent_files", [])
    if not isinstance(files, list):
        return []
    return [Path(item) for item in files if isinstance(item, str)]


def save_recent_files(recent_files: list[Path], config_path: Path | None = None, *, limit: int = 10) -> None:
    path = config_path or user_config_path()
    unique: list[str] = []
    for item in recent_files:
        value = str(Path(item))
        if value not in unique:
            unique.append(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"recent_files": unique[:limit]}, indent=2), encoding="utf-8")


class PlayerSignals(QObject):
    frame_ready = Signal(object)
    state_changed = Signal(object)
    error = Signal(object)
    warning = Signal(object)


class PlayerWindow(QMainWindow):
    def __init__(
        self,
        *,
        theme_name: str = DEFAULT_THEME,
        theme_path: Path | None = None,
        initial_media: Path | None = None,
    ) -> None:
        super().__init__()
        self._resources = ExitStack()
        self._app_icon = self._resource_file("assets", "app-icon.svg")
        self._open_media_icon = self._resource_file("assets", "open-media.svg")
        self.setWindowTitle("VoidPlayer")
        self.setWindowIcon(QIcon(str(self._app_icon)))
        self.resize(1000, 620)
        self.signals = PlayerSignals()
        self.signals.frame_ready.connect(self.show_frame)
        self.signals.state_changed.connect(self.on_state)
        self.signals.error.connect(self.on_error)
        self.signals.warning.connect(self.on_warning)
        self.player = DecodeLoopPlayer(
            on_frame=self.signals.frame_ready.emit,
            on_state=self.signals.state_changed.emit,
            on_error=self.signals.error.emit,
            on_warning=self.signals.warning.emit,
        )
        self.duration = 0.0
        self._seeking = False
        self._last_pixmap: QPixmap | None = None
        self.playlist: list[Path] = []
        self.playlist_index = -1
        self.recent_files = load_recent_files()

        self._build_ui()
        self._apply_theme(theme_name, theme_path)
        self.open_action = QAction("Open", self)
        self.open_action.setIcon(QIcon(str(self._open_media_icon)))
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.open_file)
        self.addAction(self.open_action)
        self.open_button.clicked.connect(self.open_file)
        self.previous_button.clicked.connect(self.play_previous)
        self.play_button.clicked.connect(self.toggle_playback)
        self.stop_button.clicked.connect(self.player.stop)
        self.next_button.clicked.connect(self.play_next)
        self.seek_slider.sliderPressed.connect(self._begin_seek)
        self.seek_slider.sliderReleased.connect(self._finish_seek)
        self.volume_slider.valueChanged.connect(lambda value: self.player.set_volume(value / 100))
        self.audio_stream_combo.currentIndexChanged.connect(lambda _index: self._select_audio_stream())

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_position)
        self.timer.start(100)

        if initial_media is not None:
            self.set_playlist([initial_media], start_index=0)

    def _resource_file(self, *parts: str) -> Path:
        resource = files(__package__).joinpath(*parts)
        return self._resources.enter_context(as_file(resource))

    def _build_ui(self) -> None:
        self.video_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.video_label.setObjectName("videoSurface")
        self.video_label.setText("Open a video file")
        self.video_label.setMinimumSize(640, 360)

        self.open_button = self._tool_button("Open", QIcon(str(self._open_media_icon)))
        self.previous_button = self._tool_button("Previous", QStyle.StandardPixmap.SP_MediaSkipBackward)
        self.play_button = self._tool_button("Play", QStyle.StandardPixmap.SP_MediaPlay)
        self.stop_button = self._tool_button("Stop", QStyle.StandardPixmap.SP_MediaStop)
        self.next_button = self._tool_button("Next", QStyle.StandardPixmap.SP_MediaSkipForward)

        self.elapsed_label = QLabel("00:00:00.00")
        self.elapsed_label.setObjectName("timeLabel")
        self.total_label = QLabel("00:00:00.00")
        self.total_label.setObjectName("timeLabel")

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setObjectName("seekSlider")

        self.volume_label = QLabel("Volume")
        self.volume_label.setObjectName("volumeLabel")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(130)
        self.volume_slider.setObjectName("volumeSlider")
        self.audio_stream_combo = QComboBox()
        self.audio_stream_combo.setObjectName("audioStreamCombo")
        self.audio_stream_combo.setMinimumWidth(140)

        transport = QHBoxLayout()
        transport.setContentsMargins(0, 0, 0, 0)
        transport.setSpacing(8)
        transport.addWidget(self.open_button)
        transport.addWidget(self.previous_button)
        transport.addWidget(self.play_button)
        transport.addWidget(self.stop_button)
        transport.addWidget(self.next_button)
        transport.addSpacing(4)
        transport.addWidget(self.elapsed_label)
        transport.addWidget(self.seek_slider, 1)
        transport.addWidget(self.total_label)
        transport.addSpacing(10)
        transport.addWidget(self.volume_label)
        transport.addWidget(self.volume_slider)
        transport.addWidget(self.audio_stream_combo)

        controls = QFrame()
        controls.setObjectName("controlBar")
        controls.setLayout(transport)

        root = QVBoxLayout()
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)
        root.addWidget(self.video_label, 1)
        root.addWidget(controls)

        container = QWidget()
        container.setObjectName("appRoot")
        container.setLayout(root)
        self.setCentralWidget(container)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def _tool_button(self, tooltip: str, icon: QStyle.StandardPixmap | QIcon) -> QToolButton:
        button = QToolButton()
        if isinstance(icon, QIcon):
            button.setIcon(icon)
        else:
            button.setIcon(self.style().standardIcon(icon))
        button.setToolTip(tooltip)
        button.setFixedSize(36, 36)
        button.setIconSize(QSize(20, 20))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _apply_theme(self, theme_name: str = DEFAULT_THEME, theme_path: Path | None = None) -> None:
        try:
            theme = load_theme(theme_name, theme_path)
        except ThemeError as exc:
            theme = load_theme(DEFAULT_THEME)
            self.statusBar().showMessage(f"{exc}; loaded default theme")
        self.setStyleSheet(render_stylesheet(theme))

    def open_file(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open video files",
            "",
            "Video files (*.mp4 *.mkv *.mov *.avi *.webm);;All files (*.*)",
        )
        if paths:
            self.set_playlist([Path(path) for path in paths], start_index=0)

    def set_playlist(self, paths: list[Path], *, start_index: int = 0) -> None:
        if not paths:
            return
        self.playlist = list(paths)
        self.playlist_index = max(0, min(start_index, len(self.playlist) - 1))
        self._load_current_playlist_item()

    def play_next(self) -> None:
        if self.playlist_index + 1 >= len(self.playlist):
            return
        self.playlist_index += 1
        self._load_current_playlist_item()

    def play_previous(self) -> None:
        if self.playlist_index <= 0:
            return
        self.playlist_index -= 1
        self._load_current_playlist_item()

    def _load_current_playlist_item(self) -> None:
        if 0 <= self.playlist_index < len(self.playlist):
            self.load_and_play(self.playlist[self.playlist_index])

    def load_and_play(self, path: Path) -> None:
        try:
            media = self.player.load(path)
            self.duration = media.duration or 0.0
            self._populate_audio_streams()
            self._remember_recent_file(media.path)
            self.statusBar().showMessage(str(media.path))
            self.player.play()
        except Exception as exc:
            self.on_error(exc)

    def toggle_playback(self) -> None:
        if self.player.state == PlaybackState.PLAYING:
            self.player.pause()
        else:
            self.player.play()

    def show_frame(self, frame: VideoFrame) -> None:
        image = ImageQt(frame.image)
        qimage = QImage(image)
        self._last_pixmap = QPixmap.fromImage(qimage)
        self._render_pixmap()

    def on_state(self, state: PlaybackState) -> None:
        if state == PlaybackState.PLAYING:
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
            self.play_button.setToolTip("Pause")
        elif state == PlaybackState.ENDED:
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.play_button.setToolTip("Play")
            self.play_next()
        else:
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.play_button.setToolTip("Play")

    def on_error(self, error: Exception) -> None:
        self.statusBar().showMessage(str(error))

    def on_warning(self, warning: Exception) -> None:
        self.statusBar().showMessage(str(warning))

    def refresh_position(self) -> None:
        position = self.player.master_position()
        if self.duration > 0 and not self._seeking:
            self.seek_slider.setValue(min(1000, int(position / self.duration * 1000)))
        self.elapsed_label.setText(format_timestamp(position))
        self.total_label.setText(format_timestamp(self.duration))

    def _begin_seek(self) -> None:
        self._seeking = True

    def _finish_seek(self) -> None:
        if self.duration > 0:
            self.player.seek(self.seek_slider.value() / 1000 * self.duration)
        self._seeking = False

    def _populate_audio_streams(self) -> None:
        self.audio_stream_combo.blockSignals(True)
        self.audio_stream_combo.clear()
        media = self.player.media
        if media is None or not media.audio_streams:
            self.audio_stream_combo.addItem("No audio", None)
            self.audio_stream_combo.setEnabled(False)
            self.audio_stream_combo.blockSignals(False)
            return
        self.audio_stream_combo.setEnabled(True)
        selected = self.player.selected_audio_stream_index
        selected_row = 0
        for row, stream in enumerate(media.audio_streams):
            label = f"Audio #{stream.index}"
            if stream.language:
                label += f" {stream.language}"
            if stream.codec_name:
                label += f" ({stream.codec_name})"
            self.audio_stream_combo.addItem(label, stream.index)
            if stream.index == selected:
                selected_row = row
        self.audio_stream_combo.setCurrentIndex(selected_row)
        self.audio_stream_combo.blockSignals(False)

    def _select_audio_stream(self) -> None:
        stream_index = self.audio_stream_combo.currentData()
        if stream_index is not None:
            self.player.set_audio_stream(int(stream_index))

    def _remember_recent_file(self, path: Path) -> None:
        self.recent_files = [path, *[item for item in self.recent_files if item != path]]
        save_recent_files(self.recent_files)

    def closeEvent(self, event) -> None:  # noqa: ANN001
        save_recent_files(self.recent_files)
        self.player.close()
        self._resources.close()
        event.accept()

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._render_pixmap()

    def _render_pixmap(self) -> None:
        if self._last_pixmap is None:
            return
        self.video_label.setPixmap(
            self._last_pixmap.scaled(
                self.video_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(prog="voidplayer")
    parser.add_argument("input", nargs="?", type=Path, help="Media file to open")
    parser.add_argument("--debug", action="store_true", help="Enable playback debug logging")
    parser.add_argument("--theme", default=DEFAULT_THEME, help="Theme name from bundled themes")
    parser.add_argument("--theme-path", type=Path, help="Path to a custom theme directory")
    args, qt_args = parser.parse_known_args()

    if args.debug:
        configure_debug_logging(True)
    app = QApplication([sys.argv[0], *qt_args])
    app.setWindowIcon(QIcon(str(resource_path("assets", "app-icon.svg"))))
    window = PlayerWindow(theme_name=args.theme, theme_path=args.theme_path, initial_media=args.input)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
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

        self._build_ui()
        self._apply_theme(theme_name, theme_path)
        self.open_action = QAction("Open", self)
        self.open_action.setIcon(QIcon(str(self._open_media_icon)))
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.open_file)
        self.addAction(self.open_action)
        self.open_button.clicked.connect(self.open_file)
        self.play_button.clicked.connect(self.toggle_playback)
        self.stop_button.clicked.connect(self.player.stop)
        self.seek_slider.sliderPressed.connect(self._begin_seek)
        self.seek_slider.sliderReleased.connect(self._finish_seek)
        self.volume_slider.valueChanged.connect(lambda value: self.player.set_volume(value / 100))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_position)
        self.timer.start(100)

        if initial_media is not None:
            self.load_and_play(initial_media)

    def _resource_file(self, *parts: str) -> Path:
        resource = files(__package__).joinpath(*parts)
        return self._resources.enter_context(as_file(resource))

    def _build_ui(self) -> None:
        self.video_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.video_label.setObjectName("videoSurface")
        self.video_label.setText("Open a video file")
        self.video_label.setMinimumSize(640, 360)

        self.open_button = self._tool_button("Open", QIcon(str(self._open_media_icon)))
        self.play_button = self._tool_button("Play", QStyle.StandardPixmap.SP_MediaPlay)
        self.stop_button = self._tool_button("Stop", QStyle.StandardPixmap.SP_MediaStop)

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

        transport = QHBoxLayout()
        transport.setContentsMargins(0, 0, 0, 0)
        transport.setSpacing(8)
        transport.addWidget(self.open_button)
        transport.addWidget(self.play_button)
        transport.addWidget(self.stop_button)
        transport.addSpacing(4)
        transport.addWidget(self.elapsed_label)
        transport.addWidget(self.seek_slider, 1)
        transport.addWidget(self.total_label)
        transport.addSpacing(10)
        transport.addWidget(self.volume_label)
        transport.addWidget(self.volume_slider)

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
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open video",
            "",
            "Video files (*.mp4 *.mkv *.mov *.avi *.webm);;All files (*.*)",
        )
        if path:
            self.load_and_play(Path(path))

    def load_and_play(self, path: Path) -> None:
        try:
            media = self.player.load(path)
            self.duration = media.duration or 0.0
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

    def closeEvent(self, event) -> None:  # noqa: ANN001
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


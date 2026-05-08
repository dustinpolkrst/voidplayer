from __future__ import annotations

import sys
from pathlib import Path

from ffmpeg_pywrapper import format_timestamp
from ffmpeg_pywrapper.playback import DecodeLoopPlayer, PlaybackState, VideoFrame, configure_debug_logging

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
    raise SystemExit("Install player dependencies first: uv sync --extra player --group player") from exc


ASSET_DIR = Path(__file__).with_name("assets")
APP_ICON = ASSET_DIR / "app-icon.svg"
OPEN_MEDIA_ICON = ASSET_DIR / "open-media.svg"


class PlayerSignals(QObject):
    frame_ready = Signal(object)
    state_changed = Signal(object)
    error = Signal(object)
    warning = Signal(object)


class PlayerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VoidPlayer")
        self.setWindowIcon(QIcon(str(APP_ICON)))
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
        self._apply_theme()
        self.open_action = QAction("Open", self)
        self.open_action.setIcon(QIcon(str(OPEN_MEDIA_ICON)))
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

    def _build_ui(self) -> None:
        self.video_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.video_label.setObjectName("videoSurface")
        self.video_label.setText("Open a video file")
        self.video_label.setMinimumSize(640, 360)

        self.open_button = self._tool_button("Open", QIcon(str(OPEN_MEDIA_ICON)))
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

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #0d1017;
                color: #e7eaf0;
            }
            QWidget#appRoot {
                background: #0d1017;
            }
            QLabel#videoSurface {
                background: #05070b;
                color: #8d96a6;
                border: 1px solid #202635;
                font-size: 16px;
            }
            QFrame#controlBar {
                background: #151a23;
                border: 1px solid #252c3a;
                border-radius: 8px;
                padding: 10px;
            }
            QToolButton {
                background: #242b38;
                color: #f1f4f8;
                border: 1px solid #343d4f;
                border-radius: 6px;
            }
            QToolButton:hover {
                background: #30394a;
                border-color: #4a556d;
            }
            QToolButton:pressed {
                background: #1c2230;
            }
            QLabel#timeLabel {
                color: #c7ceda;
                font-family: Consolas, "Cascadia Mono", monospace;
                font-size: 12px;
                min-width: 78px;
            }
            QLabel#volumeLabel {
                color: #aeb7c6;
                font-size: 12px;
            }
            QSlider::groove:horizontal {
                height: 5px;
                background: #2a3140;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #4f8cff;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                height: 14px;
                margin: -5px 0;
                background: #f1f5fb;
                border: 1px solid #8fb5ff;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #ffffff;
                border-color: #b8d0ff;
            }
            QStatusBar {
                background: #0d1017;
                color: #929cad;
                border-top: 1px solid #1e2532;
            }
            """
        )

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open video",
            "",
            "Video files (*.mp4 *.mkv *.mov *.avi *.webm);;All files (*.*)",
        )
        if not path:
            return
        try:
            media = self.player.load(Path(path))
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
    if "--debug" in sys.argv:
        sys.argv.remove("--debug")
        configure_debug_logging(True)
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(APP_ICON)))
    window = PlayerWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

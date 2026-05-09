from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import ExitStack
from importlib.resources import as_file, files
from pathlib import Path

from ffmpeg_pywrapper import format_timestamp, trim
from ffmpeg_pywrapper.playback import DecodeLoopPlayer, PlaybackState, VideoFrame, configure_debug_logging
from ffmpeg_pywrapper.subtitles import SubtitleError, SubtitleTrack, load_subtitles

from .theme import DEFAULT_THEME, ThemeError, load_theme, render_stylesheet

try:
    from PIL.ImageQt import ImageQt
    from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
    from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QIcon, QImage, QKeySequence, QMouseEvent, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QPushButton,
        QSlider,
        QSplitter,
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
        self.subtitle_track: SubtitleTrack | None = None
        self.subtitle_external_path: Path | None = None
        self._last_position = 0.0

        self.setAcceptDrops(True)
        self._build_ui()
        self._apply_theme(theme_name, theme_path)
        self._build_actions()
        self.open_button.clicked.connect(self.open_file)
        self.previous_button.clicked.connect(self.play_previous)
        self.play_button.clicked.connect(self.toggle_playback)
        self.stop_button.clicked.connect(self.player.stop)
        self.next_button.clicked.connect(self.play_next)
        self.drawer_button.clicked.connect(self.toggle_playlist_drawer)
        self.seek_slider.sliderPressed.connect(self._begin_seek)
        self.seek_slider.sliderReleased.connect(self._finish_seek)
        self.volume_slider.valueChanged.connect(lambda value: self.player.set_volume(value / 100))
        self.audio_stream_combo.currentIndexChanged.connect(lambda _index: self._select_audio_stream())
        self.subtitle_combo.currentIndexChanged.connect(lambda _index: self._select_subtitle_source())
        self.speed_combo.currentTextChanged.connect(self._select_playback_speed)
        self.playlist_widget.itemDoubleClicked.connect(self._play_playlist_item)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_position)
        self.timer.start(100)

        self.controls_timer = QTimer(self)
        self.controls_timer.setSingleShot(True)
        self.controls_timer.timeout.connect(self._hide_controls_if_fullscreen)

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
        self.video_label.mouseDoubleClickEvent = self._video_double_click  # type: ignore[method-assign]

        self.subtitle_label = QLabel(alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.subtitle_label.setObjectName("subtitleOverlay")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.subtitle_label.hide()

        video_layout = QGridLayout()
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.addWidget(self.video_label, 0, 0)
        video_layout.addWidget(self.subtitle_label, 0, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.video_frame = QFrame()
        self.video_frame.setObjectName("videoFrame")
        self.video_frame.setLayout(video_layout)

        self.open_button = self._tool_button("Open", QIcon(str(self._open_media_icon)))
        self.drawer_button = self._tool_button("Playlist", QStyle.StandardPixmap.SP_FileDialogDetailedView)
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
        self.subtitle_combo = QComboBox()
        self.subtitle_combo.setObjectName("subtitleCombo")
        self.subtitle_combo.setMinimumWidth(130)
        self.subtitle_combo.addItem("Subtitles Off", None)
        self.speed_combo = QComboBox()
        self.speed_combo.setObjectName("speedCombo")
        for speed in ("0.5x", "0.75x", "1x", "1.25x", "1.5x", "2x"):
            self.speed_combo.addItem(speed)
        self.speed_combo.setCurrentText("1x")
        self.speed_combo.setFixedWidth(82)

        transport = QHBoxLayout()
        transport.setContentsMargins(0, 0, 0, 0)
        transport.setSpacing(8)
        transport.addWidget(self.open_button)
        transport.addWidget(self.drawer_button)
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
        transport.addWidget(self.speed_combo)
        transport.addWidget(self.audio_stream_combo)
        transport.addWidget(self.subtitle_combo)

        controls = QFrame()
        controls.setObjectName("controlBar")
        controls.setLayout(transport)

        root = QVBoxLayout()
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)
        root.addWidget(self.video_frame, 1)
        root.addWidget(controls)

        player_container = QWidget()
        player_container.setObjectName("appRoot")
        player_container.setLayout(root)

        self.playlist_widget = QListWidget()
        self.playlist_widget.setObjectName("playlistDrawer")
        self.playlist_widget.setMinimumWidth(220)
        self.playlist_widget.hide()

        self.splitter = QSplitter()
        self.splitter.addWidget(player_container)
        self.splitter.addWidget(self.playlist_widget)
        self.splitter.setStretchFactor(0, 1)
        self.setCentralWidget(self.splitter)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def _build_actions(self) -> None:
        self.open_action = QAction("Open", self)
        self.open_action.setIcon(QIcon(str(self._open_media_icon)))
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.open_file)

        self.fullscreen_action = QAction("Fullscreen", self)
        self.fullscreen_action.setShortcut(QKeySequence("F"))
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)

        self.mute_action = QAction("Mute", self)
        self.mute_action.setShortcut(QKeySequence("M"))
        self.mute_action.triggered.connect(self.toggle_mute)

        self.save_frame_action = QAction("Save Frame", self)
        self.save_frame_action.triggered.connect(self.save_current_frame)

        self.export_clip_action = QAction("Export Clip", self)
        self.export_clip_action.triggered.connect(self.export_clip)

        self.load_subtitles_action = QAction("Load Subtitles", self)
        self.load_subtitles_action.triggered.connect(self.load_external_subtitles)

        self.recent_menu = QMenu("Recent", self)
        self._refresh_recent_menu()

        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.open_action)
        file_menu.addMenu(self.recent_menu)
        file_menu.addAction(self.load_subtitles_action)
        file_menu.addAction(self.save_frame_action)
        file_menu.addAction(self.export_clip_action)

        playback_menu = self.menuBar().addMenu("Playback")
        playback_menu.addAction(self.fullscreen_action)
        playback_menu.addAction(self.mute_action)

        for action in (
            self.open_action,
            self.fullscreen_action,
            self.mute_action,
            self.save_frame_action,
            self.export_clip_action,
            self.load_subtitles_action,
        ):
            self.addAction(action)
        self._add_shortcut("Space", self.toggle_playback)
        self._add_shortcut("Left", lambda: self.seek_relative(-5))
        self._add_shortcut("Right", lambda: self.seek_relative(5))
        self._add_shortcut("Shift+Left", lambda: self.seek_relative(-30))
        self._add_shortcut("Shift+Right", lambda: self.seek_relative(30))
        self._add_shortcut("Up", lambda: self.adjust_volume(5))
        self._add_shortcut("Down", lambda: self.adjust_volume(-5))
        self._add_shortcut("N", self.play_next)
        self._add_shortcut("P", self.play_previous)
        self._add_shortcut("Esc", self.exit_fullscreen)

    def _add_shortcut(self, shortcut: str, callback) -> None:  # noqa: ANN001
        action = QAction(self)
        action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(callback)
        self.addAction(action)

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
        self._refresh_playlist_drawer()
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
            self._populate_subtitle_sources()
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
        self._last_position = position
        if self.duration > 0 and not self._seeking:
            self.seek_slider.setValue(min(1000, int(position / self.duration * 1000)))
        self.elapsed_label.setText(format_timestamp(position))
        self.total_label.setText(format_timestamp(self.duration))
        if hasattr(self, "_render_subtitle"):
            self._render_subtitle(position)

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

    def _populate_subtitle_sources(self) -> None:
        self.subtitle_combo.blockSignals(True)
        self.subtitle_combo.clear()
        self.subtitle_combo.addItem("Subtitles Off", None)
        media = self.player.media
        if media is not None:
            for stream in media.subtitle_streams:
                label = f"Subtitle #{stream.index}"
                if stream.language:
                    label += f" {stream.language}"
                if stream.codec_name:
                    label += f" ({stream.codec_name})"
                self.subtitle_combo.addItem(label, stream.index)
        if self.subtitle_external_path is not None:
            self.subtitle_combo.addItem(self.subtitle_external_path.name, str(self.subtitle_external_path))
        self.subtitle_combo.blockSignals(False)

    def _select_subtitle_source(self) -> None:
        source = self.subtitle_combo.currentData()
        self.player.set_subtitle_source(source)
        if isinstance(source, str):
            try:
                self.subtitle_track = load_subtitles(source)
                self.subtitle_external_path = Path(source)
            except (OSError, SubtitleError) as exc:
                self.subtitle_track = None
                self.statusBar().showMessage(str(exc))
        elif source is None:
            self.subtitle_track = None
            self.subtitle_label.hide()

    def load_external_subtitles(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load subtitles", "", "Subtitle files (*.srt *.vtt *.ass);;All files (*.*)")
        if not path:
            return
        try:
            self.subtitle_track = load_subtitles(path)
        except (OSError, SubtitleError) as exc:
            self.statusBar().showMessage(str(exc))
            return
        self.subtitle_external_path = Path(path)
        self._populate_subtitle_sources()
        self.subtitle_combo.setCurrentIndex(self.subtitle_combo.count() - 1)
        self.statusBar().showMessage(f"Loaded subtitles: {self.subtitle_external_path.name}")

    def _render_subtitle(self, position: float) -> None:
        if self.subtitle_track is None:
            return
        text = self.subtitle_track.text_at(position)
        self.subtitle_label.setText(text)
        self.subtitle_label.setVisible(bool(text))

    def _select_playback_speed(self, label: str) -> None:
        if not label:
            return
        self.player.set_playback_speed(float(label.removesuffix("x")))

    def _remember_recent_file(self, path: Path) -> None:
        self.recent_files = [path, *[item for item in self.recent_files if item != path]]
        save_recent_files(self.recent_files)
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        if not hasattr(self, "recent_menu"):
            return
        self.recent_menu.clear()
        if not self.recent_files:
            empty = QAction("No recent files", self)
            empty.setEnabled(False)
            self.recent_menu.addAction(empty)
            return
        for path in self.recent_files[:10]:
            action = QAction(path.name, self)
            action.setToolTip(str(path))
            action.triggered.connect(lambda _checked=False, item=path: self.set_playlist([item], start_index=0))
            self.recent_menu.addAction(action)

    def _refresh_playlist_drawer(self) -> None:
        self.playlist_widget.clear()
        for index, path in enumerate(self.playlist):
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.playlist_widget.addItem(item)
        if 0 <= self.playlist_index < self.playlist_widget.count():
            self.playlist_widget.setCurrentRow(self.playlist_index)

    def _play_playlist_item(self, item: QListWidgetItem) -> None:
        index = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(index, int):
            self.playlist_index = index
            self._load_current_playlist_item()

    def toggle_playlist_drawer(self) -> None:
        self.playlist_widget.setVisible(not self.playlist_widget.isVisible())

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self._show_controls()
        else:
            self.showFullScreen()
            self.controls_timer.start(2500)

    def exit_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self._show_controls()

    def _video_double_click(self, _event: QMouseEvent) -> None:
        self.toggle_fullscreen()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        if self.isFullScreen():
            self._show_controls()
            self.controls_timer.start(2500)

    def _hide_controls_if_fullscreen(self) -> None:
        if self.isFullScreen():
            self.menuBar().hide()
            self.statusBar().hide()

    def _show_controls(self) -> None:
        self.menuBar().show()
        self.statusBar().show()

    def toggle_mute(self) -> None:
        self.player.set_muted(not self.player.settings.muted)
        self.statusBar().showMessage("Muted" if self.player.settings.muted else "Unmuted")

    def seek_relative(self, delta: float) -> None:
        target = max(0.0, self.player.master_position() + delta)
        if self.duration > 0:
            target = min(self.duration, target)
        self.player.seek(target)
        self.refresh_position()

    def adjust_volume(self, delta: int) -> None:
        self.volume_slider.setValue(max(0, min(100, self.volume_slider.value() + delta)))

    def save_current_frame(self) -> None:
        if self._last_pixmap is None:
            self.statusBar().showMessage("No frame available to save")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save frame", "frame.png", "PNG image (*.png);;JPEG image (*.jpg)")
        if path and self._last_pixmap.save(path):
            self.statusBar().showMessage(f"Saved frame: {path}")

    def export_clip(self) -> None:
        if self.player.current_path is None:
            self.statusBar().showMessage("Open a media file before exporting a clip")
            return
        dialog = ClipExportDialog(self._last_position, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            trim(
                self.player.current_path,
                values["output"],
                start=values["start"],
                duration=values["duration"],
                overwrite=values["overwrite"],
            )
        except Exception as exc:
            self.statusBar().showMessage(str(exc))
            return
        self.statusBar().showMessage(f"Exported clip: {values['output']}")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        media_paths = [path for path in paths if path.suffix.lower() in {".mp4", ".mkv", ".mov", ".avi", ".webm"}]
        subtitle_paths = [path for path in paths if path.suffix.lower() in {".srt", ".vtt", ".ass"}]
        if media_paths:
            self.set_playlist(media_paths, start_index=0)
        if subtitle_paths:
            try:
                self.subtitle_track = load_subtitles(subtitle_paths[0])
                self.subtitle_external_path = subtitle_paths[0]
                self._populate_subtitle_sources()
                self.subtitle_combo.setCurrentIndex(self.subtitle_combo.count() - 1)
            except (OSError, SubtitleError) as exc:
                self.statusBar().showMessage(str(exc))
        event.acceptProposedAction()

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


class ClipExportDialog(QDialog):
    def __init__(self, start: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Clip")
        self.start_input = QLineEdit(format_timestamp(start))
        self.duration_input = QLineEdit("10")
        self.output_input = QLineEdit()
        self.overwrite_check = QCheckBox("Overwrite")
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self._browse_output)

        output_row = QHBoxLayout()
        output_row.addWidget(self.output_input, 1)
        output_row.addWidget(browse_button)

        form = QFormLayout()
        form.addRow("Start", self.start_input)
        form.addRow("Duration", self.duration_input)
        form.addRow("Output", output_row)
        form.addRow("", self.overwrite_check)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export clip", "clip.mp4", "Video files (*.mp4 *.mkv *.mov)")
        if path:
            self.output_input.setText(path)

    def values(self) -> dict[str, object]:
        return {
            "start": self.start_input.text(),
            "duration": self.duration_input.text(),
            "output": Path(self.output_input.text()),
            "overwrite": self.overwrite_check.isChecked(),
        }


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

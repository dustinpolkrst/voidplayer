from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from contextlib import ExitStack
from importlib.resources import as_file, files
from pathlib import Path

from ffmpeg_pywrapper.anime import AnimeClient, AnimeClientError, AnimeEpisode, AnimeMode, AnimeSearchResult, AnimeStream, select_quality
from ffmpeg_pywrapper import format_timestamp
from ffmpeg_pywrapper.media import MediaInfo, MediaSource, ensure_media_source
from ffmpeg_pywrapper.playback import DecodeLoopPlayer, PlaybackState, VideoFrame, configure_debug_logging
from ffmpeg_pywrapper.player.config_store import (
    AnimeHistoryItem,
    anime_history_from_config,
    anime_history_progress,
    load_config,
    remove_anime_history_item,
    resumable_position,
    save_config,
    set_anime_history_item,
    should_continue_with_next_episode,
    sorted_anime_history,
)
from ffmpeg_pywrapper.player.show_detail import (
    episode_source_with_resume,
    episode_history_map,
    episode_row_text,
    selected_episode_history,
)

from .theme import DEFAULT_THEME, PACKAGED_THEMES, ThemeError, load_theme, render_stylesheet

try:
    from PIL.ImageQt import ImageQt
    from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
    from PySide6.QtGui import QAction, QActionGroup, QIcon, QImage, QKeySequence, QMouseEvent, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QBoxLayout,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPlainTextEdit,
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


class PlayerSignals(QObject):
    frame_ready = Signal(object)
    state_changed = Signal(object)
    error = Signal(object)
    warning = Signal(object)
    anime_next_ready = Signal(object, object)
    show_detail_episodes_ready = Signal(str, object, object)
    show_detail_stream_ready = Signal(str, object, object)


class AnimeWorkerSignals(QObject):
    finished = Signal(str, object, object)


class PlayerWindow(QMainWindow):
    def __init__(
        self,
        *,
        theme_name: str | None = None,
        theme_path: Path | None = None,
        initial_media: Path | None = None,
    ) -> None:
        super().__init__()
        self._resources = ExitStack()
        self._app_icon = self._resource_file("assets", "app-icon.svg")
        self._play_icon = self._resource_file("assets", "play.svg")
        self._pause_icon = self._resource_file("assets", "pause.svg")
        self._stop_icon = self._resource_file("assets", "stop.svg")
        self._next_icon = self._resource_file("assets", "next.svg")
        self.setWindowTitle("VoidPlayer")
        self.setWindowIcon(QIcon(str(self._app_icon)))
        self.resize(1000, 620)
        self.signals = PlayerSignals()
        self.signals.frame_ready.connect(self.show_frame)
        self.signals.state_changed.connect(self.on_state)
        self.signals.error.connect(self.on_error)
        self.signals.warning.connect(self.on_warning)
        self.signals.anime_next_ready.connect(self._handle_next_anime_source)
        self.signals.show_detail_episodes_ready.connect(self._handle_show_detail_episodes)
        self.signals.show_detail_stream_ready.connect(self._handle_show_detail_stream)
        self.current_show: AnimeSearchResult | None = None
        self.current_show_mode: AnimeMode = "sub"
        self.current_show_episodes: list[AnimeEpisode] = []
        self._show_detail_request_id = ""
        self._show_detail_stream_request_id = ""
        self.player = DecodeLoopPlayer(
            on_frame=self.signals.frame_ready.emit,
            on_state=self.signals.state_changed.emit,
            on_error=self.signals.error.emit,
            on_warning=self.signals.warning.emit,
        )
        self.duration = 0.0
        self._seeking = False
        self._last_pixmap: QPixmap | None = None
        self.current_source: MediaSource | None = None
        self.config_path = user_config_path()
        self.config = load_config(self.config_path)
        stored_theme = self.config.get("theme")
        self.current_theme_name = stored_theme if theme_path is None and theme_name is None and isinstance(stored_theme, str) else theme_name or DEFAULT_THEME
        self.current_theme_path = theme_path
        self.anime_history = anime_history_from_config(self.config)
        self._last_position = 0.0
        self.anime_client: AnimeClient | None = None

        self._build_ui()
        self._apply_theme(self.current_theme_name, self.current_theme_path)
        self._build_actions()
        self.home_button.clicked.connect(self.show_anime_home)
        self.play_button.clicked.connect(self.toggle_playback)
        self.stop_button.clicked.connect(self.player.stop)
        self.next_button.clicked.connect(self.play_next)
        self.seek_slider.sliderPressed.connect(self._begin_seek)
        self.seek_slider.sliderReleased.connect(self._finish_seek)
        self.volume_slider.valueChanged.connect(lambda value: self.player.set_volume(value / 100))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_position)
        self.timer.start(100)

        self.controls_timer = QTimer(self)
        self.controls_timer.setSingleShot(True)
        self.controls_timer.timeout.connect(self._hide_controls_if_fullscreen)
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self._save_current_anime_position)
        self.state_timer.start(5000)
        if initial_media is not None:
            self.statusBar().showMessage("VoidPlayer now starts from anime search; local launch input was ignored.")

    def _resource_file(self, *parts: str) -> Path:
        resource = files(__package__).joinpath(*parts)
        return self._resources.enter_context(as_file(resource))

    def _build_ui(self) -> None:
        self.video_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.video_label.setObjectName("videoSurface")
        self.video_label.setText("")
        self.video_label.setMinimumSize(640, 360)
        self.video_label.mousePressEvent = self._video_click  # type: ignore[method-assign]
        self.video_label.mouseDoubleClickEvent = self._video_double_click  # type: ignore[method-assign]

        self.subtitle_label = QLabel(alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.subtitle_label.setObjectName("subtitleOverlay")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.subtitle_label.hide()

        video_layout = QGridLayout()
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.addWidget(self.video_label, 0, 0)
        self.anime_home = self._build_anime_home()
        video_layout.addWidget(self.anime_home, 0, 0)
        self.show_detail = self._build_show_detail()
        self.show_detail.hide()
        video_layout.addWidget(self.show_detail, 0, 0)
        video_layout.addWidget(self.subtitle_label, 0, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.video_frame = QFrame()
        self.video_frame.setObjectName("videoFrame")
        self.video_frame.setLayout(video_layout)

        self.home_button = self._tool_button("Home", QIcon(str(self._app_icon)))
        self.play_button = self._tool_button("Play", QIcon(str(self._play_icon)))
        self.stop_button = self._tool_button("Stop", QIcon(str(self._stop_icon)))
        self.next_button = self._tool_button("Next Episode", QIcon(str(self._next_icon)))
        self.now_playing_label = QLabel("")
        self.now_playing_label.setObjectName("nowPlayingLabel")
        self.now_playing_label.setMinimumWidth(180)

        self.elapsed_label = QLabel("00:00:00.00")
        self.elapsed_label.setObjectName("timeLabel")
        self.total_label = QLabel("00:00:00.00")
        self.total_label.setObjectName("timeLabel")

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setObjectName("seekSlider")
        self.seek_slider.setMouseTracking(True)
        self.seek_slider.setMinimumHeight(34)

        self.volume_label = QLabel("Volume")
        self.volume_label.setObjectName("volumeLabel")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(130)
        self.volume_slider.setObjectName("volumeSlider")

        timeline_layout = QHBoxLayout()
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(12)
        timeline_layout.addWidget(self.elapsed_label)
        timeline_layout.addWidget(self.seek_slider, 1)
        timeline_layout.addWidget(self.total_label)

        timeline_bar = QFrame()
        timeline_bar.setObjectName("timelineBar")
        timeline_bar.setLayout(timeline_layout)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)
        button_layout.addWidget(self.home_button)
        button_layout.addSpacing(6)
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.next_button)
        button_layout.addSpacing(10)
        button_layout.addWidget(self.volume_label)
        button_layout.addWidget(self.volume_slider)
        button_layout.addWidget(self.now_playing_label, 1)
        button_layout.addStretch(1)

        button_bar = QFrame()
        button_bar.setObjectName("buttonBar")
        button_bar.setLayout(button_layout)

        controls_layout = QVBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(10)
        controls_layout.addWidget(timeline_bar)
        controls_layout.addWidget(button_bar)

        controls = QFrame()
        controls.setObjectName("controlBar")
        controls.setLayout(controls_layout)

        root = QVBoxLayout()
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)
        root.addWidget(self.video_frame, 1)
        root.addWidget(controls)

        player_container = QWidget()
        player_container.setObjectName("appRoot")
        player_container.setLayout(root)

        self.inspector_panel = QPlainTextEdit()
        self.inspector_panel.setObjectName("inspectorPanel")
        self.inspector_panel.setReadOnly(True)
        self.inspector_panel.setMinimumWidth(280)
        self.inspector_panel.hide()

        self.timeline_preview = QLabel()
        self.timeline_preview.setObjectName("timelinePreview")
        self.timeline_preview.hide()

        self.splitter = QSplitter()
        self.splitter.addWidget(player_container)
        self.splitter.addWidget(self.inspector_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setSizes([820, 300])
        self.setCentralWidget(self.splitter)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def _build_anime_home(self) -> QFrame:
        eyebrow = QLabel("ANIME STREAMING")
        eyebrow.setObjectName("animeHomeEyebrow")
        title = QLabel("What are we watching?")
        title.setObjectName("animeHomeTitle")
        subtitle = QLabel("Search for a series, pick sub or dub, and resume the shows already in progress.")
        subtitle.setObjectName("animeHomeSubtitle")

        self.anime_home_search_input = QLineEdit()
        self.anime_home_search_input.setObjectName("animeHomeSearchInput")
        self.anime_home_search_input.setPlaceholderText("Search anime")
        self.anime_home_mode_combo = QComboBox()
        self.anime_home_mode_combo.setObjectName("animeHomeModeCombo")
        self.anime_home_mode_combo.addItem("Sub", "sub")
        self.anime_home_mode_combo.addItem("Dub", "dub")
        self.anime_home_search_button = QPushButton("Search")
        self.anime_home_search_button.setObjectName("animePrimaryButton")
        self.anime_home_search_button.clicked.connect(self.open_anime_home_search)
        self.anime_home_search_input.returnPressed.connect(self.open_anime_home_search)

        self.anime_home_search_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.anime_home_search_row.setContentsMargins(0, 0, 0, 0)
        self.anime_home_search_row.setSpacing(10)
        self.anime_home_search_row.addWidget(self.anime_home_search_input, 1)
        self.anime_home_search_row.addWidget(self.anime_home_mode_combo)
        self.anime_home_search_row.addWidget(self.anime_home_search_button)
        search_panel = QFrame()
        search_panel.setObjectName("animeHomeSearchPanel")
        search_panel.setLayout(self.anime_home_search_row)

        continue_title = QLabel("Continue Watching")
        continue_title.setObjectName("animePanelTitle")
        self.anime_continue_list = QListWidget()
        self.anime_continue_list.setObjectName("animeContinueList")
        self.anime_continue_list.itemDoubleClicked.connect(self.play_anime_history_item)
        self.anime_continue_list.currentItemChanged.connect(lambda _current, _previous: self._update_continue_action_buttons())

        self.continue_resume_button = QPushButton("Resume")
        self.continue_resume_button.setObjectName("animeContinueActionButton")
        self.continue_resume_button.clicked.connect(self.resume_selected_anime_history_item)

        self.continue_remove_button = QPushButton("Remove")
        self.continue_remove_button.setObjectName("animeContinueActionButton")
        self.continue_remove_button.clicked.connect(self.remove_selected_anime_history_item)

        self.continue_next_button = QPushButton("Next Episode")
        self.continue_next_button.setObjectName("animeContinueActionButton")
        self.continue_next_button.clicked.connect(self.play_next_for_selected_anime_history_item)

        self.anime_continue_actions = QHBoxLayout()
        self.anime_continue_actions.setContentsMargins(0, 0, 0, 0)
        self.anime_continue_actions.setSpacing(8)
        self.anime_continue_actions.addWidget(self.continue_resume_button)
        self.anime_continue_actions.addWidget(self.continue_next_button)
        self.anime_continue_actions.addWidget(self.continue_remove_button)

        search_column = QVBoxLayout()
        search_column.setContentsMargins(0, 0, 0, 0)
        search_column.setSpacing(12)
        search_column.addWidget(eyebrow)
        search_column.addWidget(title)
        search_column.addWidget(subtitle)
        search_column.addWidget(search_panel)
        search_column.addStretch(1)

        continue_panel_layout = QVBoxLayout()
        continue_panel_layout.setContentsMargins(18, 16, 18, 18)
        continue_panel_layout.setSpacing(12)
        continue_panel_layout.addWidget(continue_title)
        continue_panel_layout.addWidget(self.anime_continue_list, 1)
        continue_panel_layout.addLayout(self.anime_continue_actions)
        self.anime_continue_panel = QFrame()
        self.anime_continue_panel.setObjectName("animeContinuePanel")
        self.anime_continue_panel.setLayout(continue_panel_layout)
        self._refresh_anime_home()

        self.anime_home_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.anime_home_layout.setContentsMargins(50, 38, 50, 36)
        self.anime_home_layout.setSpacing(26)
        self.anime_home_layout.addLayout(search_column, 3)
        self.anime_home_layout.addWidget(self.anime_continue_panel, 2)

        frame = QFrame()
        frame.setObjectName("animeHome")
        frame.setLayout(self.anime_home_layout)
        return frame

    def _build_show_detail(self) -> QFrame:
        self.show_detail_back_button = QPushButton("Home")
        self.show_detail_back_button.setObjectName("animeContinueActionButton")
        self.show_detail_back_button.clicked.connect(self.show_anime_home)

        self.show_detail_title = QLabel("")
        self.show_detail_title.setObjectName("animeHomeTitle")
        self.show_detail_status = QLabel("Choose a show to browse episodes.")
        self.show_detail_status.setObjectName("animeHomeSubtitle")
        self.show_detail_status.setWordWrap(True)

        self.show_detail_mode_combo = QComboBox()
        self.show_detail_mode_combo.setObjectName("animeHomeModeCombo")
        self.show_detail_mode_combo.addItem("Sub", "sub")
        self.show_detail_mode_combo.addItem("Dub", "dub")
        self.show_detail_mode_combo.currentIndexChanged.connect(lambda _index: self.reload_show_detail_for_mode())

        self.show_detail_refresh_button = QPushButton("Refresh Episodes")
        self.show_detail_refresh_button.setObjectName("animeContinueActionButton")
        self.show_detail_refresh_button.clicked.connect(self.refresh_show_detail_episodes)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)
        header_row.addWidget(self.show_detail_back_button)
        header_row.addWidget(self.show_detail_title, 1)
        header_row.addWidget(self.show_detail_mode_combo)
        header_row.addWidget(self.show_detail_refresh_button)

        self.show_detail_episodes = QListWidget()
        self.show_detail_episodes.setObjectName("animeShowEpisodeList")
        self.show_detail_episodes.currentItemChanged.connect(lambda _current, _previous: self._update_show_detail_buttons())
        self.show_detail_episodes.itemDoubleClicked.connect(lambda _item: self.play_selected_show_detail_episode())

        self.show_detail_play_button = QPushButton("Play")
        self.show_detail_play_button.setObjectName("animePrimaryButton")
        self.show_detail_play_button.clicked.connect(self.play_selected_show_detail_episode)
        self.show_detail_resume_button = QPushButton("Resume")
        self.show_detail_resume_button.setObjectName("animeContinueActionButton")
        self.show_detail_resume_button.clicked.connect(self.resume_selected_show_detail_episode)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        actions.addWidget(self.show_detail_play_button)
        actions.addWidget(self.show_detail_resume_button)
        actions.addStretch(1)

        layout = QVBoxLayout()
        layout.setContentsMargins(50, 38, 50, 36)
        layout.setSpacing(14)
        layout.addLayout(header_row)
        layout.addWidget(self.show_detail_status)
        layout.addWidget(self.show_detail_episodes, 1)
        layout.addLayout(actions)

        self.show_detail_play_button.setEnabled(False)
        self.show_detail_resume_button.setEnabled(False)

        frame = QFrame()
        frame.setObjectName("animeShowDetail")
        frame.setLayout(layout)
        return frame

    def _build_actions(self) -> None:
        self.fullscreen_action = QAction("Fullscreen", self)
        self.fullscreen_action.setShortcut(QKeySequence("F"))
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)

        self.mute_action = QAction("Mute", self)
        self.mute_action.setShortcut(QKeySequence("M"))
        self.mute_action.triggered.connect(self.toggle_mute)

        self.inspector_action = QAction("Inspector", self)
        self.inspector_action.triggered.connect(self.toggle_inspector)
        self.home_action = QAction("Home", self)
        self.home_action.triggered.connect(self.show_anime_home)
        self.search_anime_action = QAction("Search Anime...", self)
        self.search_anime_action.triggered.connect(self.open_anime_browser)
        self.next_episode_action = QAction("Next Episode", self)
        self.next_episode_action.setShortcut(QKeySequence("N"))
        self.next_episode_action.triggered.connect(self.play_next)
        self.disclaimer_action = QAction("Anime Source Disclaimer", self)
        self.disclaimer_action.triggered.connect(self.show_anime_disclaimer)

        self.anime_menu = self.menuBar().addMenu("Anime")
        self.anime_menu.addAction(self.home_action)
        self.anime_menu.addAction(self.search_anime_action)
        self.anime_menu.addAction(self.next_episode_action)

        self.view_menu = self.menuBar().addMenu("View")
        self.view_menu.addAction(self.fullscreen_action)
        self.view_menu.addAction(self.mute_action)
        self.view_menu.addAction(self.inspector_action)
        self.theme_menu = QMenu("Theme", self)
        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)
        for theme_id, label in PACKAGED_THEMES.items():
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(theme_id)
            action.setChecked(theme_id == self.current_theme_name)
            action.triggered.connect(lambda _checked=False, selected=theme_id: self.select_theme(selected))
            self.theme_action_group.addAction(action)
            self.theme_menu.addAction(action)
        self.view_menu.addMenu(self.theme_menu)

        self.help_menu = self.menuBar().addMenu("Help")
        self.help_menu.addAction(self.disclaimer_action)

        for action in (
            self.fullscreen_action,
            self.mute_action,
            self.inspector_action,
            self.home_action,
            self.search_anime_action,
            self.next_episode_action,
            self.disclaimer_action,
        ):
            self.addAction(action)
        self._add_shortcut("Space", self.toggle_playback)
        self._add_shortcut("Left", lambda: self.seek_relative(-5))
        self._add_shortcut("Right", lambda: self.seek_relative(5))
        self._add_shortcut("Shift+Left", lambda: self.seek_relative(-30))
        self._add_shortcut("Shift+Right", lambda: self.seek_relative(30))
        self._add_shortcut("Up", lambda: self.adjust_volume(5))
        self._add_shortcut("Down", lambda: self.adjust_volume(-5))
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
        button.setIconSize(QSize(22, 22))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _apply_theme(self, theme_name: str = DEFAULT_THEME, theme_path: Path | None = None) -> None:
        try:
            theme = load_theme(theme_name, theme_path)
        except ThemeError as exc:
            theme = load_theme(DEFAULT_THEME)
            self.current_theme_name = DEFAULT_THEME
            self.current_theme_path = None
            self.statusBar().showMessage(f"{exc}; loaded default theme")
        self.setStyleSheet(render_stylesheet(theme))

    def select_theme(self, theme_name: str) -> None:
        self.current_theme_name = theme_name
        self.current_theme_path = None
        self._apply_theme(theme_name)
        self.config = {**self.config, "theme": self.current_theme_name}
        save_config(self.config_path, self.config)
        self.statusBar().showMessage(f"Loaded {PACKAGED_THEMES.get(theme_name, theme_name)} theme")

    def play_source(self, source: Path | str | MediaSource) -> None:
        self.current_source = ensure_media_source(source)
        self.load_and_play(self.current_source)

    def play_next(self) -> None:
        if self.current_source is None:
            return
        self._save_current_anime_position()
        self._play_next_anime_episode()

    def load_and_play(self, source: Path | str | MediaSource) -> None:
        media_source = ensure_media_source(source)
        if media_source.local_path is not None:
            self.statusBar().showMessage("Local files are no longer part of the VoidPlayer app flow.")
            return
        try:
            self._last_position = 0.0
            self.current_source = media_source
            self.anime_home.hide()
            self.statusBar().showMessage(f"Opening stream: {media_source.display_name}")
            media = self.player.load(media_source)
            self.duration = media.duration or 0.0
            resumed = False
            initial_position = self._anime_metadata_resume_position(media_source) or 0.0
            resume_at = self._anime_resume_position(media_source, media)
            if resume_at is not None:
                self.player.seek(resume_at)
                resumed = True
                self.statusBar().showMessage(f"Resumed at {format_timestamp(resume_at)}")
            self._remember_anime_source(media_source, position=resume_at if resume_at is not None else initial_position)
            if media_source.subtitle_url:
                self.player.set_subtitle_source(media_source.subtitle_url)
            self._refresh_inspector(media)
            self._update_now_playing(media_source)
            if not resumed:
                self.statusBar().showMessage(media_source.display_name)
            self.player.play()
        except Exception as exc:
            self.on_error(exc)

    def open_anime_browser(self) -> None:
        if not self._confirm_anime_disclaimer():
            return
        dialog = AnimeBrowserDialog(self, client=self._anime_client())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._handle_anime_browser_result(dialog)

    def open_anime_home_search(self) -> None:
        query = self.anime_home_search_input.text().strip()
        if not query or not self._confirm_anime_disclaimer():
            return
        dialog = AnimeBrowserDialog(self, client=self._anime_client())
        dialog.search_input.setText(query)
        mode_index = dialog.mode_combo.findData(self.anime_home_mode_combo.currentData())
        if mode_index >= 0:
            dialog.mode_combo.setCurrentIndex(mode_index)
        dialog.search()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._handle_anime_browser_result(dialog)

    def _handle_anime_browser_result(self, dialog: AnimeBrowserDialog) -> None:
        if dialog.selected_show is not None:
            self.show_anime_detail(dialog.selected_show, mode=dialog.mode)
        elif dialog.selected_stream is not None:
            self.play_source(dialog.selected_stream.to_media_source())

    def play_anime_history_item(self, item: QListWidgetItem) -> None:
        history_item = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(history_item, AnimeHistoryItem):
            return
        if not self._confirm_anime_disclaimer():
            return
        if should_continue_with_next_episode(history_item):
            self.play_next_for_anime_history_item(history_item)
            return
        episode = AnimeEpisode(
            show_id=history_item.show_id,
            title=history_item.title,
            number=history_item.episode,
            mode=history_item.mode if history_item.mode in {"sub", "dub"} else "sub",
        )
        self.statusBar().showMessage(f"Resolving {history_item.display_name}...")

        def worker() -> None:
            try:
                stream = self._anime_client().fast_stream_for_episode(episode)
                if stream is None:
                    raise RuntimeError(f"No playable stream found for {history_item.display_name}.")
                source = stream.to_media_source()
                metadata = dict(source.metadata or {})
                metadata["resume_position"] = f"{history_item.position:.6f}"
                source = MediaSource(
                    location=source.location,
                    title=source.title,
                    headers=source.headers,
                    subtitle_url=source.subtitle_url or history_item.subtitle_url,
                    metadata=metadata,
                )
                self.signals.anime_next_ready.emit(source, None)
            except Exception as exc:  # pragma: no cover - UI/manual path
                self.signals.anime_next_ready.emit(None, exc)

        threading.Thread(target=worker, daemon=True).start()

    def _selected_anime_history_item(self) -> AnimeHistoryItem | None:
        item = self.anime_continue_list.currentItem() if hasattr(self, "anime_continue_list") else None
        if item is None:
            return None
        history_item = item.data(Qt.ItemDataRole.UserRole)
        return history_item if isinstance(history_item, AnimeHistoryItem) else None

    def _update_continue_action_buttons(self) -> None:
        enabled = self._selected_anime_history_item() is not None
        for button_name in ("continue_resume_button", "continue_remove_button", "continue_next_button"):
            if hasattr(self, button_name):
                getattr(self, button_name).setEnabled(enabled)

    def resume_selected_anime_history_item(self) -> None:
        item = self.anime_continue_list.currentItem() if hasattr(self, "anime_continue_list") else None
        if item is not None:
            self.play_anime_history_item(item)

    def remove_selected_anime_history_item(self) -> None:
        history_item = self._selected_anime_history_item()
        if history_item is None:
            return
        self.config = remove_anime_history_item(
            self.config,
            show_id=history_item.show_id,
            episode=history_item.episode,
            mode=history_item.mode,
        )
        save_config(self.config_path, self.config)
        self.anime_history = anime_history_from_config(self.config)
        self._refresh_anime_home()

    def play_next_for_selected_anime_history_item(self) -> None:
        history_item = self._selected_anime_history_item()
        if history_item is None:
            return
        self.play_next_for_anime_history_item(history_item)

    def play_next_for_anime_history_item(self, history_item: AnimeHistoryItem) -> None:
        if not self._confirm_anime_disclaimer():
            return
        episode = AnimeEpisode(
            show_id=history_item.show_id,
            title=history_item.title,
            number=history_item.episode,
            mode=history_item.mode if history_item.mode in {"sub", "dub"} else "sub",
        )
        self.statusBar().showMessage(f"Resolving next episode after {history_item.display_name}...")

        def worker() -> None:
            try:
                next_episode = self._anime_client().next_episode(episode)
                if next_episode is None:
                    raise RuntimeError("No next episode found.")
                stream = self._anime_client().fast_stream_for_episode(next_episode)
                if stream is None:
                    raise RuntimeError(f"No playable stream found for episode {next_episode.number}.")
                self.signals.anime_next_ready.emit(stream.to_media_source(), None)
            except Exception as exc:  # pragma: no cover - UI/manual path
                self.signals.anime_next_ready.emit(None, exc)

        threading.Thread(target=worker, daemon=True).start()

    def reload_show_detail_for_mode(self) -> None:
        if self.current_show is None:
            return
        mode = self.show_detail_mode_combo.currentData() or "sub"
        if mode not in {"sub", "dub"}:
            mode = "sub"
        if mode == self.current_show_mode:
            return
        self.show_anime_detail(self.current_show, mode=mode)

    def refresh_show_detail_episodes(self) -> None:
        if self.current_show is not None:
            self.show_anime_detail(self.current_show, mode=self.current_show_mode)

    def _cancel_show_detail_stream_request(self) -> None:
        self._show_detail_stream_request_id = ""

    def show_anime_detail(self, show: AnimeSearchResult, *, mode: AnimeMode = "sub") -> None:
        self._cancel_show_detail_stream_request()
        self.current_show = show
        self.current_show_mode = mode if mode in {"sub", "dub"} else "sub"
        mode_index = self.show_detail_mode_combo.findData(self.current_show_mode)
        if mode_index >= 0 and self.show_detail_mode_combo.currentIndex() != mode_index:
            previous = self.show_detail_mode_combo.blockSignals(True)
            self.show_detail_mode_combo.setCurrentIndex(mode_index)
            self.show_detail_mode_combo.blockSignals(previous)
        self.show_detail_title.setText(show.title)
        self.show_detail_status.setText("Loading episodes")
        self.show_detail_refresh_button.setEnabled(False)
        self.show_detail_episodes.clear()
        self.current_show_episodes = []
        self._update_show_detail_buttons()
        self.anime_home.hide()
        self.show_detail.show()
        self._load_show_detail_episodes()

    def _load_show_detail_episodes(self) -> None:
        if self.current_show is None:
            return
        self._request_counter = getattr(self, "_request_counter", 0) + 1
        request_id = f"episodes:{self._request_counter}"
        self._show_detail_request_id = request_id
        show = self.current_show
        mode = self.current_show_mode

        def worker() -> None:
            try:
                episodes = self._anime_client().episodes(show, mode=mode)
                self.signals.show_detail_episodes_ready.emit(request_id, episodes, None)
            except Exception as exc:  # pragma: no cover - UI/manual path
                self.signals.show_detail_episodes_ready.emit(request_id, None, exc)

        threading.Thread(target=worker, daemon=True).start()

    def _update_show_detail_buttons(self) -> None:
        episode = self._selected_show_detail_episode()
        enabled = episode is not None
        self.show_detail_play_button.setEnabled(enabled)
        history_item = self._selected_show_detail_history()
        self.show_detail_resume_button.setEnabled(history_item is not None and history_item.position > 0)

    def _selected_show_detail_episode(self) -> AnimeEpisode | None:
        item = self.show_detail_episodes.currentItem() if hasattr(self, "show_detail_episodes") else None
        episode = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return episode if isinstance(episode, AnimeEpisode) else None

    def _selected_show_detail_history(self) -> AnimeHistoryItem | None:
        episode = self._selected_show_detail_episode()
        if episode is None:
            return None
        return selected_episode_history(episode, episode_history_map(self.anime_history))

    def _handle_show_detail_episodes(self, request_id: str, result: object, error: object) -> None:
        if request_id != self._show_detail_request_id:
            return
        self.show_detail_refresh_button.setEnabled(True)
        if isinstance(error, Exception):
            self.current_show_episodes = []
            self.show_detail_episodes.clear()
            self.show_detail_status.setText(str(error))
            self._update_show_detail_buttons()
            return
        episodes = result if isinstance(result, list) else []
        self.current_show_episodes = [episode for episode in episodes if isinstance(episode, AnimeEpisode)]
        self._render_show_detail_episodes()

    def _render_show_detail_episodes(self) -> None:
        self.anime_history = anime_history_from_config(self.config)
        history = episode_history_map(self.anime_history)
        self.show_detail_episodes.clear()
        if not self.current_show_episodes:
            self.show_detail_status.setText("No episodes found for this mode.")
            self._update_show_detail_buttons()
            return
        for episode in self.current_show_episodes:
            history_item = selected_episode_history(episode, history)
            item = QListWidgetItem(episode_row_text(episode, history_item))
            item.setData(Qt.ItemDataRole.UserRole, episode)
            self.show_detail_episodes.addItem(item)
        count = len(self.current_show_episodes)
        self.show_detail_status.setText(f"{count} episode{'s' if count != 1 else ''} loaded.")
        self.show_detail_episodes.setCurrentRow(-1)
        self._update_show_detail_buttons()

    def _handle_show_detail_stream(self, request_id: str, result: object, error: object) -> None:
        if request_id != self._show_detail_stream_request_id:
            return
        if isinstance(error, Exception):
            self.show_detail_status.setText(str(error))
            self._update_show_detail_buttons()
            return
        if isinstance(result, MediaSource):
            self._cancel_show_detail_stream_request()
            self._update_show_detail_buttons()
            self.play_source(result)
            self.show_detail.hide()
            return
        self.show_detail_status.setText("No playable stream returned.")
        self._update_show_detail_buttons()

    def play_selected_show_detail_episode(self) -> None:
        self._resolve_selected_show_detail_episode(resume=False)

    def resume_selected_show_detail_episode(self) -> None:
        self._resolve_selected_show_detail_episode(resume=True)

    def _resolve_selected_show_detail_episode(self, *, resume: bool) -> None:
        episode = self._selected_show_detail_episode()
        if episode is None:
            return
        history_item = self._selected_show_detail_history() if resume else None
        self._request_counter = getattr(self, "_request_counter", 0) + 1
        request_id = f"stream:{self._request_counter}"
        self._show_detail_stream_request_id = request_id
        self.show_detail_play_button.setEnabled(False)
        self.show_detail_resume_button.setEnabled(False)
        self.show_detail_status.setText(f"Resolving Episode {episode.number}")

        def worker() -> None:
            try:
                stream = self._anime_client().fast_stream_for_episode(episode)
                if stream is None:
                    raise RuntimeError(f"No playable fast stream found for Episode {episode.number}.")
                source = episode_source_with_resume(stream.to_media_source(), history_item)
                self.signals.show_detail_stream_ready.emit(request_id, source, None)
            except Exception as exc:  # pragma: no cover - UI/manual path
                self.signals.show_detail_stream_ready.emit(request_id, None, exc)

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_anime_home(self) -> None:
        if not hasattr(self, "anime_continue_list"):
            return
        self.anime_continue_list.clear()
        if not self.anime_history:
            item = QListWidgetItem("No anime history yet")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.anime_continue_list.addItem(item)
            self._update_continue_action_buttons()
            return
        grouped_history: dict[str, list[AnimeHistoryItem]] = {}
        group_titles: dict[str, str] = {}
        for history_item in sorted_anime_history(self.anime_history)[:20]:
            grouped_history.setdefault(history_item.show_id, []).append(history_item)
            group_titles.setdefault(history_item.show_id, history_item.title)
        for show_id, history_items in grouped_history.items():
            header = QListWidgetItem(group_titles[show_id])
            header.setData(Qt.ItemDataRole.UserRole, None)
            header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsEnabled)
            self.anime_continue_list.addItem(header)
            for history_item in history_items:
                progress = anime_history_progress(history_item)
                progress_text = f"    {progress}" if progress else ""
                resume_text = format_timestamp(history_item.position) if history_item.position > 0 else "start"
                item = QListWidgetItem(f"Episode {history_item.episode}    Resume {resume_text}{progress_text}")
                item.setToolTip(history_item.stream_url)
                item.setData(Qt.ItemDataRole.UserRole, history_item)
                self.anime_continue_list.addItem(item)
        self.anime_continue_list.setCurrentRow(-1)
        self._update_continue_action_buttons()

    def _remember_anime_source(self, source: MediaSource, *, position: float = 0.0) -> None:
        metadata = source.metadata or {}
        if metadata.get("kind") != "anime":
            return
        title = metadata.get("title")
        show_id = metadata.get("show_id")
        episode = metadata.get("episode")
        mode = metadata.get("mode", "sub")
        if not all(isinstance(value, str) and value for value in (title, show_id, episode, mode)):
            return
        self.config = set_anime_history_item(
            self.config,
            AnimeHistoryItem(
                title=title,
                show_id=show_id,
                episode=episode,
                mode=mode,
                stream_url=source.location,
                display_name=source.display_name,
                position=position,
                duration=self.duration if self.duration > 0 else None,
                subtitle_url=source.subtitle_url,
            ),
        )
        self.anime_history = anime_history_from_config(self.config)
        save_config(self.config_path, self.config)
        self._refresh_anime_home()

    def _anime_resume_position(self, source: MediaSource, media: MediaInfo) -> float | None:
        return resumable_position(self._anime_metadata_resume_position(source), media.duration)

    def _anime_metadata_resume_position(self, source: MediaSource) -> float | None:
        metadata = source.metadata or {}
        if metadata.get("kind") != "anime":
            return None
        try:
            position = float(metadata.get("resume_position", 0.0))
        except (TypeError, ValueError):
            return None
        return max(0.0, position)

    def _confirm_anime_disclaimer(self) -> bool:
        if self.config.get("anime_disclaimer_accepted") is True:
            return True
        message = QMessageBox(self)
        message.setWindowTitle("Enable Anime Search")
        message.setIcon(QMessageBox.Icon.Warning)
        message.setText("Anime search uses third-party public sources and is inspired by ani-cli.")
        message.setInformativeText(
            "VoidPlayer does not host or control the content. Use this feature at your own risk and follow the laws and terms that apply to you."
        )
        message.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok)
        message.button(QMessageBox.StandardButton.Ok).setText("Enable")
        if message.exec() != QMessageBox.StandardButton.Ok:
            return False
        self.config = dict(self.config)
        self.config["anime_disclaimer_accepted"] = True
        save_config(self.config_path, self.config)
        return True

    def show_anime_disclaimer(self) -> None:
        message = QMessageBox(self)
        message.setWindowTitle("Anime Source Disclaimer")
        message.setIcon(QMessageBox.Icon.Information)
        message.setText("Anime search uses third-party public sources and is inspired by ani-cli.")
        message.setInformativeText(
            "VoidPlayer does not host or control the content. Use this feature at your own risk and follow the laws and terms that apply to you."
        )
        message.setStandardButtons(QMessageBox.StandardButton.Ok)
        message.exec()

    def _anime_client(self) -> AnimeClient:
        if self.anime_client is None:
            self.anime_client = AnimeClient(cache_path=self.config_path.with_name("anime-cache.json"))
        return self.anime_client

    def _play_next_anime_episode(self) -> bool:
        if self.current_source is None:
            return False
        current = self.current_source
        metadata = current.metadata or {}
        if metadata.get("kind") != "anime":
            return False
        show_id = metadata.get("show_id")
        title = metadata.get("title")
        episode_number = metadata.get("episode")
        mode = metadata.get("mode", "sub")
        if not show_id or not title or not episode_number or mode not in ("sub", "dub"):
            return False
        episode = AnimeEpisode(show_id=show_id, title=title, number=episode_number, mode=mode)
        self.statusBar().showMessage("Resolving next anime episode...")

        def worker() -> None:
            try:
                next_episode = self._anime_client().next_episode(episode)
                if next_episode is None:
                    raise RuntimeError("No next episode found.")
                stream = self._anime_client().fast_stream_for_episode(next_episode)
                if stream is None:
                    raise RuntimeError(f"No playable stream found for episode {next_episode.number}.")
                self.signals.anime_next_ready.emit(stream.to_media_source(), None)
            except Exception as exc:  # pragma: no cover - UI/manual path
                self.signals.anime_next_ready.emit(None, exc)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _handle_next_anime_source(self, source: object, error: object) -> None:
        if isinstance(error, Exception):
            self.statusBar().showMessage(str(error))
            return
        if not isinstance(source, MediaSource):
            return
        self.play_source(source)

    def toggle_playback(self) -> None:
        if self.player.state == PlaybackState.PLAYING:
            self.player.pause()
        else:
            self.player.play()

    def _update_now_playing(self, source: MediaSource | None = None) -> None:
        if source is None:
            self.now_playing_label.setText("")
            self.now_playing_label.setToolTip("")
            return
        metadata = source.metadata or {}
        if metadata.get("kind") == "anime":
            title = metadata.get("title") or source.display_name
            episode = metadata.get("episode")
            mode = metadata.get("mode")
            suffix = f"Episode {episode}" if episode else "Anime"
            if mode in {"sub", "dub"}:
                suffix = f"{suffix} ({mode.upper()})"
            text = f"Now playing: {title} - {suffix}"
        else:
            text = f"Now playing: {source.display_name}"
        self.now_playing_label.setText(text)
        self.now_playing_label.setToolTip(text)

    def show_frame(self, frame: VideoFrame) -> None:
        image = ImageQt(frame.image)
        qimage = QImage(image)
        self._last_pixmap = QPixmap.fromImage(qimage)
        self._render_pixmap()

    def on_state(self, state: PlaybackState) -> None:
        if state == PlaybackState.PLAYING:
            self.play_button.setIcon(QIcon(str(self._pause_icon)))
            self.play_button.setToolTip("Pause")
        elif state == PlaybackState.ENDED:
            self.play_button.setIcon(QIcon(str(self._play_icon)))
            self.play_button.setToolTip("Play")
            self.play_next()
        else:
            self.play_button.setIcon(QIcon(str(self._play_icon)))
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

    def _begin_seek(self) -> None:
        self._seeking = True

    def _finish_seek(self) -> None:
        if self.duration > 0:
            self.player.seek(self.seek_slider.value() / 1000 * self.duration)
        self._seeking = False

    def show_anime_home(self) -> None:
        self._cancel_show_detail_stream_request()
        self._save_current_anime_position()
        self.player.stop()
        self.current_source = None
        self._last_pixmap = None
        self.video_label.clear()
        self.subtitle_label.hide()
        self.duration = 0.0
        self.seek_slider.setValue(0)
        self.elapsed_label.setText(format_timestamp(0))
        self.total_label.setText(format_timestamp(0))
        self.anime_history = anime_history_from_config(self.config)
        self._refresh_anime_home()
        self._update_now_playing()
        if hasattr(self, "show_detail"):
            self.show_detail.hide()
        self.anime_home.show()
        self.statusBar().showMessage("Home")

    def _save_current_anime_position(self) -> None:
        source = self.current_source
        if source is None:
            return
        metadata = source.metadata or {}
        if metadata.get("kind") != "anime":
            return
        position = max(self.player.master_position(), self._last_position)
        self._remember_anime_source(source, position=position)

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

    def _video_click(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.player.media is not None:
            self.toggle_playback()

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

    def toggle_inspector(self) -> None:
        self.inspector_panel.setVisible(not self.inspector_panel.isVisible())

    def copy_probe_json(self) -> None:
        source = self.player.current_source or self.current_source
        if source is not None:
            QApplication.clipboard().setText(json.dumps({"source": source.location, "metadata": source.metadata or {}}, indent=2))
            self.statusBar().showMessage("Copied stream metadata")

    def _refresh_inspector(self, media: MediaInfo) -> None:
        lines = [
            f"Stream: {media.path}",
            f"Duration: {format_timestamp(media.duration)}",
        ]
        if media.primary_video is not None:
            video = media.primary_video
            lines.append(f"Video: {video.codec_name or 'unknown'} {video.width or '?'}x{video.height or '?'} {video.frame_rate or '?'}fps")
        for stream in media.audio_streams:
            lines.append(f"Audio #{stream.index}: {stream.codec_name or 'unknown'} {stream.language or ''} {stream.channels or '?'}ch")
        for stream in media.subtitle_streams:
            lines.append(f"Subtitle #{stream.index}: {stream.codec_name or 'unknown'} {stream.language or ''}")
        self.inspector_panel.setPlainText("\n".join(lines))

    def closeEvent(self, event) -> None:  # noqa: ANN001
        self._save_current_anime_position()
        save_config(self.config_path, self.config)
        self.player.close()
        self._resources.close()
        event.accept()

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._update_anime_home_layout()
        self._render_pixmap()

    def _update_anime_home_layout(self) -> None:
        if not hasattr(self, "anime_home_layout"):
            return
        width = self.width()
        compact = width < 780
        narrow = width < 620
        self.anime_home_layout.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        self.anime_home_layout.setContentsMargins(28 if compact else 50, 24 if compact else 38, 28 if compact else 50, 24 if compact else 36)
        self.anime_home_layout.setSpacing(16 if compact else 26)
        self.anime_home_layout.setStretch(0, 0 if compact else 3)
        self.anime_home_layout.setStretch(1, 1 if compact else 2)
        self.anime_home_search_row.setDirection(QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight)
        self.anime_continue_panel.setMinimumHeight(220 if compact else 0)

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


class AnimeBrowserDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, *, client: AnimeClient | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Search Anime")
        self.setObjectName("animeBrowserDialog")
        self.setMinimumSize(820, 600)
        self.client: AnimeClient | None = client
        self.selected_stream: AnimeStream | None = None
        self.selected_show: AnimeSearchResult | None = None
        self._current_streams: list[AnimeStream] = []
        self._request_counter = 0
        self._active_search_request = ""
        self._active_episodes_request = ""
        self._active_streams_request = ""
        self._worker_signals = AnimeWorkerSignals()
        self._worker_signals.finished.connect(self._handle_worker_result)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("animeSearchInput")
        self.search_input.setPlaceholderText("Search anime")
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("animeModeCombo")
        self.mode_combo.addItem("Sub", "sub")
        self.mode_combo.addItem("Dub", "dub")
        self.search_button = QPushButton("Search")
        self.search_button.setObjectName("animePrimaryButton")
        self.open_show_button = QPushButton("Open Show")
        self.open_show_button.setObjectName("animeContinueActionButton")
        self.open_show_button.setEnabled(False)
        self.results_list = QListWidget()
        self.results_list.setObjectName("animeResultsList")
        self.episodes_list = QListWidget()
        self.episodes_list.setObjectName("animeEpisodesList")
        self.quality_combo = QComboBox()
        self.quality_combo.setObjectName("animeQualityCombo")
        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("animePlayButton")
        self.play_button.setEnabled(False)
        self.status_label = QLabel("Powered by public third-party sources. Inspired by ani-cli.")
        self.status_label.setObjectName("animeStatus")
        self.status_label.setWordWrap(True)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(10)
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.mode_combo)
        search_row.addWidget(self.search_button)

        search_frame = QFrame()
        search_frame.setObjectName("animeSearchBar")
        search_frame.setLayout(search_row)

        lists_splitter = QSplitter(Qt.Orientation.Horizontal)
        lists_splitter.setObjectName("animeListsSplitter")
        results_column = QVBoxLayout()
        results_column.setContentsMargins(12, 12, 12, 12)
        results_title = QLabel("Results")
        results_title.setObjectName("animePanelTitle")
        results_column.addWidget(results_title)
        results_column.addWidget(self.results_list, 1)
        results_panel = QFrame()
        results_panel.setObjectName("animePanel")
        results_panel.setLayout(results_column)
        episodes_column = QVBoxLayout()
        episodes_column.setContentsMargins(12, 12, 12, 12)
        episodes_title = QLabel("Episodes")
        episodes_title.setObjectName("animePanelTitle")
        episodes_column.addWidget(episodes_title)
        episodes_column.addWidget(self.episodes_list, 1)
        episodes_panel = QFrame()
        episodes_panel.setObjectName("animePanel")
        episodes_panel.setLayout(episodes_column)
        lists_splitter.addWidget(results_panel)
        lists_splitter.addWidget(episodes_panel)
        lists_splitter.setSizes([420, 360])

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(10)
        bottom_row.addWidget(QLabel("Quality"))
        bottom_row.addWidget(self.quality_combo, 1)
        bottom_row.addWidget(self.open_show_button)
        bottom_row.addWidget(self.play_button)

        bottom_frame = QFrame()
        bottom_frame.setObjectName("animeBottomBar")
        bottom_frame.setLayout(bottom_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        layout.addWidget(search_frame)
        layout.addWidget(lists_splitter, 1)
        layout.addWidget(bottom_frame)
        layout.addWidget(self.status_label)
        layout.addWidget(buttons)
        self.setLayout(layout)

        self.search_button.clicked.connect(self.search)
        self.search_input.returnPressed.connect(self.search)
        self.results_list.itemSelectionChanged.connect(self.load_episodes)
        self.results_list.itemSelectionChanged.connect(self._update_open_show_button)
        self.episodes_list.itemSelectionChanged.connect(self.load_streams)
        self.quality_combo.currentIndexChanged.connect(lambda _index: self.play_button.setEnabled(self.quality_combo.currentData() is not None))
        self.open_show_button.clicked.connect(self.accept_selected_show)
        self.play_button.clicked.connect(self.accept_selected_stream)

    @property
    def mode(self) -> AnimeMode:
        return self.mode_combo.currentData() or "sub"

    def search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            return
        request_id = self._next_request_id("search")
        self._active_search_request = request_id
        self._active_episodes_request = ""
        self._active_streams_request = ""
        self.results_list.clear()
        self.episodes_list.clear()
        self.quality_combo.clear()
        self._current_streams = []
        self.selected_show = None
        self.selected_stream = None
        self.play_button.setEnabled(False)
        self._update_open_show_button()
        self.search_button.setEnabled(False)
        self._set_status("Searching...")
        self._run_worker(request_id, lambda: self._client().search(query, mode=self.mode))

    def _apply_search_results(self, results: list[AnimeSearchResult]) -> None:
        self.results_list.clear()
        self.episodes_list.clear()
        self.quality_combo.clear()
        self.play_button.setEnabled(False)
        if not results:
            self._update_open_show_button()
            self._set_status("No results found.")
            return
        for result in results:
            suffix = f" ({result.episode_count} episodes)" if result.episode_count else ""
            item = QListWidgetItem(f"{result.title}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, result)
            self.results_list.addItem(item)
        self._set_status(f"{len(results)} result{'s' if len(results) != 1 else ''}")
        self._update_open_show_button()

    def load_episodes(self) -> None:
        item = self.results_list.currentItem()
        result = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(result, AnimeSearchResult):
            return
        request_id = self._next_request_id("episodes")
        self._active_episodes_request = request_id
        self.episodes_list.clear()
        self.quality_combo.clear()
        self.play_button.setEnabled(False)
        self._update_open_show_button()
        self._set_status("Loading episodes...")
        self._run_worker(request_id, lambda: self._client().episodes(result, mode=self.mode))

    def _apply_episode_results(self, episodes: list[AnimeEpisode]) -> None:
        self.episodes_list.clear()
        self.quality_combo.clear()
        self.play_button.setEnabled(False)
        if not episodes:
            self._set_status("No episodes found for this title.")
            return
        for episode in episodes:
            item = QListWidgetItem(f"Episode {episode.number}")
            item.setData(Qt.ItemDataRole.UserRole, episode)
            self.episodes_list.addItem(item)
        self._set_status(f"{len(episodes)} episode{'s' if len(episodes) != 1 else ''}")

    def load_streams(self) -> None:
        item = self.episodes_list.currentItem()
        episode = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(episode, AnimeEpisode):
            return
        request_id = self._next_request_id("streams")
        self._active_streams_request = request_id
        self._current_streams = []
        self.quality_combo.clear()
        self.play_button.setEnabled(False)
        self._set_status("Resolving fast stream...")
        self._run_worker(request_id, lambda: self._client().fast_streams(episode))

    def _apply_stream_results(self, streams: list[AnimeStream]) -> None:
        self._current_streams = list(streams)
        self.quality_combo.clear()
        for stream in self._current_streams:
            self.quality_combo.addItem(stream.quality, stream)
        self.play_button.setEnabled(bool(self._current_streams))
        if not self._current_streams:
            self._set_status("No playable streams found for this episode.")
            return
        self._set_status(f"Fast stream ready ({len(self._current_streams)} option{'s' if len(self._current_streams) != 1 else ''})")

    def accept_selected_stream(self) -> None:
        stream = self.quality_combo.currentData()
        if isinstance(stream, AnimeStream):
            self.selected_stream = stream
        else:
            self.selected_stream = select_quality(self._current_streams)
        if self.selected_stream is not None:
            self.selected_show = None
            self.accept()

    def _selected_search_result(self) -> AnimeSearchResult | None:
        item = self.results_list.currentItem()
        result = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return result if isinstance(result, AnimeSearchResult) else None

    def _update_open_show_button(self) -> None:
        self.open_show_button.setEnabled(self._selected_search_result() is not None)

    def accept_selected_show(self) -> None:
        result = self._selected_search_result()
        if result is None:
            return
        self.selected_show = result
        self.selected_stream = None
        self.accept()

    def _client(self) -> AnimeClient:
        if self.client is None:
            try:
                self.client = AnimeClient()
            except AnimeClientError:
                raise
        return self.client

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _next_request_id(self, prefix: str) -> str:
        self._request_counter += 1
        return f"{prefix}:{self._request_counter}"

    def _run_worker(self, request_id: str, work) -> None:  # noqa: ANN001
        def runner() -> None:
            try:
                result = work()
                error = None
            except Exception as exc:  # pragma: no cover - exercised through UI/manual paths
                result = None
                error = exc
            self._worker_signals.finished.emit(request_id, result, error)

        threading.Thread(target=runner, daemon=True).start()

    def _handle_worker_result(self, request_id: str, result: object, error: object) -> None:
        kind = request_id.split(":", 1)[0]
        if kind == "search":
            self.search_button.setEnabled(True)
            if request_id != self._active_search_request:
                return
            if isinstance(error, Exception):
                self._set_status(str(error))
                return
            self._apply_search_results(result if isinstance(result, list) else [])
        elif kind == "episodes":
            if request_id != self._active_episodes_request:
                return
            if isinstance(error, Exception):
                self._set_status(str(error))
                return
            self._apply_episode_results(result if isinstance(result, list) else [])
        elif kind == "streams":
            if request_id != self._active_streams_request:
                return
            if isinstance(error, Exception):
                self._set_status(str(error))
                return
            self._apply_stream_results(result if isinstance(result, list) else [])


def main() -> int:
    parser = argparse.ArgumentParser(prog="voidplayer")
    parser.add_argument("--debug", action="store_true", help="Enable playback debug logging")
    parser.add_argument("--theme", help="Theme name from bundled themes")
    parser.add_argument("--theme-path", type=Path, help="Path to a custom theme directory")
    args, qt_args = parser.parse_known_args()

    if args.debug:
        configure_debug_logging(True)
    app = QApplication([sys.argv[0], *qt_args])
    app.setWindowIcon(QIcon(str(resource_path("assets", "app-icon.svg"))))
    window = PlayerWindow(theme_name=args.theme, theme_path=args.theme_path)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

# Show Detail Episode Browser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a first-class show detail and episode browser workflow so search results lead to a show page with episode state, sub/dub mode switching, and Play/Resume actions.

**Architecture:** Add pure show-detail helper functions first, then wire a PySide show-detail surface into `PlayerWindow`, then adapt the existing anime search dialog so it can open a show instead of only returning a stream. Keep provider lookup and cache behavior inside `AnimeClient`; keep watch state in the existing config-backed anime history.

**Tech Stack:** Python 3.13, PySide6 widgets, existing `AnimeClient`/`AnimeSearchResult`/`AnimeEpisode`/`AnimeStream`, existing `AnimeHistoryItem`, pytest offscreen GUI tests, Rust core left unchanged.

---

## File Structure

- Create: `src/ffmpeg_pywrapper/player/show_detail.py`
  - Pure helper module for matching history, building episode labels, and attaching resume metadata.
- Modify: `src/ffmpeg_pywrapper/player/app.py`
  - Add show-detail widgets and transitions.
  - Add worker signals for episode loading and stream loading.
  - Add Play/Resume/Refresh behavior.
  - Add search-dialog support for opening a show detail page.
- Modify: `tests/test_player_config.py`
  - Add pure helper coverage.
- Modify: `tests/test_player_smoke.py`
  - Add offscreen GUI coverage for show detail construction, search handoff, mode switching, playback, resume, and error states.
- Modify: `README.md`
  - Update user flow to mention show detail and episode browsing.
- Modify: `docs/superpowers/specs/2026-05-11-project-state-and-next-steps.md`
  - Mark provider cache/resilience and rich Continue Watching as completed/current, then set Show Detail And Episode Browser as the active next step.
- Generated if available: `graphify-out/`
  - Rebuilt by `python -m graphify update . --force`; do not hand-edit generated files.

## Task 1: Add Pure Show Detail Helpers

**Files:**
- Create: `src/ffmpeg_pywrapper/player/show_detail.py`
- Test: `tests/test_player_config.py`

- [ ] **Step 1: Write failing helper tests**

Append these tests to `tests/test_player_config.py`:

```python
from ffmpeg_pywrapper.anime import AnimeEpisode
from ffmpeg_pywrapper.media import MediaSource
from ffmpeg_pywrapper.player.show_detail import (
    anime_history_key,
    episode_history_map,
    episode_row_text,
    episode_source_with_resume,
    selected_episode_history,
)
```

Add the tests near the existing anime history tests:

```python
def test_show_detail_matches_history_by_show_episode_and_mode() -> None:
    sub_history = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="2",
        mode="sub",
        stream_url="https://example.test/sub-2.mp4",
        display_name="Example - Episode 2",
        position=42,
        duration=100,
    )
    dub_history = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="2",
        mode="dub",
        stream_url="https://example.test/dub-2.mp4",
        display_name="Example - Episode 2",
        position=10,
        duration=100,
    )
    episode = AnimeEpisode(show_id="show-1", title="Example", number="2", mode="sub")

    history = episode_history_map([dub_history, sub_history])

    assert anime_history_key(episode) == ("show-1", "2", "sub")
    assert selected_episode_history(episode, history) == sub_history


def test_show_detail_episode_row_text_includes_resume_and_progress() -> None:
    episode = AnimeEpisode(show_id="show-1", title="Example", number="2", mode="sub")
    history_item = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="2",
        mode="sub",
        stream_url="https://example.test/sub-2.mp4",
        display_name="Example - Episode 2",
        position=42,
        duration=100,
    )

    assert episode_row_text(episode, history_item) == "Episode 2    Resume 00:00:42.00    42%"
    assert episode_row_text(episode, None) == "Episode 2    Not watched"


def test_show_detail_source_with_resume_attaches_position_metadata() -> None:
    source = MediaSource(
        location="https://example.test/sub-2.mp4",
        title="Example - Episode 2",
        headers={"User-Agent": "test"},
        metadata={"kind": "anime", "show_id": "show-1", "title": "Example", "episode": "2", "mode": "sub"},
    )
    history_item = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="2",
        mode="sub",
        stream_url="https://example.test/sub-2.mp4",
        display_name="Example - Episode 2",
        position=42,
        duration=100,
        subtitle_url="https://example.test/sub-2.vtt",
    )

    updated = episode_source_with_resume(source, history_item)

    assert updated.location == source.location
    assert updated.headers == source.headers
    assert updated.subtitle_url == "https://example.test/sub-2.vtt"
    assert updated.metadata["resume_position"] == "42.000000"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_player_config.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'ffmpeg_pywrapper.player.show_detail'`.

- [ ] **Step 3: Add helper module**

Create `src/ffmpeg_pywrapper/player/show_detail.py`:

```python
from __future__ import annotations

from ffmpeg_pywrapper import format_timestamp
from ffmpeg_pywrapper.anime import AnimeEpisode
from ffmpeg_pywrapper.media import MediaSource
from ffmpeg_pywrapper.player.config_store import AnimeHistoryItem, anime_history_progress

HistoryKey = tuple[str, str, str]


def anime_history_key(episode: AnimeEpisode) -> HistoryKey:
    return (episode.show_id, episode.number, episode.mode)


def episode_history_map(items: list[AnimeHistoryItem]) -> dict[HistoryKey, AnimeHistoryItem]:
    return {(item.show_id, item.episode, item.mode): item for item in items}


def selected_episode_history(
    episode: AnimeEpisode,
    history: dict[HistoryKey, AnimeHistoryItem],
) -> AnimeHistoryItem | None:
    return history.get(anime_history_key(episode))


def episode_row_text(episode: AnimeEpisode, history_item: AnimeHistoryItem | None) -> str:
    if history_item is None:
        return f"Episode {episode.number}    Not watched"
    progress = anime_history_progress(history_item)
    progress_text = f"    {progress}" if progress else ""
    if history_item.position > 0:
        return f"Episode {episode.number}    Resume {format_timestamp(history_item.position)}{progress_text}"
    return f"Episode {episode.number}    Watched{progress_text}"


def episode_source_with_resume(source: MediaSource, history_item: AnimeHistoryItem | None) -> MediaSource:
    if history_item is None or history_item.position <= 0:
        return source
    metadata = dict(source.metadata or {})
    metadata["resume_position"] = f"{history_item.position:.6f}"
    return MediaSource(
        location=source.location,
        title=source.title,
        headers=source.headers,
        subtitle_url=source.subtitle_url or history_item.subtitle_url,
        metadata=metadata,
    )
```

- [ ] **Step 4: Run tests to verify green**

Run:

```powershell
uv run pytest tests/test_player_config.py -q
```

Expected: all config/helper tests pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add src/ffmpeg_pywrapper/player/show_detail.py tests/test_player_config.py
git commit -m "feat: add show detail state helpers"
```

## Task 2: Add Show Detail Surface

**Files:**
- Modify: `src/ffmpeg_pywrapper/player/app.py`
- Test: `tests/test_player_smoke.py`

- [ ] **Step 1: Write failing construction test**

Append this test to `tests/test_player_smoke.py`:

```python
def test_show_detail_surface_constructs_offscreen(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)

    try:
        assert window.show_detail.objectName() == "animeShowDetail"
        assert window.show_detail.isHidden() is True
        assert window.show_detail_title.text() == ""
        assert window.show_detail_mode_combo.currentData() == "sub"
        assert window.show_detail_episodes.objectName() == "animeShowEpisodeList"
        assert window.show_detail_play_button.isEnabled() is False
        assert window.show_detail_resume_button.isEnabled() is False
    finally:
        window.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_show_detail_surface_constructs_offscreen -q
```

Expected: fails because `show_detail` widgets do not exist.

- [ ] **Step 3: Add imports and signals**

In `src/ffmpeg_pywrapper/player/app.py`, add this import:

```python
from ffmpeg_pywrapper.player.show_detail import (
    episode_history_map,
    episode_row_text,
    episode_source_with_resume,
    selected_episode_history,
)
```

Extend `PlayerSignals`:

```python
class PlayerSignals(QObject):
    frame_ready = Signal(object)
    state_changed = Signal(object)
    error = Signal(object)
    warning = Signal(object)
    anime_next_ready = Signal(object, object)
    show_detail_episodes_ready = Signal(str, object, object)
    show_detail_stream_ready = Signal(str, object, object)
```

In `PlayerWindow.__init__`, after the existing signal connections, add:

```python
self.signals.show_detail_episodes_ready.connect(self._handle_show_detail_episodes)
self.signals.show_detail_stream_ready.connect(self._handle_show_detail_stream)
self.current_show: AnimeSearchResult | None = None
self.current_show_mode: AnimeMode = "sub"
self.current_show_episodes: list[AnimeEpisode] = []
self._show_detail_request_id = ""
self._show_detail_stream_request_id = ""
```

- [ ] **Step 4: Add show detail widgets**

In `_build_ui`, after this existing line:

```python
self.anime_home = self._build_anime_home()
video_layout.addWidget(self.anime_home, 0, 0)
```

add:

```python
self.show_detail = self._build_show_detail()
self.show_detail.hide()
video_layout.addWidget(self.show_detail, 0, 0)
```

Add this method near `_build_anime_home`:

```python
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

    frame = QFrame()
    frame.setObjectName("animeShowDetail")
    frame.setLayout(layout)
    return frame
```

Add these stub-safe methods near `_refresh_anime_home`; later tasks will fill behavior:

```python
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
```

At the end of `_build_show_detail`, buttons start disabled through `_update_show_detail_buttons`. Add this before returning `frame`:

```python
self.show_detail_play_button.setEnabled(False)
self.show_detail_resume_button.setEnabled(False)
```

- [ ] **Step 5: Run test to verify green**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_show_detail_surface_constructs_offscreen -q
```

Expected: pass.

- [ ] **Step 6: Commit Task 2**

```powershell
git add src/ffmpeg_pywrapper/player/app.py tests/test_player_smoke.py
git commit -m "feat: add anime show detail surface"
```

## Task 3: Load Episodes Into Show Detail

**Files:**
- Modify: `src/ffmpeg_pywrapper/player/app.py`
- Test: `tests/test_player_smoke.py`

- [ ] **Step 1: Write failing episode-load tests**

Append these tests to `tests/test_player_smoke.py`:

```python
def test_show_detail_loads_episodes_and_history_state(monkeypatch, tmp_path) -> None:
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    config_path = tmp_path / "config.json"
    config = app_module.set_anime_history_item(
        {},
        app_module.AnimeHistoryItem(
            title="Example",
            show_id="show-1",
            episode="2",
            mode="sub",
            stream_url="https://example.test/episode-2.mp4",
            display_name="Example - Episode 2",
            position=50,
            duration=100,
        ),
    )
    app_module.save_config(config_path, config)

    class ImmediateThread:
        def __init__(self, target, daemon=False):  # noqa: ANN001, FBT002
            self.target = target

        def start(self) -> None:
            self.target()

    class FakeAnimeClient:
        def episodes(self, show, *, mode="sub"):  # noqa: ANN001
            return [
                app_module.AnimeEpisode(show_id=show.show_id, title=show.title, number="1", mode=mode),
                app_module.AnimeEpisode(show_id=show.show_id, title=show.title, number="2", mode=mode),
            ]

    monkeypatch.setattr(app_module.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(app_module, "user_config_path", lambda: config_path)
    app_module, window = _window(monkeypatch)
    window.anime_client = FakeAnimeClient()

    try:
        window.show_anime_detail(app_module.AnimeSearchResult(show_id="show-1", title="Example"), mode="sub")

        assert window.anime_home.isHidden() is True
        assert window.show_detail.isHidden() is False
        assert window.show_detail_title.text() == "Example"
        assert window.show_detail_episodes.count() == 2
        assert window.show_detail_episodes.item(0).text() == "Episode 1    Not watched"
        assert window.show_detail_episodes.item(1).text() == "Episode 2    Resume 00:00:50.00    50%"
        assert "2 episodes" in window.show_detail_status.text()
    finally:
        window.close()


def test_show_detail_episode_load_failure_keeps_refresh_enabled(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)

    try:
        window.show_detail_refresh_button.setEnabled(False)
        request_id = "episodes:1"
        window._show_detail_request_id = request_id
        window._handle_show_detail_episodes(request_id, None, RuntimeError("episode lookup failed"))

        assert window.show_detail_refresh_button.isEnabled() is True
        assert "episode lookup failed" in window.show_detail_status.text()
    finally:
        window.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_show_detail_loads_episodes_and_history_state tests/test_player_smoke.py::test_show_detail_episode_load_failure_keeps_refresh_enabled -q
```

Expected: fail because `show_anime_detail` and `_handle_show_detail_episodes` do not exist or do not load rows.

- [ ] **Step 3: Implement episode loading**

Add these methods to `PlayerWindow` near the show-detail helper methods:

```python
def show_anime_detail(self, show: AnimeSearchResult, *, mode: AnimeMode = "sub") -> None:
    self.current_show = show
    self.current_show_mode = mode if mode in {"sub", "dub"} else "sub"
    mode_index = self.show_detail_mode_combo.findData(self.current_show_mode)
    if mode_index >= 0 and self.show_detail_mode_combo.currentIndex() != mode_index:
        self.show_detail_mode_combo.blockSignals(True)
        self.show_detail_mode_combo.setCurrentIndex(mode_index)
        self.show_detail_mode_combo.blockSignals(False)
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
```

- [ ] **Step 4: Run tests to verify green**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_show_detail_loads_episodes_and_history_state tests/test_player_smoke.py::test_show_detail_episode_load_failure_keeps_refresh_enabled -q
```

Expected: both tests pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add src/ffmpeg_pywrapper/player/app.py tests/test_player_smoke.py
git commit -m "feat: load anime show detail episodes"
```

## Task 4: Play And Resume Episodes From Show Detail

**Files:**
- Modify: `src/ffmpeg_pywrapper/player/app.py`
- Test: `tests/test_player_smoke.py`

- [ ] **Step 1: Write failing playback tests**

Append these tests to `tests/test_player_smoke.py`:

```python
def test_show_detail_play_selected_episode_resolves_fast_stream(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)

    class ImmediateThread:
        def __init__(self, target, daemon=False):  # noqa: ANN001, FBT002
            self.target = target

        def start(self) -> None:
            self.target()

    class FakeAnimeClient:
        def fast_stream_for_episode(self, episode):  # noqa: ANN001
            return app_module.AnimeStream(
                url=f"https://example.test/{episode.number}.mp4",
                quality="direct",
                title=episode.title,
                episode=episode.number,
                show_id=episode.show_id,
                mode=episode.mode,
            )

    monkeypatch.setattr(app_module.threading, "Thread", ImmediateThread)
    window.anime_client = FakeAnimeClient()
    loaded = []
    monkeypatch.setattr(window, "play_source", lambda source: loaded.append(source))
    window.current_show_episodes = [app_module.AnimeEpisode(show_id="show-1", title="Example", number="3", mode="sub")]
    window._render_show_detail_episodes()

    try:
        window.show_detail_episodes.setCurrentRow(0)
        window.play_selected_show_detail_episode()

        assert len(loaded) == 1
        assert loaded[0].location == "https://example.test/3.mp4"
        assert loaded[0].metadata["episode"] == "3"
    finally:
        window.close()


def test_show_detail_resume_selected_episode_attaches_resume_position(monkeypatch, tmp_path) -> None:
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    config_path = tmp_path / "config.json"
    config = app_module.set_anime_history_item(
        {},
        app_module.AnimeHistoryItem(
            title="Example",
            show_id="show-1",
            episode="3",
            mode="sub",
            stream_url="https://example.test/old-3.mp4",
            display_name="Example - Episode 3",
            position=77,
            duration=100,
            subtitle_url="https://example.test/3.vtt",
        ),
    )
    app_module.save_config(config_path, config)

    class ImmediateThread:
        def __init__(self, target, daemon=False):  # noqa: ANN001, FBT002
            self.target = target

        def start(self) -> None:
            self.target()

    class FakeAnimeClient:
        def fast_stream_for_episode(self, episode):  # noqa: ANN001
            return app_module.AnimeStream(
                url=f"https://example.test/fresh-{episode.number}.mp4",
                quality="direct",
                title=episode.title,
                episode=episode.number,
                show_id=episode.show_id,
                mode=episode.mode,
            )

    monkeypatch.setattr(app_module.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(app_module, "user_config_path", lambda: config_path)
    app_module, window = _window(monkeypatch)
    window.anime_client = FakeAnimeClient()
    loaded = []
    monkeypatch.setattr(window, "play_source", lambda source: loaded.append(source))
    window.current_show_episodes = [app_module.AnimeEpisode(show_id="show-1", title="Example", number="3", mode="sub")]
    window._render_show_detail_episodes()

    try:
        window.show_detail_episodes.setCurrentRow(0)
        window.resume_selected_show_detail_episode()

        assert len(loaded) == 1
        assert loaded[0].location == "https://example.test/fresh-3.mp4"
        assert loaded[0].metadata["resume_position"] == "77.000000"
        assert loaded[0].subtitle_url == "https://example.test/3.vtt"
    finally:
        window.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_show_detail_play_selected_episode_resolves_fast_stream tests/test_player_smoke.py::test_show_detail_resume_selected_episode_attaches_resume_position -q
```

Expected: fail because show-detail playback methods are missing.

- [ ] **Step 3: Implement stream resolution and playback**

Add these methods to `PlayerWindow`:

```python
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


def _handle_show_detail_stream(self, request_id: str, result: object, error: object) -> None:
    if request_id != self._show_detail_stream_request_id:
        return
    if isinstance(error, Exception):
        self.show_detail_status.setText(str(error))
        self._update_show_detail_buttons()
        return
    if isinstance(result, MediaSource):
        self.play_source(result)
        return
    self.show_detail_status.setText("No playable stream returned.")
    self._update_show_detail_buttons()
```

- [ ] **Step 4: Run tests to verify green**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_show_detail_play_selected_episode_resolves_fast_stream tests/test_player_smoke.py::test_show_detail_resume_selected_episode_attaches_resume_position -q
```

Expected: both tests pass.

- [ ] **Step 5: Commit Task 4**

```powershell
git add src/ffmpeg_pywrapper/player/app.py tests/test_player_smoke.py
git commit -m "feat: play anime episodes from show detail"
```

## Task 5: Let Search Open Show Detail

**Files:**
- Modify: `src/ffmpeg_pywrapper/player/app.py`
- Test: `tests/test_player_smoke.py`

- [ ] **Step 1: Write failing search handoff tests**

Append these tests to `tests/test_player_smoke.py`:

```python
def test_anime_browser_can_return_selected_show(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt_widgets = pytest.importorskip("PySide6.QtWidgets")
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    app = qt_widgets.QApplication.instance() or qt_widgets.QApplication(["voidplayer-test"])
    dialog = app_module.AnimeBrowserDialog()

    try:
        dialog._apply_search_results([app_module.AnimeSearchResult(show_id="show-1", title="Example", episode_count=3)])
        dialog.results_list.setCurrentRow(0)
        dialog.accept_selected_show()

        assert dialog.selected_show == app_module.AnimeSearchResult(show_id="show-1", title="Example", episode_count=3)
        assert dialog.result() == app_module.QDialog.DialogCode.Accepted
    finally:
        dialog.close()


def test_home_search_opens_show_detail_when_dialog_returns_show(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)
    selected = app_module.AnimeSearchResult(show_id="show-1", title="Example", episode_count=3)

    class FakeDialog:
        selected_show = selected
        selected_stream = None

        def __init__(self, parent=None, *, client=None):  # noqa: ANN001
            self.search_input = app_module.QLineEdit()
            self.mode_combo = app_module.QComboBox()
            self.mode_combo.addItem("Sub", "sub")

        @property
        def mode(self):  # noqa: ANN201
            return "sub"

        def search(self) -> None:
            return None

        def exec(self):  # noqa: ANN201
            return app_module.QDialog.DialogCode.Accepted

    monkeypatch.setattr(app_module, "AnimeBrowserDialog", FakeDialog)
    monkeypatch.setattr(window, "_confirm_anime_disclaimer", lambda: True)
    opened = []
    monkeypatch.setattr(window, "show_anime_detail", lambda show, *, mode="sub": opened.append((show, mode)))
    window.anime_home_search_input.setText("Example")

    try:
        window.open_anime_home_search()

        assert opened == [(selected, "sub")]
    finally:
        window.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_anime_browser_can_return_selected_show tests/test_player_smoke.py::test_home_search_opens_show_detail_when_dialog_returns_show -q
```

Expected: fail because `selected_show`, `accept_selected_show`, and home-search handoff are not implemented.

- [ ] **Step 3: Add show selection to `AnimeBrowserDialog`**

In `AnimeBrowserDialog.__init__`, after `self.selected_stream`, add:

```python
self.selected_show: AnimeSearchResult | None = None
```

After creating `self.search_button`, create:

```python
self.open_show_button = QPushButton("Open Show")
self.open_show_button.setObjectName("animeContinueActionButton")
self.open_show_button.setEnabled(False)
```

In the bottom action row, before `self.play_button`, add:

```python
bottom_row.addWidget(self.open_show_button)
```

Add signal connections:

```python
self.results_list.itemSelectionChanged.connect(self._update_open_show_button)
self.open_show_button.clicked.connect(self.accept_selected_show)
```

Add these methods to `AnimeBrowserDialog` near `accept_selected_stream`:

```python
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
```

At the end of `_apply_search_results`, add:

```python
self._update_open_show_button()
```

When clearing results in `_apply_search_results`, `load_episodes`, and stale/empty branches, keep `open_show_button` consistent by calling `_update_open_show_button()`.

- [ ] **Step 4: Route accepted show to show detail**

In `open_anime_browser`, replace the accepted branch with:

```python
if dialog.exec() == QDialog.DialogCode.Accepted:
    if dialog.selected_show is not None:
        self.show_anime_detail(dialog.selected_show, mode=dialog.mode)
    elif dialog.selected_stream is not None:
        self.play_source(dialog.selected_stream.to_media_source())
```

In `open_anime_home_search`, replace the accepted branch with:

```python
if dialog.exec() == QDialog.DialogCode.Accepted:
    if dialog.selected_show is not None:
        self.show_anime_detail(dialog.selected_show, mode=dialog.mode)
    elif dialog.selected_stream is not None:
        self.play_source(dialog.selected_stream.to_media_source())
```

- [ ] **Step 5: Run tests to verify green**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_anime_browser_can_return_selected_show tests/test_player_smoke.py::test_home_search_opens_show_detail_when_dialog_returns_show -q
```

Expected: both tests pass.

- [ ] **Step 6: Commit Task 5**

```powershell
git add src/ffmpeg_pywrapper/player/app.py tests/test_player_smoke.py
git commit -m "feat: open anime show detail from search"
```

## Task 6: Mode Switching And Visual Polish

**Files:**
- Modify: `src/ffmpeg_pywrapper/player/app.py`
- Modify: `src/ffmpeg_pywrapper/player/themes/default/style.qss`
- Modify: `src/ffmpeg_pywrapper/player/themes/catppuccin-frappe/style.qss`
- Modify: `src/ffmpeg_pywrapper/player/themes/catppuccin-macchiato/style.qss`
- Modify: `src/ffmpeg_pywrapper/player/themes/catppuccin-mocha/style.qss`
- Test: `tests/test_player_smoke.py`
- Test: `tests/test_theme.py`

- [ ] **Step 1: Write failing mode-switch and theme tests**

Append to `tests/test_player_smoke.py`:

```python
def test_show_detail_mode_switch_reloads_same_show(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)
    show = app_module.AnimeSearchResult(show_id="show-1", title="Example")
    calls = []
    window.current_show = show
    window.current_show_mode = "sub"
    monkeypatch.setattr(window, "show_anime_detail", lambda selected, *, mode="sub": calls.append((selected, mode)))

    try:
        window.show_detail_mode_combo.setCurrentIndex(window.show_detail_mode_combo.findData("dub"))

        assert calls == [(show, "dub")]
    finally:
        window.close()
```

Append to `tests/test_theme.py`:

```python
def test_show_detail_widgets_are_styled_in_all_packaged_themes() -> None:
    for theme_name in theme_module.PACKAGED_THEMES:
        stylesheet = theme_module.render_stylesheet(theme_module.load_theme(theme_name))

        assert "QFrame#animeShowDetail" in stylesheet
        assert "QListWidget#animeShowEpisodeList" in stylesheet
```

- [ ] **Step 2: Run tests to verify failures**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_show_detail_mode_switch_reloads_same_show tests/test_theme.py::test_show_detail_widgets_are_styled_in_all_packaged_themes -q
```

Expected: mode test may already pass if Task 2 implemented mode switching; theme test fails until QSS rules are added.

- [ ] **Step 3: Add QSS rules to all packaged themes**

In each packaged `style.qss`, add this block near the anime home/list rules:

```css
QFrame#animeShowDetail {
    background: {{ color.window_background }};
    color: {{ color.text_primary }};
}
QListWidget#animeShowEpisodeList {
    background: {{ color.control_background }};
    color: {{ color.text_primary }};
    border: 1px solid {{ color.border_control }};
    border-radius: {{ size.control_radius }};
    padding: 8px;
}
QListWidget#animeShowEpisodeList::item {
    padding: 10px 12px;
    border-radius: {{ size.button_radius }};
}
QListWidget#animeShowEpisodeList::item:selected {
    background: {{ color.button_background }};
    color: {{ color.text_button }};
}
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_show_detail_mode_switch_reloads_same_show tests/test_theme.py::test_show_detail_widgets_are_styled_in_all_packaged_themes -q
```

Expected: both tests pass.

- [ ] **Step 5: Commit Task 6**

```powershell
git add src/ffmpeg_pywrapper/player/app.py src/ffmpeg_pywrapper/player/themes/default/style.qss src/ffmpeg_pywrapper/player/themes/catppuccin-frappe/style.qss src/ffmpeg_pywrapper/player/themes/catppuccin-macchiato/style.qss src/ffmpeg_pywrapper/player/themes/catppuccin-mocha/style.qss tests/test_player_smoke.py tests/test_theme.py
git commit -m "style: polish anime show detail view"
```

## Task 7: Documentation And Roadmap Update

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-05-11-project-state-and-next-steps.md`

- [ ] **Step 1: Update README user flow**

In `README.md`, update the feature list so it includes:

```markdown
- Opens search results into a show detail and episode browser workflow.
- Shows watched/resume state before playing an episode.
```

Update "How To Use" to this flow:

```markdown
1. Launch `animeplayer` or `voidplayer`.
2. Accept the anime source disclaimer.
3. Search for a show from the home screen.
4. Choose `Sub` or `Dub`.
5. Open the show detail view.
6. Select an episode and choose Play or Resume.
7. Use `Next Episode` when you want to continue the show.
8. Press `Home` at any time to return to the home screen; your anime timestamp is saved for Continue Watching.
```

- [ ] **Step 2: Update roadmap snapshot**

In `docs/superpowers/specs/2026-05-11-project-state-and-next-steps.md`, add completed-work bullets:

```markdown
19. Added provider-stage errors and retry hints.
20. Added persistent search, episode, and stream cache support.
21. Upgraded Continue Watching with grouped history, progress, Resume, Next Episode, Remove, and near-end next behavior.
```

Replace the "First Plan To Write Next" section with:

````markdown
The best next implementation plan is:

```text
Show detail and episode browser
```

Scope it as one vertical slice:

- Add pure show-detail helper functions for episode/history state.
- Add an in-app show detail surface.
- Load episode metadata through the existing cached `AnimeClient`.
- Open show detail from anime search results.
- Resolve fast streams from selected episodes.
- Attach resume metadata when history exists.
- Verify with focused player/config/theme tests, full tests, Rust tests, and Graphify.
```
````

- [ ] **Step 3: Inspect docs**

Run:

```powershell
Select-String -Path README.md,docs\superpowers\specs\2026-05-11-project-state-and-next-steps.md -Pattern "Show detail|episode browser|Continue Watching"
```

Expected: output shows the new README flow and roadmap section.

- [ ] **Step 4: Commit Task 7**

```powershell
git add README.md docs/superpowers/specs/2026-05-11-project-state-and-next-steps.md
git commit -m "docs: set show detail as next roadmap slice"
```

## Task 8: Final Verification

**Files:**
- No new implementation files unless verification reveals a root cause.
- Generated if available: `graphify-out/`

- [ ] **Step 1: Run focused tests**

```powershell
uv run pytest tests/test_player_config.py tests/test_player_smoke.py tests/test_theme.py tests/test_anime.py -q
```

Expected: all focused tests pass.

- [ ] **Step 2: Run full Python tests**

```powershell
uv run pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Run Rust tests**

```powershell
cargo test
```

Run from:

```powershell
rust
```

Expected: all Rust tests pass.

- [ ] **Step 4: Rebuild Graphify**

```powershell
python -m graphify update . --force
```

Expected: Graphify completes successfully. Generated output stays under ignored `graphify-out/` unless tracked files already exist.

- [ ] **Step 5: Inspect worktree**

```powershell
git status --short --branch
git diff --stat
```

Expected: only intentional show-detail changes are present, plus the pre-existing `rust/src/process.rs` change if it was still dirty before implementation. Do not commit unrelated `rust/src/process.rs` changes with this feature unless the user explicitly asks for that scope.

## Self-Review

- Spec coverage: Tasks cover pure show-detail state, UI surface, episode loading, mode switching, Play/Resume, search handoff, error status, docs, and verification.
- Placeholder scan: No placeholder markers or unspecified implementation steps remain.
- Type consistency: `AnimeSearchResult`, `AnimeEpisode`, `AnimeStream`, `AnimeHistoryItem`, `MediaSource`, and helper names are consistent across tasks.
- Scope check: The plan is one vertical product slice and excludes provider picker, subtitle/audio controls, local library import, release automation, and Rust migration.

# Rich Continue Watching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Continue Watching into the main daily-use surface with explicit resume/remove/next actions, stable last-watched ordering, progress display, show grouping, and near-end next-episode handling.

**Architecture:** Extend the existing config-backed `AnimeHistoryItem` model first, then add pure formatting/action helpers that are easy to test, then wire those helpers into `PlayerWindow._build_anime_home`, `_refresh_anime_home`, and `play_anime_history_item`. Keep playback resolution through the existing `AnimeClient -> AnimeStream -> MediaSource` path and keep local-file player scope out of the feature.

**Tech Stack:** Python 3.13, PySide6 widgets, existing `ffmpeg_pywrapper.player.config_store`, existing `AnimeClient`/`AnimeEpisode`/`AnimeStream`, pytest offscreen GUI tests, Graphify.

---

## File Structure

- Modify: `src/ffmpeg_pywrapper/player/config_store.py`
  - Add optional `duration` to `AnimeHistoryItem`.
  - Add `remove_anime_history_item`.
  - Add `sorted_anime_history`.
  - Add `anime_history_progress`.
  - Add `should_continue_with_next_episode`.
- Modify: `src/ffmpeg_pywrapper/player/app.py`
  - Persist duration when remembering anime sources.
  - Render grouped Continue Watching rows.
  - Add Resume, Remove, and Next Episode buttons for selected history items.
  - Use near-end logic when resuming a completed/nearly completed item.
  - Preserve compact layout behavior.
- Modify: `src/ffmpeg_pywrapper/player/themes/default/style.qss`
  - Style the Continue Watching action row and grouped rows.
- Modify: `src/ffmpeg_pywrapper/player/themes/catppuccin-frappe/style.qss`
  - Mirror Continue Watching action styling.
- Modify: `src/ffmpeg_pywrapper/player/themes/catppuccin-macchiato/style.qss`
  - Mirror Continue Watching action styling.
- Modify: `src/ffmpeg_pywrapper/player/themes/catppuccin-mocha/style.qss`
  - Mirror Continue Watching action styling.
- Modify: `tests/test_player_config.py`
  - Cover duration persistence, removal, stable sorting, progress display, and near-end detection.
- Modify: `tests/test_player_smoke.py`
  - Cover Continue Watching buttons, removal, grouping, progress text, and near-end next-episode behavior.

## Task 1: Extend Anime History Data

**Files:**
- Modify: `src/ffmpeg_pywrapper/player/config_store.py`
- Test: `tests/test_player_config.py`

- [ ] **Step 1: Write failing config tests**

Append these tests to `tests/test_player_config.py`:

```python
def test_anime_history_round_trip_preserves_duration(tmp_path) -> None:  # noqa: ANN001
    config_path = tmp_path / "config.json"
    item = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="3",
        mode="sub",
        stream_url="https://example.test/episode-3.mp4",
        display_name="Example - Episode 3",
        position=45,
        duration=100,
    )

    save_config(config_path, set_anime_history_item({}, item))
    history = anime_history_from_config(load_config(config_path))

    assert history[0].duration == 100


def test_remove_anime_history_item_preserves_other_entries() -> None:
    first = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="1",
        mode="sub",
        stream_url="https://example.test/1.mp4",
        display_name="Example - Episode 1",
    )
    second = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="2",
        mode="sub",
        stream_url="https://example.test/2.mp4",
        display_name="Example - Episode 2",
    )
    config = set_anime_history_item(set_anime_history_item({}, first), second)

    updated = remove_anime_history_item(config, show_id="show-1", episode="2", mode="sub")
    history = anime_history_from_config(updated)

    assert len(history) == 1
    assert history[0].episode == "1"


def test_sorted_anime_history_orders_last_watched_first() -> None:
    older = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="1",
        mode="sub",
        stream_url="https://example.test/1.mp4",
        display_name="Example - Episode 1",
        updated_at=10,
    )
    newer = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="2",
        mode="sub",
        stream_url="https://example.test/2.mp4",
        display_name="Example - Episode 2",
        updated_at=20,
    )

    assert [item.episode for item in sorted_anime_history([older, newer])] == ["2", "1"]


def test_anime_history_progress_formats_known_duration() -> None:
    item = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="1",
        mode="sub",
        stream_url="https://example.test/1.mp4",
        display_name="Example - Episode 1",
        position=50,
        duration=200,
    )

    assert anime_history_progress(item) == "25%"


def test_should_continue_with_next_episode_when_near_end() -> None:
    near_end = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="1",
        mode="sub",
        stream_url="https://example.test/1.mp4",
        display_name="Example - Episode 1",
        position=296,
        duration=300,
    )
    middle = AnimeHistoryItem(
        title="Example",
        show_id="show-1",
        episode="1",
        mode="sub",
        stream_url="https://example.test/1.mp4",
        display_name="Example - Episode 1",
        position=120,
        duration=300,
    )

    assert should_continue_with_next_episode(near_end) is True
    assert should_continue_with_next_episode(middle) is False
```

Also update the import in `tests/test_player_config.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_player_config.py -q
```

Expected: fail during collection or assertions because `duration`, `remove_anime_history_item`, `sorted_anime_history`, `anime_history_progress`, and `should_continue_with_next_episode` do not exist yet.

- [ ] **Step 3: Implement config helpers**

In `src/ffmpeg_pywrapper/player/config_store.py`, update the dataclass and helpers:

```python
@dataclass(frozen=True, slots=True)
class AnimeHistoryItem:
    title: str
    show_id: str
    episode: str
    mode: str
    stream_url: str
    display_name: str
    position: float = 0.0
    duration: float | None = None
    subtitle_url: str | None = None
    updated_at: float = 0.0
```

When constructing `AnimeHistoryItem` in `anime_history_from_config`, include:

```python
duration=_optional_positive_float(raw.get("duration")),
```

When constructing `fresh` in `set_anime_history_item`, include:

```python
duration=item.duration,
```

Add these functions near `set_anime_history_item`:

```python
def remove_anime_history_item(config: dict[str, Any], *, show_id: str, episode: str, mode: str) -> dict[str, Any]:
    updated = dict(config)
    key = (show_id, episode, mode)
    kept = [item for item in anime_history_from_config(config) if (item.show_id, item.episode, item.mode) != key]
    updated["anime_history"] = [asdict(item) for item in kept]
    return updated


def sorted_anime_history(items: list[AnimeHistoryItem]) -> list[AnimeHistoryItem]:
    return sorted(items, key=lambda item: item.updated_at, reverse=True)


def anime_history_progress(item: AnimeHistoryItem) -> str | None:
    if item.duration is None or item.duration <= 0:
        return None
    percent = int(min(max(item.position / item.duration, 0.0), 1.0) * 100)
    return f"{percent}%"


def should_continue_with_next_episode(item: AnimeHistoryItem, *, edge_seconds: float = 15.0) -> bool:
    if item.duration is None or item.duration <= edge_seconds * 2:
        return False
    return item.duration - min(max(item.position, 0.0), item.duration) <= edge_seconds
```

Add this helper near `_float`:

```python
def _optional_positive_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
```

- [ ] **Step 4: Run tests to verify green**

Run:

```powershell
uv run pytest tests/test_player_config.py -q
```

Expected: all `tests/test_player_config.py` tests pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add src/ffmpeg_pywrapper/player/config_store.py tests/test_player_config.py
git commit -m "feat: enrich anime history metadata"
```

## Task 2: Add Continue Watching Selection Actions

**Files:**
- Modify: `src/ffmpeg_pywrapper/player/app.py`
- Test: `tests/test_player_smoke.py`

- [ ] **Step 1: Write failing GUI tests for action buttons and removal**

Append these tests to `tests/test_player_smoke.py`:

```python
def test_continue_watching_buttons_enable_for_selected_history(monkeypatch, tmp_path) -> None:
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    config_path = tmp_path / "config.json"
    config = app_module.set_anime_history_item(
        {},
        app_module.AnimeHistoryItem(
            title="Example",
            show_id="show-1",
            episode="3",
            mode="sub",
            stream_url="https://example.test/episode-3.mp4",
            display_name="Example - Episode 3",
            position=40,
            duration=100,
        ),
    )
    app_module.save_config(config_path, config)
    monkeypatch.setattr(app_module, "user_config_path", lambda: config_path)
    app_module, window = _window(monkeypatch)

    try:
        assert window.continue_resume_button.isEnabled() is False
        assert window.continue_remove_button.isEnabled() is False
        assert window.continue_next_button.isEnabled() is False

        window.anime_continue_list.setCurrentRow(0)

        assert window.continue_resume_button.isEnabled() is True
        assert window.continue_remove_button.isEnabled() is True
        assert window.continue_next_button.isEnabled() is True
    finally:
        window.close()


def test_remove_selected_continue_watching_item_updates_config_and_list(monkeypatch, tmp_path) -> None:
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    config_path = tmp_path / "config.json"
    config = app_module.set_anime_history_item(
        {},
        app_module.AnimeHistoryItem(
            title="Example",
            show_id="show-1",
            episode="3",
            mode="sub",
            stream_url="https://example.test/episode-3.mp4",
            display_name="Example - Episode 3",
            position=40,
            duration=100,
        ),
    )
    app_module.save_config(config_path, config)
    monkeypatch.setattr(app_module, "user_config_path", lambda: config_path)
    app_module, window = _window(monkeypatch)

    try:
        window.anime_continue_list.setCurrentRow(0)
        window.remove_selected_anime_history_item()

        assert app_module.anime_history_from_config(app_module.load_config(config_path)) == []
        assert window.anime_continue_list.item(0).text() == "No anime history yet"
        assert window.continue_resume_button.isEnabled() is False
    finally:
        window.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_continue_watching_buttons_enable_for_selected_history tests/test_player_smoke.py::test_remove_selected_continue_watching_item_updates_config_and_list -q
```

Expected: fail because `continue_resume_button`, `continue_remove_button`, `continue_next_button`, and `remove_selected_anime_history_item` do not exist.

- [ ] **Step 3: Implement action buttons**

In `src/ffmpeg_pywrapper/player/app.py`, update imports from `config_store`:

```python
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
```

In `_build_anime_home`, after creating `self.anime_continue_list`, add:

```python
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
```

In the continue panel layout, add the action row below the list:

```python
continue_panel_layout.addWidget(self.anime_continue_list, 1)
continue_panel_layout.addLayout(self.anime_continue_actions)
```

Add these methods to `PlayerWindow` near `play_anime_history_item`:

```python
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
    item = self.anime_continue_list.currentItem()
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
```

At the end of `_refresh_anime_home`, call:

```python
self._update_continue_action_buttons()
```

- [ ] **Step 4: Run tests to verify green**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_continue_watching_buttons_enable_for_selected_history tests/test_player_smoke.py::test_remove_selected_continue_watching_item_updates_config_and_list -q
```

Expected: both tests pass.

- [ ] **Step 5: Commit Task 2**

```powershell
git add src/ffmpeg_pywrapper/player/app.py tests/test_player_smoke.py
git commit -m "feat: add continue watching actions"
```

## Task 3: Render Grouped History With Progress

**Files:**
- Modify: `src/ffmpeg_pywrapper/player/app.py`
- Test: `tests/test_player_smoke.py`

- [ ] **Step 1: Write failing GUI test for grouping and progress**

Append this test to `tests/test_player_smoke.py`:

```python
def test_continue_watching_groups_by_show_and_shows_progress(monkeypatch, tmp_path) -> None:
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    config_path = tmp_path / "config.json"
    config = {}
    for item in (
        app_module.AnimeHistoryItem(
            title="Other",
            show_id="show-2",
            episode="1",
            mode="sub",
            stream_url="https://example.test/other-1.mp4",
            display_name="Other - Episode 1",
            position=20,
            duration=100,
            updated_at=20,
        ),
        app_module.AnimeHistoryItem(
            title="Example",
            show_id="show-1",
            episode="2",
            mode="sub",
            stream_url="https://example.test/example-2.mp4",
            display_name="Example - Episode 2",
            position=50,
            duration=200,
            updated_at=30,
        ),
        app_module.AnimeHistoryItem(
            title="Example",
            show_id="show-1",
            episode="1",
            mode="sub",
            stream_url="https://example.test/example-1.mp4",
            display_name="Example - Episode 1",
            position=75,
            duration=100,
            updated_at=10,
        ),
    ):
        config = app_module.set_anime_history_item(config, item)
    app_module.save_config(config_path, config)
    monkeypatch.setattr(app_module, "user_config_path", lambda: config_path)
    app_module, window = _window(monkeypatch)

    try:
        texts = [window.anime_continue_list.item(index).text() for index in range(window.anime_continue_list.count())]

        assert texts[0] == "Example"
        assert "Episode 2" in texts[1]
        assert "25%" in texts[1]
        assert "Episode 1" in texts[2]
        assert "75%" in texts[2]
        assert texts[3] == "Other"
        assert "20%" in texts[4]
    finally:
        window.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_continue_watching_groups_by_show_and_shows_progress -q
```

Expected: fail because the current list renders flat rows with no group headers and no progress percentage.

- [ ] **Step 3: Implement grouped rendering**

Update `_refresh_anime_home` in `src/ffmpeg_pywrapper/player/app.py`:

```python
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
    previous_show_id: str | None = None
    for history_item in sorted_anime_history(self.anime_history)[:20]:
        if history_item.show_id != previous_show_id:
            header = QListWidgetItem(history_item.title)
            header.setData(Qt.ItemDataRole.UserRole, None)
            header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsEnabled)
            self.anime_continue_list.addItem(header)
            previous_show_id = history_item.show_id
        progress = anime_history_progress(history_item)
        progress_text = f"    {progress}" if progress else ""
        resume_text = format_timestamp(history_item.position) if history_item.position > 0 else "start"
        item = QListWidgetItem(f"Episode {history_item.episode}    Resume {resume_text}{progress_text}")
        item.setToolTip(history_item.stream_url)
        item.setData(Qt.ItemDataRole.UserRole, history_item)
        self.anime_continue_list.addItem(item)
    self._update_continue_action_buttons()
```

- [ ] **Step 4: Run test to verify green**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_continue_watching_groups_by_show_and_shows_progress -q
```

Expected: pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add src/ffmpeg_pywrapper/player/app.py tests/test_player_smoke.py
git commit -m "feat: group continue watching history"
```

## Task 4: Persist Duration And Handle Near-End Resume As Next Episode

**Files:**
- Modify: `src/ffmpeg_pywrapper/player/app.py`
- Test: `tests/test_player_smoke.py`

- [ ] **Step 1: Write failing GUI tests for duration persistence and near-end next**

Append these tests to `tests/test_player_smoke.py`:

```python
def test_anime_source_load_updates_continue_watching_duration(monkeypatch, tmp_path) -> None:
    app_module, window = _window(monkeypatch, tmp_path)
    source = MediaSource(
        location="https://example.test/episode-4.mp4",
        title="Example - Episode 4",
        metadata={"kind": "anime", "show_id": "show-1", "title": "Example", "episode": "4", "mode": "dub"},
    )
    media = MediaInfo(path=source.location, duration=100.0, streams=(StreamInfo(index=0, codec_type="video", codec_name="h264"),))
    monkeypatch.setattr(window.player, "load", lambda loaded_source: media)
    monkeypatch.setattr(window.player, "play", lambda: None)

    try:
        window.play_source(source)

        history = app_module.anime_history_from_config(app_module.load_config(tmp_path / "config.json"))
        assert history[0].duration == 100.0
        assert "0%" in window.anime_continue_list.item(1).text()
    finally:
        window.close()


def test_near_end_continue_watching_plays_next_episode(monkeypatch, tmp_path) -> None:
    app_module = importlib.import_module("ffmpeg_pywrapper.player.app")
    config_path = tmp_path / "config.json"
    config = app_module.set_anime_history_item(
        {},
        app_module.AnimeHistoryItem(
            title="Example",
            show_id="show-1",
            episode="1",
            mode="sub",
            stream_url="https://example.test/episode-1.mp4",
            display_name="Example - Episode 1",
            position=296,
            duration=300,
        ),
    )
    app_module.save_config(config_path, config)

    class ImmediateThread:
        def __init__(self, target, daemon=False):  # noqa: ANN001, FBT002
            self.target = target

        def start(self) -> None:
            self.target()

    class FakeAnimeClient:
        def next_episode(self, episode):  # noqa: ANN001
            return app_module.AnimeEpisode(show_id=episode.show_id, title=episode.title, number="2", mode=episode.mode)

        def fast_stream_for_episode(self, episode):  # noqa: ANN001
            return app_module.AnimeStream(
                url="https://example.test/episode-2.mp4",
                quality="direct",
                title=episode.title,
                episode=episode.number,
                show_id=episode.show_id,
                mode=episode.mode,
            )

    monkeypatch.setattr(app_module.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(app_module, "user_config_path", lambda: config_path)
    app_module, window = _window(monkeypatch)
    window.config["anime_disclaimer_accepted"] = True
    window.anime_client = FakeAnimeClient()
    loaded = []
    monkeypatch.setattr(window, "load_and_play", lambda source: loaded.append(source))

    try:
        window.anime_continue_list.setCurrentRow(1)
        window.resume_selected_anime_history_item()

        assert window.current_source is not None
        assert window.current_source.metadata["episode"] == "2"
        assert window.current_source.location == "https://example.test/episode-2.mp4"
        assert loaded == [window.current_source]
    finally:
        window.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_anime_source_load_updates_continue_watching_duration tests/test_player_smoke.py::test_near_end_continue_watching_plays_next_episode -q
```

Expected: first test fails because duration is not persisted; second fails because history resume always replays the saved episode.

- [ ] **Step 3: Persist duration**

In `_remember_anime_source`, change the `AnimeHistoryItem` construction to include:

```python
duration=self.duration if self.duration > 0 else None,
```

- [ ] **Step 4: Implement selected-history Next Episode path**

Add this method near `resume_selected_anime_history_item`:

```python
def play_next_for_selected_anime_history_item(self) -> None:
    history_item = self._selected_anime_history_item()
    if history_item is None:
        return
    if not self._confirm_anime_disclaimer():
        return
    episode = AnimeEpisode(
        show_id=history_item.show_id,
        title=history_item.title,
        number=history_item.episode,
        mode=history_item.mode if history_item.mode in ("sub", "dub") else "sub",
    )

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

    self.statusBar().showMessage(f"Resolving next episode after {history_item.display_name}...")
    threading.Thread(target=worker, daemon=True).start()
```

Update `play_anime_history_item` near the top after disclaimer:

```python
if should_continue_with_next_episode(history_item):
    self.play_next_for_selected_anime_history_item()
    return
```

- [ ] **Step 5: Run tests to verify green**

Run:

```powershell
uv run pytest tests/test_player_smoke.py::test_anime_source_load_updates_continue_watching_duration tests/test_player_smoke.py::test_near_end_continue_watching_plays_next_episode -q
```

Expected: both tests pass.

- [ ] **Step 6: Commit Task 4**

```powershell
git add src/ffmpeg_pywrapper/player/app.py tests/test_player_smoke.py
git commit -m "feat: continue near-finished anime with next episode"
```

## Task 5: Theme The Rich Continue Watching Controls

**Files:**
- Modify: `src/ffmpeg_pywrapper/player/themes/default/style.qss`
- Modify: `src/ffmpeg_pywrapper/player/themes/catppuccin-frappe/style.qss`
- Modify: `src/ffmpeg_pywrapper/player/themes/catppuccin-macchiato/style.qss`
- Modify: `src/ffmpeg_pywrapper/player/themes/catppuccin-mocha/style.qss`
- Test: `tests/test_theme.py`

- [ ] **Step 1: Write failing theme test**

Append this test to `tests/test_theme.py`:

```python
def test_continue_watching_action_button_is_styled_in_all_packaged_themes() -> None:
    from ffmpeg_pywrapper.player.theme import PACKAGED_THEMES, load_theme, render_stylesheet

    for theme_name in PACKAGED_THEMES:
        stylesheet = render_stylesheet(load_theme(theme_name))
        assert "QPushButton#animeContinueActionButton" in stylesheet
        assert "QListWidget#animeContinueList::item" in stylesheet
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/test_theme.py::test_continue_watching_action_button_is_styled_in_all_packaged_themes -q
```

Expected: fail because `animeContinueActionButton` is not styled yet.

- [ ] **Step 3: Add theme rules**

Add this block to each bundled `style.qss` file after the `QListWidget#animeContinueList::item:selected` block:

```css
QPushButton#animeContinueActionButton {
    background: {{ color.button_background }};
    color: {{ color.text_button }};
    border: 1px solid {{ color.border_button }};
    border-radius: {{ size.button_radius }};
    padding: 7px 12px;
    min-height: 26px;
}
QPushButton#animeContinueActionButton:hover {
    background: {{ color.button_hover_background }};
    border-color: {{ color.border_button_hover }};
}
QPushButton#animeContinueActionButton:disabled {
    color: {{ color.text_muted }};
    background: {{ color.control_background }};
}
```

- [ ] **Step 4: Run theme tests**

Run:

```powershell
uv run pytest tests/test_theme.py -q
```

Expected: all theme tests pass.

- [ ] **Step 5: Commit Task 5**

```powershell
git add src/ffmpeg_pywrapper/player/themes/default/style.qss src/ffmpeg_pywrapper/player/themes/catppuccin-frappe/style.qss src/ffmpeg_pywrapper/player/themes/catppuccin-macchiato/style.qss src/ffmpeg_pywrapper/player/themes/catppuccin-mocha/style.qss tests/test_theme.py
git commit -m "style: polish continue watching actions"
```

## Task 6: Final Verification And Graphify

**Files:**
- No new implementation files unless a verification failure reveals a root cause.
- Generated: `graphify-out/`

- [ ] **Step 1: Run focused tests**

```powershell
uv run pytest tests/test_player_config.py tests/test_player_smoke.py tests/test_theme.py tests/test_anime.py -q
```

Expected: all focused tests pass.

- [ ] **Step 2: Run full tests**

```powershell
uv run pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Build package**

```powershell
uv build
```

Expected: source distribution and wheel build successfully under `dist/`.

- [ ] **Step 4: Rebuild Graphify**

```powershell
python -m graphify update . --force
```

Expected: Graphify reports a successful rebuild and updates outputs under `graphify-out/`.

- [ ] **Step 5: Inspect worktree**

```powershell
git status --short --branch
git diff --stat
```

Expected: only intentional implementation changes plus expected generated Graphify artifacts are present. Existing unrelated changes from before this plan should remain separate and should not be committed with this feature.

- [ ] **Step 6: Commit final Graphify/artifact changes if tracked**

If Graphify changed tracked files, commit those tracked Graphify outputs with the feature branch changes:

```powershell
git add graphify-out
git commit -m "chore: update graphify map"
```

If Graphify outputs are untracked or ignored, do not force-add them.

## Self-Review

- Spec coverage: The plan covers Resume, Remove, Next Episode, last-watched sorting, show grouping, progress percentage, near-end next behavior, smaller-screen preservation through existing layout tests, and Graphify.
- Placeholder scan: No placeholders are present; every task has concrete files, test snippets, implementation snippets, commands, and expected outcomes.
- Type consistency: The new `AnimeHistoryItem.duration`, `remove_anime_history_item`, `sorted_anime_history`, `anime_history_progress`, and `should_continue_with_next_episode` names are consistent across tests and implementation snippets.

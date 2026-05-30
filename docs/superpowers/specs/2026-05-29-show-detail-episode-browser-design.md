# Show Detail And Episode Browser Design

## Goal

Build a first-class show detail and episode browser workflow for VoidPlayer. Search should lead to a selected show view where the user can inspect episodes, see watched/resume state, switch sub/dub mode, and start playback without treating the whole anime experience as a one-off modal picker.

This is the next product slice after provider cache/resilience and rich Continue Watching. Those pieces already exist in the current tree, so this design reuses them instead of rebuilding provider diagnostics or history storage.

## Current Context

VoidPlayer currently starts on an anime home screen and opens `AnimeBrowserDialog` for search. The dialog can search, list episodes, resolve fast streams, and return a selected `AnimeStream`. Continue Watching has grouped rows, Resume, Next Episode, Remove, progress percentages, and near-end next-episode behavior.

The provider layer already has:

- `AnimeSearchResult`, `AnimeEpisode`, and `AnimeStream` contracts.
- `AnimeClient.search`, `episodes`, `fast_streams`, `streams`, `next_episode`, and `fast_stream_for_episode`.
- `AnimeResolvedCache` with separate metadata and stream TTL behavior.
- `AnimeProviderStage` and `AnimeClientError` for staged provider failures.

The main remaining product gap is navigation: users can resume known shows, but new browsing still feels like a modal search utility rather than an anime client.

## User Experience

The home screen keeps the current search field, sub/dub selector, and Continue Watching panel. Searching from the home screen opens search results, and choosing a result moves into a show detail view inside the main player surface.

The show detail view contains:

- Show title.
- Current mode selector for Sub/Dub.
- Episode list for the selected show and mode.
- Per-episode state: unwatched, watched, resume timestamp, progress percentage when duration is known.
- Primary actions for selected episode: Play, Resume when history exists, and Refresh Episodes.
- Compact status line for loading, cache hits when easy to know, and provider errors.

The user can return Home at any time. Existing playback controls remain unchanged. The app should still optimize time-to-first-play: selecting an episode resolves a fast stream first, starts playback when available, and only uses slower resolution if the user explicitly asks for more quality options in a later feature.

## Architecture

Add a small show-detail state layer in Python and keep provider work in `AnimeClient`.

New focused units:

- `src/ffmpeg_pywrapper/player/show_detail.py`
  - Pure data helpers for show detail state, episode history matching, progress labels, and selected-episode playback metadata.
  - No Qt imports.
- `PlayerWindow` show detail UI in `src/ffmpeg_pywrapper/player/app.py`
  - Owns widgets, transitions between Home and Show Detail, worker threads, and playback calls.
  - Reuses existing `AnimeClient`, `MediaSource`, `AnimeHistoryItem`, and `play_source`.

Do not introduce a new framework or persistence store. The existing config file remains the source of truth for watched/resume state. Provider metadata remains in `anime-cache.json` through `AnimeResolvedCache`.

## Data Flow

1. User searches from Home.
2. `AnimeBrowserDialog` or a lighter search results dialog returns an `AnimeSearchResult`.
3. `PlayerWindow.show_anime_detail(result, mode)` renders the show detail surface and starts an episode-load worker.
4. Worker calls `AnimeClient.episodes(result, mode=mode)`.
5. UI renders episode rows using `show_detail` helpers and current `self.anime_history`.
6. User selects an episode and clicks Play or Resume.
7. Worker calls `AnimeClient.fast_stream_for_episode(episode)`.
8. Returned `AnimeStream` becomes `MediaSource`.
9. If history has a resumable position, `resume_position` is attached to source metadata.
10. Existing `play_source` and `_remember_anime_source` handle playback and persistence.

## Error Handling

Provider errors should stay readable and actionable:

- Search failure: show existing staged `AnimeClientError` text.
- Episode load failure: keep the show detail view visible and enable Refresh Episodes.
- Stream resolution failure: keep the selected episode visible and enable Play again.
- No episodes: show "No episodes found for this mode."
- No fast stream: show the staged error or "No playable fast stream found for Episode X."

No raw tracebacks should appear in the UI. Debug details can remain in exception text for now because `AnimeClientError` already formats stage summaries and retry hints.

## Testing

Use offscreen PySide smoke tests for UI behavior and pure unit tests for helper logic.

Required coverage:

- Show detail helper matches history by show id, episode, and mode.
- Episode rows show resume/progress state.
- Home search can open show detail for a selected result.
- Mode switching reloads episodes for the same show.
- Play selected episode resolves a fast stream and calls existing playback path.
- Resume selected episode attaches `resume_position`.
- Episode load failure leaves Refresh enabled and shows a readable status.
- Existing Continue Watching tests remain green.

## Scope Boundaries

In scope:

- Show detail view.
- Episode list state.
- Mode switching inside show detail.
- Play/Resume from show detail.
- Refresh episode list.
- Focused tests and docs update.

Out of scope:

- Full poster/artwork metadata.
- Subtitle/audio picker UI.
- Multiple provider source picker.
- Local library import.
- PyInstaller or release automation.
- Rust migration of show detail state.

## Success Criteria

- A user can search a title, open its show detail view, select an episode, and play or resume it without using a stream-picker dialog as the primary workflow.
- Watched/resume information is visible before playback.
- Mode switching is explicit and predictable.
- Provider/cache behavior remains inside `AnimeClient`.
- `uv run pytest -q` and `cargo test` pass after implementation.
- `python -m graphify update . --force` runs after final code/doc changes.

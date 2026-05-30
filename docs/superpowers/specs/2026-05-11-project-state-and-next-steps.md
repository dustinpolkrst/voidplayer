# VoidPlayer Project State And Next Steps

> Written with Superpowers as a durable continuation spec for future development sessions. This is a product and architecture snapshot, not an implementation plan.

## Product Position

VoidPlayer is now a hackable anime streaming client. The desktop app should open into an anime-first experience with search, sub/dub mode selection, continue watching, resume timestamps, next-episode playback, and dark community-editable themes.

The lower-level `ffmpeg_pywrapper` package remains valuable, but it is secondary compatibility infrastructure. The app experience should not drift back into a generic local-file media player unless a future feature directly supports anime playback.

Keep this exact positioning phrase in app/docs copy unless the product direction changes:

```text
hackable anime streaming client
```

## Current Architecture

### App Shell

- Main GUI entrypoint: `src/ffmpeg_pywrapper/player/app.py`
- Console launchers: `animeplayer` and `voidplayer`
- Packaged app entrypoint: `packaging/voidplayer_entry.py`
- PyInstaller spec: `packaging/VoidPlayer.spec`

`PlayerWindow` owns the PySide6 UI, anime home screen, playback controls, menus, theme selection, continue-watching display, disclaimer flow, next-episode action, inspector, fullscreen behavior, and save-on-navigation behavior.

### Anime Provider Layer

- Provider code: `src/ffmpeg_pywrapper/anime.py`
- Important types: `AnimeClient`, `AnimeSearchResult`, `AnimeEpisode`, `AnimeStream`

`AnimeClient` handles search, episode lookup, fast stream resolution, fallback provider resolution, persisted query calls, m3u8 parsing, stream quality selection, and next-episode lookup. It returns stream metadata that can be converted into `MediaSource`.

The current UX priority is perceived speed. Prefer early playable streams and responsive UI over exhaustive provider completeness.

### Playback Layer

- Decode/playback engine: `src/ffmpeg_pywrapper/playback.py`
- Media contracts: `src/ffmpeg_pywrapper/media.py`

The live playback stack is:

```text
AnimeClient -> MediaSource -> DecodeLoopPlayer -> PyAV/sounddevice -> PySide6 rendering
```

`DecodeLoopPlayer` handles media loading, generation-guarded worker lifecycle, seek/play/pause/stop, audio/video decode threads, sounddevice output, subtitles, and state callbacks.

The original wrapper helpers are still useful for probing, scripting, FFmpeg command execution, and CLI compatibility. They are not the main live anime render loop.

### Config And Continue Watching

- Config persistence: `src/ffmpeg_pywrapper/player/config_store.py`
- Core record: `AnimeHistoryItem`

Continue watching stores anime title, show id, episode, sub/dub mode, stream URL, display name, timestamp, subtitle metadata when present, and update time.

Progress must be saved when playback state updates, when the app closes, before loading the next episode, and when pressing Home. When navigating away from playback, save the best available timestamp before stopping.

### Themes And Assets

- Theme loader: `src/ffmpeg_pywrapper/player/theme.py`
- Bundled themes: `src/ffmpeg_pywrapper/player/themes/`
- Bundled assets: `src/ffmpeg_pywrapper/player/assets/`

Themes are file-driven directories containing `theme.toml` and `style.qss`. Keep customization community-editable through files. Prefer theme-native assets such as `asset.chevron_down` for controls instead of generic CSS tricks.

The established visual direction is dark, neon, cyberpunk/goth/industrial, and open-source flavored. Preserve that when making narrow UI fixes.

### Website And Docs

- GitHub Pages site: `docs/`
- Main README: `README.md`

Docs should lead with the anime app and keep wrapper/CLI material as a compatibility section. Requirements should explicitly list Python 3.13, FFmpeg/ffprobe, and `uv`.

### Graphify

This repo has an explicit agent instruction:

```powershell
python -m graphify update . --force
```

Run that after code or documentation changes and keep generated artifacts under `graphify-out/`. Do not hand-edit generated graph files.

## Completed Work So Far

1. Renamed and repositioned the app as VoidPlayer while keeping the internal package import path as `ffmpeg_pywrapper`.
2. Moved the GUI into the packaged app under `src/ffmpeg_pywrapper/player/`.
3. Added package resource loading for themes and assets.
4. Added bundled dark themes and file-driven custom theme support.
5. Hardened FFmpeg runner behavior with bounded output support.
6. Hardened playback lifecycle with generation invalidation and safer worker shutdown.
7. Added PyAV/sounddevice decode playback for the app.
8. Added anime search, episode selection, sub/dub modes, stream resolution, and m3u8 parsing.
9. Added fast stream resolution so Play can happen quickly.
10. Added continue-watching history with resume timestamps.
11. Added anime-aware Next Episode behavior.
12. Added Home behavior that saves progress before leaving playback.
13. Refocused the desktop UI around anime browsing instead of local-file playlist controls.
14. Removed obsolete local-player UI surfaces from the app direction.
15. Added offscreen GUI smoke tests plus anime, theme, config, playback, runner, and CLI tests.
16. Added Windows portable packaging with PyInstaller.
17. Added a static docs site under `docs/`.
18. Added Graphify workflow expectations through `AGENTS.md`.
19. Added provider-stage errors and retry hints.
20. Added persistent search, episode, and stream cache support.
21. Upgraded Continue Watching with grouped history, progress, Resume, Next Episode, Remove, and near-end next behavior.

## Current Verification Anchors

Use these before claiming a development branch is ready:

```powershell
uv run pytest
uv run pyinstaller packaging\VoidPlayer.spec --clean --noconfirm
uv build
python -m graphify update . --force
```

For narrower player/anime work, this focused set has been useful:

```powershell
uv run pytest tests/test_anime.py tests/test_player_smoke.py tests/test_player_config.py tests/test_theme.py tests/test_playback.py
python -m graphify update . --force
```

Before shipping, also inspect:

```powershell
git status --short --branch
git diff --stat
```

The current checkout had pre-existing uncommitted changes when this spec was written, including README, pyproject, playback, tests, lockfile, docs, and packaging paths. Future work should verify which changes are intentional before committing or releasing.

## Development Principles For Future Sessions

- Keep the app anime-only unless the user explicitly changes direction.
- Optimize perceived speed in anime browsing and stream resolution.
- Preserve continue-watching visibility on smaller screens.
- Save progress before any navigation that exits playback.
- Treat Next as anime episode advancement when anime metadata exists.
- Keep themes file-driven and community-editable.
- Avoid broad visual redesigns when the request is a narrow affordance fix.
- Prefer targeted tests around the user-facing behavior being changed.
- Run Graphify after the last code/doc change, not before final edits.

## High-Impact Next Steps

## Roadmap To Preserve

This is the working product roadmap as of 2026-05-11. Phase 1 is the next development target. Later phases should stay visible so the project does not lose the broader direction while reliability work is underway.

### Phase 1: Provider Resilience And Stream Cache

Goal: make the core loop reliable enough that a user can trust Search, Play, Continue Watching, and Next Episode.

Build this first:

- Provider diagnostics that distinguish search failure, episode lookup failure, source-link failure, fast-provider failure, slow-provider failure, m3u8 parsing failure, and playback-load failure.
- User-facing retry and fallback messages that explain what happened without exposing raw provider internals by default.
- Structured debug detail that can be copied or inspected during development.
- A small persistent cache for anime search/episode metadata and resolved streams.
- Expiry rules that treat final stream URLs as short-lived while preserving slower-to-change episode metadata longer.
- Cache integration for Continue Watching and Next Episode so known shows resume faster and repeat fewer provider calls.

Success criteria:

- A failed provider path produces an actionable app message instead of a vague error.
- Continue Watching can re-resolve or reuse enough metadata to recover from stale stream URLs.
- Next Episode prefers fast cached metadata, then provider lookup, then a clear failure state.
- Focused anime/player tests cover success, fallback, stale cache, and provider failure cases.

### Phase 2: Rich Continue Watching

Goal: turn the home screen into the daily-use surface.

Build after Phase 1:

- Resume action for the highlighted history item.
- Remove-from-history action.
- Last-watched sorting that is obvious and stable.
- Grouping or visual clustering by show.
- Progress percentage when duration is known.
- Near-end handling that suggests the next episode instead of resuming the final seconds of the previous one.

Success criteria:

- A returning user can open the app and continue a show without re-searching.
- History stays editable and does not become stale clutter.
- Smaller screens still keep Continue Watching visible and useful.

### Phase 3: Show Detail And Episode Browser

Goal: replace the search-dialog feel with a real anime client workflow.

Build after the Continue Watching surface is stronger:

- Show detail screen with title, mode, episodes, watched state, and direct Play/Resume.
- Sub/dub availability display where provider data allows it.
- Episode list with clear loading and retry states.
- A path from search results into the show detail screen instead of straight into a modal-only flow.

Success criteria:

- Users can browse episodes before choosing one.
- Watched state makes sense across Continue Watching, search, and show detail.
- The app still gets to first playback quickly.

### Phase 4: Subtitle And Audio Controls

Goal: make anime playback quality controllable from the UI.

Build after the show/episode workflow exists:

- Subtitle track picker.
- External subtitle metadata display where provider data provides it.
- Audio stream picker for multi-audio sources.
- Per-show or per-mode subtitle/audio preference if the storage model is already stable enough.

Success criteria:

- Users can inspect and change subtitle/audio choices without opening the lower-level inspector.
- Preferences do not break fast playback or continue-watching resume.

### Phase 5: Theme Validation And Gallery

Goal: make the hackable theme system safe and inviting.

Build after the daily-use playback loop is stable:

- Theme validator for missing tokens, malformed colors, unsupported asset references, and common QSS mistakes.
- Theme preview/gallery that lets users inspect bundled and custom themes without restarting.
- Clear fallback behavior when a custom theme fails validation.

Success criteria:

- Theme authors get fast, concrete feedback.
- Broken custom themes do not leave the app unusable.

### Phase 6: Release Automation

Goal: make releases routine and repeatable.

Build once the app is reliable enough for regular prereleases:

- Release checklist script or documented command sequence.
- Full test run.
- Windows portable package build.
- Smoke launch of `dist\VoidPlayer\VoidPlayer.exe`.
- Audit for secrets, caches, logs, bytecode, and generated artifacts.
- Graphify rebuild.
- Tag and artifact attachment flow.

Success criteria:

- A future release can be cut without rediscovering packaging steps.
- Failed release checks clearly identify whether the blocker is tests, packaging, environment, or repo hygiene.

### 1. Provider Resilience And Diagnostics

Make anime search/play failures understandable and recoverable. Add a provider health layer that records which step failed: search, episodes, source links, fast provider, slow provider, m3u8 parse, or playback load. Surface a concise in-app error with a retry path and keep structured debug details available for development.

Why this matters: public anime sources are brittle. A great app needs graceful degradation instead of mysterious broken Play buttons.

### 2. Stream Resolution Cache

Add a small persistent cache for resolved episode streams with expiry and validation. Cache search/episode metadata separately from final stream URLs if URLs are short-lived.

Why this matters: it makes Continue Watching and Next Episode feel faster while reducing repeated provider calls.

### 3. Rich Continue Watching

Upgrade Continue Watching into a stronger home-screen workflow:

- Resume button for the highlighted item.
- Remove from history.
- Last watched sorting and grouping by show.
- Progress percentage when duration is known.
- Continue next unwatched episode when the previous one is near the end.

Why this matters: this is the core daily-use surface.

### 4. Episode Queue And Show Detail View

Add a show detail screen between search and playback. It should show episodes, sub/dub availability, current watched status, and a direct Play/Resume action.

Why this matters: search dialogs work for v1, but a real anime client needs a browsable show page.

### 5. Subtitle And Audio Controls

Promote subtitles/audio from internal playback support into polished UI:

- Subtitle track picker.
- External subtitle URL/file metadata where provider data allows it.
- Audio stream picker for multi-audio sources.
- Per-show subtitle preference.

Why this matters: anime playback quality depends heavily on subtitle behavior.

### 6. Local Library Metadata Without Local Playback Creep

If local files return, keep them as anime-library support, not generic media-player scope. A good boundary would be: import local anime episodes, match them to show metadata, and use the same continue-watching and next-episode model.

Why this matters: it expands usefulness while preserving the anime-only product.

### 7. Theme Gallery And Theme Validation

Add a developer-facing theme validator and a small in-app theme preview/gallery. Validate missing tokens, malformed colors, unsupported asset references, and common QSS mistakes.

Why this matters: the project promise is hackability. Theme authors need fast feedback.

### 8. Release Hardening

Build a repeatable release checklist:

- Run full tests.
- Build portable Windows package.
- Smoke launch `dist\VoidPlayer\VoidPlayer.exe`.
- Audit generated files and secrets.
- Rebuild Graphify.
- Tag release.
- Attach portable package.

Why this matters: the app is close enough to be useful; releases should become routine.

## Suggested Implementation Order

1. Provider diagnostics and user-facing retry/error states.
2. Stream resolution cache.
3. Rich Continue Watching.
4. Show detail view.
5. Subtitle/audio controls.
6. Theme validation and gallery.
7. Release automation.

This order improves reliability and the daily-use loop before expanding breadth.

## First Plan To Write Next

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

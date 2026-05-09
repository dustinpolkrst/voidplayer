# Graph Report - ffmpeg_pywrapper  (2026-05-09)

## Corpus Check
- 37 files · ~12,168 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 456 nodes · 1016 edges · 15 communities (13 shown, 2 thin omitted)
- Extraction: 75% EXTRACTED · 25% INFERRED · 0% AMBIGUOUS · INFERRED: 259 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fb790354`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]

## God Nodes (most connected - your core abstractions)
1. `PlayerWindow` - 80 edges
2. `DecodeLoopPlayer` - 75 edges
3. `run_ffmpeg()` - 25 edges
4. `PlayerWindow` - 23 edges
5. `MediaInfo` - 21 edges
6. `UnsupportedMediaError` - 15 edges
7. `ClipExportDialog` - 15 edges
8. `AudioOutputError` - 14 edges
9. `AudioClock` - 14 edges
10. `FFmpegConfig` - 13 edges

## Surprising Connections (you probably didn't know these)
- `test_missing_absolute_executable_raises()` --calls--> `FFmpegConfig`  [INFERRED]
  tests/test_config.py → src/ffmpeg_pywrapper/config.py
- `test_classifies_unsupported_codec()` --calls--> `classify_process_error()`  [INFERRED]
  tests/test_errors.py → src/ffmpeg_pywrapper/errors.py
- `test_classifies_invalid_command()` --calls--> `classify_process_error()`  [INFERRED]
  tests/test_errors.py → src/ffmpeg_pywrapper/errors.py
- `test_falls_back_to_process_error()` --calls--> `classify_process_error()`  [INFERRED]
  tests/test_errors.py → src/ffmpeg_pywrapper/errors.py
- `test_timestamp_helpers()` --calls--> `format_timestamp()`  [INFERRED]
  tests/test_media.py → src/ffmpeg_pywrapper/media.py

## Communities (15 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (12): format_timestamp(), nearest_preview(), _file_size(), main(), PlayerWindow, resource_path(), TimelineSlider, user_cache_path() (+4 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (24): _audio_frame_to_stereo_float32(), DecodeLoopPlayer, _default_output_sample_rate(), Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on (+16 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (41): build_command(), convert(), Build a plain argv list for a single-output FFmpeg command., thumbnail(), trim(), FFmpegConfig, Executable locations for system FFmpeg tools., _resolve_executable() (+33 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (34): Exception, classify_process_error(), FFmpegCancelledError, FFmpegError, FFmpegExecutableNotFound, FFmpegInvalidCommand, FFmpegProcessError, FFmpegTimeoutError (+26 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (25): Enum, AudioOutputError, DecodeError, PlaybackError, Base exception for playback-specific failures., Raised when no playable media stream is available., Raised when media decoding fails., Raised when audio output cannot be initialized. (+17 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (19): _frame_rate(), media_info_from_probe(), MediaInfo, _optional_float(), _optional_int(), seconds_from_timestamp(), _stream_info(), StreamInfo (+11 more)

### Community 6 - "Community 6"
Cohesion: 0.14
Nodes (20): load_recent_files(), save_recent_files(), user_config_path(), _float(), load_config(), media_state_from_config(), MediaState, normalize_media_key() (+12 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (12): configure_debug_logging(), QMainWindow, RuntimeError, main(), PlayerWindow, _flatten_tokens(), load_theme(), render_stylesheet() (+4 more)

### Community 8 - "Community 8"
Cohesion: 0.16
Nodes (17): _clean_text(), load_subtitles(), parse_ass(), _parse_ass_time(), parse_srt(), _parse_timed_blocks(), _parse_timestamp(), parse_vtt() (+9 more)

### Community 9 - "Community 9"
Cohesion: 0.17
Nodes (19): CLI, code:powershell (ffmpeg -version), code:powershell (uv sync --dev), code:powershell (uv run voidplayer), code:powershell (python -m ffmpeg_pywrapper probe input.mp4 --json), code:python (from ffmpeg_pywrapper import convert, probe, thumbnail, trim), code:python (from ffmpeg_pywrapper import build_command), code:python (import threading) (+11 more)

### Community 10 - "Community 10"
Cohesion: 0.26
Nodes (10): Chapter, _chapter_time(), generate_timeline_thumbnails(), parse_chapters(), preview_timestamps(), thumbnail_cache_dir(), test_generate_timeline_thumbnails_uses_thumbnail_helper(), test_parse_chapters_from_probe_payload() (+2 more)

### Community 11 - "Community 11"
Cohesion: 0.5
Nodes (6): _flatten_tokens(), load_theme(), render_stylesheet(), Theme, ThemeError, _validate_tokens()

### Community 12 - "Community 12"
Cohesion: 0.47
Nodes (5): code:powershell (uv sync), code:powershell (uv run voidplayer), code:powershell (uv run voidplayer --theme default), Simple Player Example, VoidPlayer Example

## Knowledge Gaps
- **26 isolated node(s):** `Build a plain argv list for a single-output FFmpeg command.`, `Executable locations for system FFmpeg tools.`, `Base exception for wrapper errors.`, `Raised when ffmpeg or ffprobe cannot be found.`, `Raised when a process exceeds its timeout.` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DecodeLoopPlayer` connect `Community 1` to `Community 0`, `Community 4`, `Community 5`, `Community 7`, `Community 8`?**
  _High betweenness centrality (0.229) - this node is a cross-community bridge._
- **Why does `PlayerWindow` connect `Community 0` to `Community 1`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 10`, `Community 11`?**
  _High betweenness centrality (0.226) - this node is a cross-community bridge._
- **Why does `run_ffmpeg()` connect `Community 2` to `Community 0`, `Community 3`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `PlayerWindow` (e.g. with `MediaInfo` and `DecodeLoopPlayer`) actually correct?**
  _`PlayerWindow` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `DecodeLoopPlayer` (e.g. with `AudioOutputError` and `DecodeError`) actually correct?**
  _`DecodeLoopPlayer` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 45 inferred relationships involving `str` (e.g. with `build_command()` and `_resolve_executable()`) actually correct?**
  _`str` has 45 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `run_ffmpeg()` (e.g. with `str` and `test_media_flow_with_system_ffmpeg()`) actually correct?**
  _`run_ffmpeg()` has 11 INFERRED edges - model-reasoned connections that need verification._
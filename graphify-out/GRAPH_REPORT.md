# Graph Report - ffmpeg_pywrapper  (2026-05-09)

## Corpus Check
- 29 files · ~7,175 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 295 nodes · 621 edges · 11 communities (9 shown, 2 thin omitted)
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 147 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `965297e7`
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

## God Nodes (most connected - your core abstractions)
1. `DecodeLoopPlayer` - 62 edges
2. `PlayerWindow` - 25 edges
3. `PlayerWindow` - 23 edges
4. `run_ffmpeg()` - 22 edges
5. `MediaInfo` - 14 edges
6. `AudioClock` - 14 edges
7. `FFmpegConfig` - 13 edges
8. `AudioOutputError` - 12 edges
9. `PlaybackClock` - 12 edges
10. `UnsupportedMediaError` - 11 edges

## Surprising Connections (you probably didn't know these)
- `test_missing_absolute_executable_raises()` --calls--> `FFmpegConfig`  [INFERRED]
  tests/test_config.py → src/ffmpeg_pywrapper/config.py
- `test_classifies_unsupported_codec()` --calls--> `classify_process_error()`  [INFERRED]
  tests/test_errors.py → src/ffmpeg_pywrapper/errors.py
- `test_classifies_invalid_command()` --calls--> `classify_process_error()`  [INFERRED]
  tests/test_errors.py → src/ffmpeg_pywrapper/errors.py
- `test_falls_back_to_process_error()` --calls--> `classify_process_error()`  [INFERRED]
  tests/test_errors.py → src/ffmpeg_pywrapper/errors.py
- `test_normalize_options_preserves_order_and_stream_specifiers()` --calls--> `normalize_options()`  [INFERRED]
  tests/test_commands.py → src/ffmpeg_pywrapper/options.py

## Communities (11 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (28): MediaInfo, StreamInfo, _audio_frame_to_stereo_float32(), DecodeLoopPlayer, _default_output_sample_rate(), Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on (+20 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (19): configure_debug_logging(), main(), PlayerSignals, PlayerWindow, resource_path(), _flatten_tokens(), load_theme(), render_stylesheet() (+11 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (38): Enum, Exception, AudioOutputError, classify_process_error(), DecodeError, FFmpegError, FFmpegExecutableNotFound, FFmpegInvalidCommand (+30 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (21): build_command(), convert(), Build a plain argv list for a single-output FFmpeg command., thumbnail(), trim(), FFmpegConfig, Executable locations for system FFmpeg tools., _resolve_executable() (+13 more)

### Community 4 - "Community 4"
Cohesion: 0.14
Nodes (22): FFmpegTimeoutError, Raised when a process exceeds its timeout., _parse_float(), _parse_int(), parse_progress_blocks(), _parse_time(), Progress, progress_from_mapping() (+14 more)

### Community 5 - "Community 5"
Cohesion: 0.14
Nodes (10): describe_media(), format_timestamp(), _frame_rate(), media_info_from_probe(), _optional_float(), _optional_int(), seconds_from_timestamp(), _stream_info() (+2 more)

### Community 6 - "Community 6"
Cohesion: 0.21
Nodes (14): CLI, code:powershell (uv sync --dev), code:powershell (uv run voidplayer), code:powershell (python -m ffmpeg_pywrapper input.mp4), code:python (from ffmpeg_pywrapper import convert, probe, thumbnail, trim), code:python (from ffmpeg_pywrapper import build_command), code:python (from ffmpeg_pywrapper import describe_media), Development (+6 more)

### Community 7 - "Community 7"
Cohesion: 0.5
Nodes (6): _flatten_tokens(), load_theme(), render_stylesheet(), Theme, ThemeError, _validate_tokens()

### Community 8 - "Community 8"
Cohesion: 0.47
Nodes (5): code:powershell (uv sync), code:powershell (uv run voidplayer), code:powershell (uv run voidplayer --theme default), Simple Player Example, VoidPlayer Example

## Knowledge Gaps
- **26 isolated node(s):** `Build a plain argv list for a single-output FFmpeg command.`, `Executable locations for system FFmpeg tools.`, `Base exception for wrapper errors.`, `Raised when ffmpeg or ffprobe cannot be found.`, `Raised when a process exceeds its timeout.` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DecodeLoopPlayer` connect `Community 0` to `Community 1`, `Community 2`?**
  _High betweenness centrality (0.259) - this node is a cross-community bridge._
- **Why does `run_ffmpeg()` connect `Community 4` to `Community 1`, `Community 2`, `Community 3`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Why does `PlayerWindow` connect `Community 1` to `Community 0`, `Community 2`, `Community 5`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `DecodeLoopPlayer` (e.g. with `AudioOutputError` and `DecodeError`) actually correct?**
  _`DecodeLoopPlayer` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `str` (e.g. with `build_command()` and `_resolve_executable()`) actually correct?**
  _`str` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `PlayerWindow` (e.g. with `DecodeLoopPlayer` and `PlaybackState`) actually correct?**
  _`PlayerWindow` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `PlayerWindow` (e.g. with `PlaybackState` and `VideoFrame`) actually correct?**
  _`PlayerWindow` has 4 INFERRED edges - model-reasoned connections that need verification._
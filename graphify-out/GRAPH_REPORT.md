# Graph Report - ffmpeg_pywrapper  (2026-05-09)

## Corpus Check
- 33 files · ~10,217 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 399 nodes · 860 edges · 14 communities (11 shown, 3 thin omitted)
- Extraction: 77% EXTRACTED · 23% INFERRED · 0% AMBIGUOUS · INFERRED: 196 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b7bec160`
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

## God Nodes (most connected - your core abstractions)
1. `DecodeLoopPlayer` - 74 edges
2. `PlayerWindow` - 58 edges
3. `run_ffmpeg()` - 25 edges
4. `PlayerWindow` - 23 edges
5. `MediaInfo` - 17 edges
6. `UnsupportedMediaError` - 15 edges
7. `AudioOutputError` - 14 edges
8. `AudioClock` - 14 edges
9. `FFmpegConfig` - 13 edges
10. `DecodeError` - 13 edges

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

## Communities (14 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (34): MediaInfo, StreamInfo, _audio_frame_to_stereo_float32(), DecodeLoopPlayer, _default_output_sample_rate(), Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on (+26 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (43): build_command(), convert(), Build a plain argv list for a single-output FFmpeg command., thumbnail(), trim(), FFmpegConfig, Executable locations for system FFmpeg tools., _resolve_executable() (+35 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (8): load_recent_files(), main(), PlayerWindow, resource_path(), save_recent_files(), user_config_path(), str, test_recent_files_round_trip()

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (26): Enum, AudioOutputError, DecodeError, PlaybackError, Raised when FFmpeg reports an unavailable codec., Base exception for playback-specific failures., Raised when no playable media stream is available., Raised when media decoding fails. (+18 more)

### Community 4 - "Community 4"
Cohesion: 0.1
Nodes (31): Exception, classify_process_error(), FFmpegCancelledError, FFmpegError, FFmpegInvalidCommand, FFmpegProcessError, FFmpegTimeoutError, FFmpegUnsupportedCodec (+23 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (12): format_timestamp(), _frame_rate(), media_info_from_probe(), _optional_float(), _optional_int(), seconds_from_timestamp(), _stream_info(), FFProbeResult (+4 more)

### Community 6 - "Community 6"
Cohesion: 0.12
Nodes (10): configure_debug_logging(), QMainWindow, main(), PlayerWindow, _flatten_tokens(), load_theme(), render_stylesheet(), Theme (+2 more)

### Community 7 - "Community 7"
Cohesion: 0.16
Nodes (16): _clean_text(), load_subtitles(), parse_ass(), _parse_ass_time(), parse_srt(), _parse_timed_blocks(), _parse_timestamp(), parse_vtt() (+8 more)

### Community 8 - "Community 8"
Cohesion: 0.17
Nodes (19): CLI, code:powershell (ffmpeg -version), code:powershell (uv sync --dev), code:powershell (uv run voidplayer), code:powershell (python -m ffmpeg_pywrapper probe input.mp4 --json), code:python (from ffmpeg_pywrapper import convert, probe, thumbnail, trim), code:python (from ffmpeg_pywrapper import build_command), code:python (import threading) (+11 more)

### Community 9 - "Community 9"
Cohesion: 0.5
Nodes (6): _flatten_tokens(), load_theme(), render_stylesheet(), Theme, ThemeError, _validate_tokens()

### Community 11 - "Community 11"
Cohesion: 0.47
Nodes (5): code:powershell (uv sync), code:powershell (uv run voidplayer), code:powershell (uv run voidplayer --theme default), Simple Player Example, VoidPlayer Example

## Knowledge Gaps
- **26 isolated node(s):** `Build a plain argv list for a single-output FFmpeg command.`, `Executable locations for system FFmpeg tools.`, `Base exception for wrapper errors.`, `Raised when ffmpeg or ffprobe cannot be found.`, `Raised when a process exceeds its timeout.` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DecodeLoopPlayer` connect `Community 0` to `Community 2`, `Community 3`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.265) - this node is a cross-community bridge._
- **Why does `PlayerWindow` connect `Community 2` to `Community 0`, `Community 3`, `Community 6`, `Community 7`, `Community 9`?**
  _High betweenness centrality (0.172) - this node is a cross-community bridge._
- **Why does `run_ffmpeg()` connect `Community 1` to `Community 2`, `Community 4`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Are the 31 inferred relationships involving `DecodeLoopPlayer` (e.g. with `AudioOutputError` and `DecodeError`) actually correct?**
  _`DecodeLoopPlayer` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `PlayerWindow` (e.g. with `DecodeLoopPlayer` and `PlaybackState`) actually correct?**
  _`PlayerWindow` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 39 inferred relationships involving `str` (e.g. with `build_command()` and `_resolve_executable()`) actually correct?**
  _`str` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `run_ffmpeg()` (e.g. with `str` and `test_media_flow_with_system_ffmpeg()`) actually correct?**
  _`run_ffmpeg()` has 11 INFERRED edges - model-reasoned connections that need verification._
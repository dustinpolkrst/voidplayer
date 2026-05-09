# Graph Report - ffmpeg_pywrapper  (2026-05-09)

## Corpus Check
- 31 files · ~8,673 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 341 nodes · 729 edges · 12 communities (10 shown, 2 thin omitted)
- Extraction: 78% EXTRACTED · 22% INFERRED · 0% AMBIGUOUS · INFERRED: 162 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1585fe7b`
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

## God Nodes (most connected - your core abstractions)
1. `DecodeLoopPlayer` - 67 edges
2. `PlayerWindow` - 32 edges
3. `run_ffmpeg()` - 25 edges
4. `PlayerWindow` - 23 edges
5. `MediaInfo` - 16 edges
6. `UnsupportedMediaError` - 14 edges
7. `AudioClock` - 14 edges
8. `FFmpegConfig` - 13 edges
9. `AudioOutputError` - 13 edges
10. `DecodeError` - 12 edges

## Surprising Connections (you probably didn't know these)
- `test_state_callback_is_not_called_while_lifecycle_lock_is_held()` --calls--> `DecodeLoopPlayer`  [INFERRED]
  tests/test_playback.py → src/ffmpeg_pywrapper/playback.py
- `test_master_clock_prefers_active_audio()` --calls--> `DecodeLoopPlayer`  [INFERRED]
  tests/test_playback.py → src/ffmpeg_pywrapper/playback.py
- `test_master_clock_reads_audio_only_after_audio_ready()` --calls--> `DecodeLoopPlayer`  [INFERRED]
  tests/test_playback.py → src/ffmpeg_pywrapper/playback.py
- `test_master_clock_falls_back_to_wall_clock()` --calls--> `DecodeLoopPlayer`  [INFERRED]
  tests/test_playback.py → src/ffmpeg_pywrapper/playback.py
- `test_video_start_waits_for_audio_readiness_when_audio_is_expected()` --calls--> `DecodeLoopPlayer`  [INFERRED]
  tests/test_playback.py → src/ffmpeg_pywrapper/playback.py

## Communities (12 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (45): build_command(), convert(), Build a plain argv list for a single-output FFmpeg command., thumbnail(), trim(), FFmpegConfig, Executable locations for system FFmpeg tools., _resolve_executable() (+37 more)

### Community 1 - "Community 1"
Cohesion: 0.12
Nodes (9): AudioOutputError, Raised when audio output cannot be initialized., DecodeLoopPlayer, _default_output_sample_rate(), Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on (+1 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (13): load_recent_files(), main(), PlayerWindow, resource_path(), save_recent_files(), user_config_path(), _flatten_tokens(), load_theme() (+5 more)

### Community 3 - "Community 3"
Cohesion: 0.1
Nodes (31): Exception, classify_process_error(), FFmpegCancelledError, FFmpegError, FFmpegInvalidCommand, FFmpegProcessError, FFmpegTimeoutError, FFmpegUnsupportedCodec (+23 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (22): Enum, DecodeError, PlaybackError, Raised when FFmpeg reports an unavailable codec., Base exception for playback-specific failures., Raised when no playable media stream is available., Raised when media decoding fails., UnsupportedMediaError (+14 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (13): describe_media(), format_timestamp(), _frame_rate(), media_info_from_probe(), _optional_float(), _optional_int(), seconds_from_timestamp(), _stream_info() (+5 more)

### Community 6 - "Community 6"
Cohesion: 0.1
Nodes (24): MediaInfo, StreamInfo, _audio_frame_to_stereo_float32(), RuntimeError, test_cli_describe_uses_media_summary(), test_audio_callback_outputs_silence_before_ready_without_advancing_clock(), test_audio_callback_writes_pcm_and_advances_clock_after_ready(), test_audio_warning_does_not_force_error_state() (+16 more)

### Community 7 - "Community 7"
Cohesion: 0.12
Nodes (10): configure_debug_logging(), QMainWindow, main(), PlayerWindow, _flatten_tokens(), load_theme(), render_stylesheet(), Theme (+2 more)

### Community 8 - "Community 8"
Cohesion: 0.18
Nodes (18): CLI, code:powershell (ffmpeg -version), code:powershell (uv sync --dev), code:powershell (uv run voidplayer), code:powershell (python -m ffmpeg_pywrapper probe input.mp4 --json), code:python (from ffmpeg_pywrapper import convert, probe, thumbnail, trim), code:python (from ffmpeg_pywrapper import build_command), code:python (import threading) (+10 more)

### Community 9 - "Community 9"
Cohesion: 0.47
Nodes (5): code:powershell (uv sync), code:powershell (uv run voidplayer), code:powershell (uv run voidplayer --theme default), Simple Player Example, VoidPlayer Example

## Knowledge Gaps
- **25 isolated node(s):** `Build a plain argv list for a single-output FFmpeg command.`, `Executable locations for system FFmpeg tools.`, `Base exception for wrapper errors.`, `Raised when ffmpeg or ffprobe cannot be found.`, `Raised when a process exceeds its timeout.` (+20 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DecodeLoopPlayer` connect `Community 1` to `Community 2`, `Community 4`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.252) - this node is a cross-community bridge._
- **Why does `run_ffmpeg()` connect `Community 0` to `Community 3`?**
  _High betweenness centrality (0.128) - this node is a cross-community bridge._
- **Why does `PlayerWindow` connect `Community 2` to `Community 1`, `Community 4`, `Community 5`, `Community 7`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Are the 28 inferred relationships involving `DecodeLoopPlayer` (e.g. with `AudioOutputError` and `DecodeError`) actually correct?**
  _`DecodeLoopPlayer` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `str` (e.g. with `build_command()` and `_resolve_executable()`) actually correct?**
  _`str` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `PlayerWindow` (e.g. with `DecodeLoopPlayer` and `PlaybackState`) actually correct?**
  _`PlayerWindow` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `run_ffmpeg()` (e.g. with `str` and `test_media_flow_with_system_ffmpeg()`) actually correct?**
  _`run_ffmpeg()` has 11 INFERRED edges - model-reasoned connections that need verification._
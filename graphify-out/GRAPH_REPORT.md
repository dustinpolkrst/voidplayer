# Graph Report - ffmpeg_pywrapper  (2026-05-09)

## Corpus Check
- 27 files · ~6,563 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 246 nodes · 500 edges · 14 communities (13 shown, 1 thin omitted)
- Extraction: 77% EXTRACTED · 23% INFERRED · 0% AMBIGUOUS · INFERRED: 113 edges (avg confidence: 0.69)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6a07e073`
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
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]

## God Nodes (most connected - your core abstractions)
1. `DecodeLoopPlayer` - 54 edges
2. `PlayerWindow` - 23 edges
3. `run_ffmpeg()` - 15 edges
4. `AudioClock` - 14 edges
5. `FFmpegConfig` - 13 edges
6. `MediaInfo` - 13 edges
7. `AudioOutputError` - 12 edges
8. `PlaybackClock` - 12 edges
9. `UnsupportedMediaError` - 11 edges
10. `DecodeError` - 11 edges

## Surprising Connections (you probably didn't know these)
- `PlayerSignals` --uses--> `DecodeLoopPlayer`  [INFERRED]
  examples/simple_player/main.py → src/ffmpeg_pywrapper/playback.py
- `PlayerSignals` --uses--> `PlaybackState`  [INFERRED]
  examples/simple_player/main.py → src/ffmpeg_pywrapper/playback.py
- `PlayerSignals` --uses--> `VideoFrame`  [INFERRED]
  examples/simple_player/main.py → src/ffmpeg_pywrapper/playback.py
- `PlayerWindow` --uses--> `DecodeLoopPlayer`  [INFERRED]
  examples/simple_player/main.py → src/ffmpeg_pywrapper/playback.py
- `PlayerWindow` --uses--> `PlaybackState`  [INFERRED]
  examples/simple_player/main.py → src/ffmpeg_pywrapper/playback.py

## Communities (14 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (30): build_command(), convert(), Build a plain argv list for a single-output FFmpeg command., thumbnail(), trim(), FFmpegConfig, Executable locations for system FFmpeg tools., _resolve_executable() (+22 more)

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (16): configure_debug_logging(), QMainWindow, QObject, RuntimeError, main(), PlayerSignals, PlayerWindow, _flatten_tokens() (+8 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (16): DecodeLoopPlayer, Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on, test_audio_callback_outputs_silence_before_ready_without_advancing_clock(), test_audio_callback_writes_pcm_and_advances_clock_after_ready(), test_audio_warning_does_not_force_error_state() (+8 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (13): Enum, DecodeError, Raised when media decoding fails., AudioClock, _ensure_decode_dependency(), frame_timing(), FrameTiming, PlaybackClock (+5 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (20): Exception, AudioOutputError, classify_process_error(), FFmpegError, FFmpegInvalidCommand, FFmpegProcessError, FFmpegUnsupportedCodec, _last_relevant_line() (+12 more)

### Community 5 - "Community 5"
Cohesion: 0.15
Nodes (10): describe_media(), format_timestamp(), _frame_rate(), media_info_from_probe(), _optional_float(), _optional_int(), seconds_from_timestamp(), _stream_info() (+2 more)

### Community 6 - "Community 6"
Cohesion: 0.21
Nodes (14): CLI, code:powershell (uv sync --dev), code:powershell (uv sync --extra player --group player), code:powershell (voidplayer input.mp4), code:python (from ffmpeg_pywrapper import convert, probe, thumbnail, trim), code:python (from ffmpeg_pywrapper import build_command), code:python (from ffmpeg_pywrapper import describe_media), Development (+6 more)

### Community 7 - "Community 7"
Cohesion: 0.23
Nodes (3): _audio_frame_to_stereo_float32(), _default_output_sample_rate(), test_packed_stereo_audio_frame_is_reshaped_without_duplication()

### Community 8 - "Community 8"
Cohesion: 0.39
Nodes (7): _parse_float(), _parse_int(), parse_progress_blocks(), _parse_time(), Progress, progress_from_mapping(), test_parse_progress_blocks()

### Community 10 - "Community 10"
Cohesion: 0.32
Nodes (8): Raised when no playable media stream is available., UnsupportedMediaError, MediaInfo, StreamInfo, VideoFrame, test_paused_seek_repositions_without_restarting_workers(), test_seek_clears_audio_buffers_without_reopening_output(), test_seek_while_playing_restarts_workers_at_seek_target()

### Community 12 - "Community 12"
Cohesion: 0.47
Nodes (5): code:powershell (uv sync --extra player --group player), code:powershell (uv run --extra player --group player python examples/simple_), code:powershell (uv run --extra player --group player python examples/simple_), Simple Player Example, VoidPlayer Example

## Knowledge Gaps
- **24 isolated node(s):** `Build a plain argv list for a single-output FFmpeg command.`, `Executable locations for system FFmpeg tools.`, `Base exception for wrapper errors.`, `Raised when ffmpeg or ffprobe cannot be found.`, `Raised when a process exceeds its timeout.` (+19 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DecodeLoopPlayer` connect `Community 2` to `Community 1`, `Community 3`, `Community 4`, `Community 7`, `Community 9`, `Community 10`, `Community 11`?**
  _High betweenness centrality (0.255) - this node is a cross-community bridge._
- **Why does `PlayerWindow` connect `Community 1` to `Community 10`, `Community 2`, `Community 3`, `Community 5`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Why does `run_ffmpeg()` connect `Community 0` to `Community 8`, `Community 1`, `Community 4`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `DecodeLoopPlayer` (e.g. with `PlayerSignals` and `PlayerWindow`) actually correct?**
  _`DecodeLoopPlayer` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `PlayerWindow` (e.g. with `DecodeLoopPlayer` and `PlaybackState`) actually correct?**
  _`PlayerWindow` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `str` (e.g. with `.__init__()` and `._build_ui()`) actually correct?**
  _`str` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `run_ffmpeg()` (e.g. with `str` and `test_media_flow_with_system_ffmpeg()`) actually correct?**
  _`run_ffmpeg()` has 4 INFERRED edges - model-reasoned connections that need verification._